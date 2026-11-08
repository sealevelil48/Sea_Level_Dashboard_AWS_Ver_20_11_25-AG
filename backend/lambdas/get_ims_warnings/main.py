"""IMS warnings: merges the IMS general and sea alert RSS feeds.

Feeds (RSS 2.0, us-ascii, ttl 15 min):
  general: rssAlert_general_country_en.xml  - all country-wide warnings (rain, floods,
           thunderstorms, heat, and also some sea warnings)
  sea:     rssAlert_sea_country_en.xml      - sea-only warnings (high sea swimming danger,
           sea state, etc.)

Response (backwards compatible: every item still has title/description/pub_date/severity):
  {
    "warnings": [ {title, title_clean, description, pub_date, severity, category,
                   feeds, valid_from, valid_until, link}, ... ],   # active only, most severe first
    "counts": {"total": n, "sea": n, "general": n},
    "feed_status": {"general": "ok" | "<error>", "sea": "ok" | "<error>"},
    "last_updated": ISO time, "source": "IMS RSS Feed"
  }
"""
import html
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
    ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")
except Exception:  # tzdata missing: fixed +02:00 is close enough for expiry checks
    ISRAEL_TZ = timezone(timedelta(hours=2))

FEEDS = {
    "general": "https://ims.gov.il/sites/default/files/ims_data/rss/alert/rssAlert_general_country_en.xml",
    "sea": "https://ims.gov.il/sites/default/files/ims_data/rss/alert/rssAlert_sea_country_en.xml",
}
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SeaLevelDashboard/1.1",
    "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
    "Cache-Control": "no-cache",
}
SEA_KEYWORDS = ("sea", "wave", "swimming", "coast", "marine", "gulf")
SEVERITY_RANK = {"red": 0, "orange": 1, "yellow": 2, "info": 3}

# Last good parse per feed, so a transient IMS hiccup doesn't blank the card (warm Lambda / local server)
_last_good_items = {}


def _fetch_feed(url, attempts=2):
    last_exc = None
    for attempt in range(attempts):
        try:
            resp = requests.get(url, params={"_": int(time.time())}, headers=_HEADERS, timeout=10)
            resp.raise_for_status()
            return ET.fromstring(resp.content)
        except Exception as e:
            last_exc = e
            if attempt < attempts - 1:
                time.sleep(1)
    raise last_exc


def _clean_text(raw):
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _clean_title(title):
    """'Orange Warning - High Sea Swimming Danger Updated on:07/11 21:36' -> 'High Sea Swimming Danger'"""
    t = re.sub(r"\s*Updated on:.*$", "", title or "", flags=re.IGNORECASE)
    t = re.sub(r"^\s*(red|orange|yellow)\s+warning\s*[-:]\s*", "", t, flags=re.IGNORECASE)
    return t.strip()


def get_warning_severity(title_text, description_text=""):
    """Severity from the IMS colour code (title first, then description), else a keyword fallback."""
    for text in (title_text or "", description_text or ""):
        m = re.search(r"\b(red|orange|yellow)\b", text, flags=re.IGNORECASE)
        if m:
            return m.group(1).lower()
    lower = (title_text or "").lower()
    if any(w in lower for w in ("severe", "extreme")):
        return "red"
    if "significant" in lower:
        return "orange"
    if any(w in lower for w in ("heat", "danger", "high")):
        return "yellow"
    return "info"


_DT = r"(\d{1,2})/(\d{1,2})(?:/\d{2,4})?\s+(\d{1,2})(?::(\d{2}))?"
_VALIDITY_RE = re.compile(
    r"from\s*" + _DT + r"\s*(?:LT)?\s*(?:until|till|to|-)\s*(?:(\d{1,2})/(\d{1,2})(?:/\d{2,4})?\s+)?(\d{1,2})(?::(\d{2}))?",
    re.IGNORECASE,
)


def _parse_validity(description, pub_dt):
    """Best-effort parse of 'from 07/11 22 until 08/11 22 LT' / 'from 07/11 06:00 to 10:00'.

    Returns (valid_from, valid_until) as aware datetimes in Israel time, or (None, None).
    """
    m = _VALIDITY_RE.search(description or "")
    if not m:
        return None, None
    try:
        year = (pub_dt or datetime.now(ISRAEL_TZ)).astimezone(ISRAEL_TZ).year
        d1, mo1, h1, mi1, d2, mo2, h2, mi2 = m.groups()
        start = datetime(year, int(mo1), int(d1), int(h1) % 24, int(mi1 or 0), tzinfo=ISRAEL_TZ)
        if d2 and mo2:
            end = datetime(year, int(mo2), int(d2), int(h2) % 24, int(mi2 or 0), tzinfo=ISRAEL_TZ)
        else:
            end = start.replace(hour=int(h2) % 24, minute=int(mi2 or 0))
        if int(h2) == 24:
            end += timedelta(days=1)
        if end < start:  # crosses midnight or new year
            end = end + timedelta(days=1) if d2 is None else end.replace(year=end.year + 1)
        return start, end
    except (ValueError, TypeError):
        return None, None


def _parse_items(root, feed_name):
    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        desc = _clean_text(item.findtext("description"))
        pub_raw = (item.findtext("pubDate") or "").strip()
        try:
            pub_dt = parsedate_to_datetime(pub_raw) if pub_raw else None
        except (TypeError, ValueError):
            pub_dt = None
        valid_from, valid_until = _parse_validity(desc, pub_dt)
        title_clean = _clean_title(title)
        is_sea = feed_name == "sea" or any(k in (title_clean + " " + desc).lower() for k in SEA_KEYWORDS)
        items.append({
            "title": title,
            "title_clean": title_clean,
            "description": desc,
            "pub_date": pub_raw,
            "severity": get_warning_severity(title, desc),
            "category": "sea" if is_sea else "general",
            "feeds": [feed_name],
            "valid_from": valid_from.isoformat() if valid_from else None,
            "valid_until": valid_until.isoformat() if valid_until else None,
            "link": (item.findtext("link") or "").strip() or "https://www.ims.gov.il/en/IMSWarnings",
            "_pub_ts": pub_dt.timestamp() if pub_dt else 0,
        })
    return items


def collect_warnings(now=None):
    now = now or datetime.now(ISRAEL_TZ)
    feed_status = {}
    all_items = []
    for name, url in FEEDS.items():
        try:
            items = _parse_items(_fetch_feed(url), name)
            _last_good_items[name] = items
            feed_status[name] = "ok"
        except Exception as e:
            logger.error(f"IMS {name} alerts feed failed: {e}")
            items = _last_good_items.get(name, [])
            feed_status[name] = f"error ({type(e).__name__}){' - using last good copy' if items else ''}"
        all_items.extend(items)

    # De-duplicate: the same sea warning often appears in both feeds
    merged = {}
    for it in all_items:
        key = (it["title_clean"].lower(), it["pub_date"])
        if key in merged:
            merged[key]["feeds"] = sorted(set(merged[key]["feeds"]) | set(it["feeds"]))
            if it["category"] == "sea":
                merged[key]["category"] = "sea"
        else:
            merged[key] = dict(it)

    active = []
    for it in merged.values():
        if it["valid_until"]:
            if datetime.fromisoformat(it["valid_until"]) < now:
                continue  # expired; IMS sometimes keeps old items in the feed
        active.append(it)

    active.sort(key=lambda w: (SEVERITY_RANK.get(w["severity"], 9), -w["_pub_ts"]))
    for w in active:
        w.pop("_pub_ts", None)

    return {
        "warnings": active,
        "counts": {
            "total": len(active),
            "sea": sum(1 for w in active if w["category"] == "sea"),
            "general": sum(1 for w in active if w["category"] == "general"),
        },
        "feed_status": feed_status,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source": "IMS RSS Feed",
    }


def lambda_handler(event, context):
    """Fetch IMS warnings from the general + sea RSS feeds."""
    try:
        payload = collect_warnings()
        all_failed = all(s != "ok" for s in payload["feed_status"].values()) and not payload["warnings"]
        return {
            "statusCode": 503 if all_failed else 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=300",
            },
            "body": json.dumps(payload),
        }
    except Exception as e:
        logger.error(f"Error fetching IMS warnings: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e), "warnings": []}),
        }
