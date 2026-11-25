import json
import os
import tempfile
import time
import xml.etree.ElementTree as ET
import urllib.request
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
    ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")
except Exception:  # tzdata missing (e.g. bare Windows venv): fixed +02:00 is close enough for an age check
    from datetime import timedelta
    ISRAEL_TZ = timezone(timedelta(hours=2))

IMS_SEA_FORECAST_URL = "https://ims.gov.il/sites/default/files/ims_data/xml_files/isr_sea.xml"
IMS_UV_URL = "https://ims.gov.il/sites/default/files/ims_data/xml_files/isr_rad.xml"
# IMS issues the sea forecast daily; anything older than this is flagged stale.
MAX_ISSUE_AGE_HOURS = 36
# Bot filters in front of ims.gov.il can reject the default "Python-urllib/x.y"
# agent. Previously any fetch failure silently served hard-coded 2025 data.
_IMS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SeaLevelDashboard/1.1",
    "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}
_LAST_GOOD_PATH = os.path.join(tempfile.gettempdir(), "ims_isr_sea_last_good.xml")
_last_good_mem = None  # (bytes, fetched_at_iso)


def _fetch_ims_bytes(url, timeout=10, attempts=3):
    """GET an IMS file with a browser-like UA, a cache-buster and retries."""
    sep = "&" if "?" in url else "?"
    last_exc = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(f"{url}{sep}_={int(time.time())}", headers=_IMS_HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except Exception as e:  # URLError, HTTPError, socket.timeout/TimeoutError, ConnectionResetError
            last_exc = e
            if attempt < attempts - 1:
                time.sleep(1.5 * (attempt + 1))
    raise last_exc


def _save_last_good(raw, fetched_at):
    global _last_good_mem
    _last_good_mem = (raw, fetched_at)
    try:
        with open(_LAST_GOOD_PATH, "wb") as f:
            f.write(raw)
        with open(_LAST_GOOD_PATH + ".ts", "w", encoding="utf-8") as f:
            f.write(fetched_at)
    except OSError:
        pass


def _load_last_good():
    if _last_good_mem is not None:
        return _last_good_mem
    try:
        with open(_LAST_GOOD_PATH, "rb") as f:
            raw = f.read()
        with open(_LAST_GOOD_PATH + ".ts", encoding="utf-8") as f:
            ts = f.read().strip()
        return raw, ts
    except OSError:
        return None


def _normalize_city_name(name):
    """Normalize a city name for robust matching (strip, collapse spaces, lowercase)."""
    if not name:
        return ""
    return " ".join(str(name).strip().split()).lower()


# Map IMS UV-feed English city names (from <LocationNameEng>) -> dashboard sections.
# Keys are normalized (lowercase) names. Only cities present in the live isr_rad.xml
# feed are used as data sources.
UV_CITY_TO_SECTION = {
    "tiberias": "Sea of Galilee",
    "eilat": "Gulf of Eilat",
    "haifa": "Northern Coast",
    "acre": "Northern Coast",
    "ashdod": "Southern Coast",
    "ashkelon": "Southern Coast",
    "tel aviv": "Central Coast",
    "tel-aviv": "Central Coast",
    "tel aviv-yafo": "Central Coast",
    # The live feed has no Tel Aviv station; Hadera is the closest
    # central-coast station and supplies Central Coast UV data.
    "hadera": "Central Coast",
}


def _safe_print(message):
    """Avoid crashing when stdout is no longer connected (broken pipe)."""
    try:
        print(message)
    except (BrokenPipeError, OSError, ValueError):
        pass


def _parse_datetime(value):
    """Parse IMS datetime strings into datetime objects."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def _parse_uv_index(raw_value):
    """Parse UV index from IMS radiation feed values."""
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        if value.upper() == "M":
            return 4
        if value.upper() == "L":
            return 0
        return None


def _uv_severity_label(uv_value):
    """Return a human-friendly UV severity label."""
    if uv_value is None:
        return "N/A"
    if uv_value >= 8:
        return "Very High"
    if uv_value >= 6:
        return "High"
    if uv_value >= 3:
        return "Moderate"
    return "Low"


def _build_uv_payload():
    """Fetch and filter the IMS UV feed down to the cities relevant to the sea forecast."""
    url = IMS_UV_URL

    try:
        _safe_print(f"Fetching UV XML from: {url}")
        root = ET.fromstring(_fetch_ims_bytes(url, attempts=2))
    except Exception as e:  # UV is optional enrichment; never fail the forecast over it
        _safe_print(f"Failed to fetch/parse UV XML: {e}")
        return {}

    uv_payload = {}

    for location in root.findall('Location'):
        location_meta = location.find('LocationMetaData')
        if location_meta is None:
            continue

        # Strictly identify the city by its English name; ignore Hebrew tags.
        city_name = (location_meta.findtext('LocationNameEng') or '').strip()
        if not city_name:
            continue

        # Route the city to a dashboard section using the English name only.
        if _normalize_city_name(city_name) not in UV_CITY_TO_SECTION:
            continue

        location_data = location.find('LocationData')
        if location_data is None:
            continue

        hourly_series = []
        for time_unit in location_data.findall('TimeUnitData'):
            solrad_period = time_unit.find('SolRadPeriod')
            element = time_unit.find('Element')
            if solrad_period is None or element is None:
                continue

            hourly_series.append({
                'from': solrad_period.findtext('DateTimeFrom') or '',
                'to': solrad_period.findtext('DateTimeTo') or '',
                'value': element.findtext('ElementValue') or '',
                'index': _parse_uv_index(element.findtext('ElementIndex'))
            })

        if hourly_series:
            # Key by the raw English feed name so the section matcher can find it.
            uv_payload[city_name] = hourly_series

    return uv_payload


def build_forecast_payload():
    """Fetch and parse IMS sea forecast XML data into a JSON payload.

    Freshness contract (fields under ``metadata``):
      - ``source``: "live" (fetched now) or "cache" (IMS unreachable, last good copy)
      - ``fetched_at``: UTC ISO time the XML was actually downloaded from IMS
      - ``stale``: True if served from cache or the IMS issue time is > 36 h old
      - ``fetch_error``: why the live fetch failed (only when source == "cache")

    If IMS is unreachable and no good copy has ever been fetched, this raises
    instead of serving invented data (the old hard-coded 2025-09-17 fallback).
    """
    url = IMS_SEA_FORECAST_URL
    source = "live"
    fetch_error = None

    try:
        raw_data = _fetch_ims_bytes(url)
        root = ET.fromstring(raw_data)  # bytes: honours the XML's declared ISO-8859-8 encoding
        if root.find('.//IssueDateTime') is None or not root.findall('Location'):
            raise ValueError("IMS sea forecast XML has no IssueDateTime/Location elements")
        fetched_at = datetime.now(timezone.utc).isoformat()
        _save_last_good(raw_data, fetched_at)
    except Exception as e:  # network, HTTP 4xx/5xx, timeout, malformed XML
        fetch_error = f"{type(e).__name__}: {e}"
        _safe_print(f"Live IMS forecast fetch failed ({fetch_error}); trying last good copy")
        cached = _load_last_good()
        if cached is None:
            raise RuntimeError(f"IMS sea forecast unavailable and no cached copy: {fetch_error}")
        raw_data, fetched_at = cached
        root = ET.fromstring(raw_data)
        source = "cache"

    uv_payload = _build_uv_payload()

    forecast_data = {
        "metadata": {
            "organization": root.find('.//Organization').text if root.find('.//Organization') is not None else '',
            "title": root.find('.//Title').text if root.find('.//Title') is not None else '',
            "issue_datetime": root.find('.//IssueDateTime').text if root.find('.//IssueDateTime') is not None else '',
            "source": source,
            "fetched_at": fetched_at,
            "fetch_error": fetch_error,
        },
        "locations": []
    }
    issue_dt = _parse_datetime(forecast_data["metadata"]["issue_datetime"])
    issue_age_h = None
    if issue_dt is not None:
        issue_age_h = (datetime.now(ISRAEL_TZ).replace(tzinfo=None) - issue_dt).total_seconds() / 3600
    forecast_data["metadata"]["issue_age_hours"] = round(issue_age_h, 1) if issue_age_h is not None else None
    forecast_data["metadata"]["stale"] = source != "live" or (issue_age_h is not None and issue_age_h > MAX_ISSUE_AGE_HOURS)
    _safe_print(f"Parsed metadata: {forecast_data['metadata']}")

    for location in root.findall('Location'):
        location_meta = location.find('LocationMetaData')
        location_data = location.find('LocationData')

        if location_meta is None:
            continue

        original_name = location_meta.find('LocationNameEng').text if location_meta.find('LocationNameEng') is not None else ''
        mapped_name = map_location_name(original_name)

        location_info = {
            "id": location_meta.find('LocationId').text if location_meta.find('LocationId') is not None else '',
            "name_eng": mapped_name,
            "name_heb": location_meta.find('LocationNameHeb').text if location_meta.find('LocationNameHeb') is not None else '',
            "coordinates": get_location_coordinates(mapped_name),
            "forecasts": []
        }

        if location_data is None:
            forecast_data["locations"].append(location_info)
            continue

        for time_unit in location_data.findall('TimeUnitData'):
            forecast_period = {
                "from": time_unit.find('DateTimeFrom').text if time_unit.find('DateTimeFrom') is not None else '',
                "to": time_unit.find('DateTimeTo').text if time_unit.find('DateTimeTo') is not None else '',
                "elements": {}
            }

            for element in time_unit.findall('Element'):
                element_name = element.find('ElementName').text if element.find('ElementName') is not None else ''
                element_value = element.find('ElementValue').text if element.find('ElementValue') is not None else ''

                if element_name == "Sea status and waves height":
                    forecast_period["elements"]["wave_height"] = element_value
                elif element_name == "Sea temperature":
                    try:
                        forecast_period["elements"]["sea_temperature"] = int(element_value)
                    except (ValueError, TypeError):
                        forecast_period["elements"]["sea_temperature"] = element_value
                elif element_name == "Wind direction and speed":
                    forecast_period["elements"]["wind"] = element_value

            block_start = _parse_datetime(forecast_period.get('from'))
            block_end = _parse_datetime(forecast_period.get('to'))
            # Cities that feed this dashboard section, per the English-name mapping.
            relevant_city_keys = [city for city, section in UV_CITY_TO_SECTION.items() if section == mapped_name]
            matched_hours = []

            for city_key in relevant_city_keys:
                # Find the feed series for this city (keyed by its raw English name).
                hourly_series = next(
                    (series for raw_name, series in uv_payload.items() if _normalize_city_name(raw_name) == city_key),
                    []
                )
                for entry in hourly_series:
                    entry_start = _parse_datetime(entry.get('from'))
                    entry_end = _parse_datetime(entry.get('to'))
                    if entry_start and entry_end and block_start and block_end:
                        if entry_start < block_end and entry_end > block_start:
                            matched_hours.append(entry)

            if matched_hours:
                uv_values = [entry.get('index') for entry in matched_hours if entry.get('index') is not None]
                max_uv = max(uv_values) if uv_values else None
                min_uv = min(uv_values) if uv_values else None
                summary = f"Max {max_uv}" if max_uv is not None else "N/A"
                if min_uv is not None and max_uv is not None and min_uv != max_uv:
                    summary = f"{min_uv}-{max_uv}"
                display_value = f"{summary} ({_uv_severity_label(max_uv)})" if max_uv is not None else "N/A"
                forecast_period["elements"]["uv_index"] = {
                    "value": max_uv,
                    "display": display_value,
                    "severity": _uv_severity_label(max_uv).lower().replace(' ', '-'),
                    "hourly_values": [
                        {
                            "from": entry.get('from'),
                            "to": entry.get('to'),
                            "index": entry.get('index'),
                            "label": _uv_severity_label(entry.get('index'))
                        }
                        for entry in matched_hours
                    ],
                    "range": f"{min_uv}-{max_uv}" if min_uv is not None and max_uv is not None and min_uv != max_uv else str(max_uv) if max_uv is not None else None,
                }
            else:
                forecast_period["elements"]["uv_index"] = {
                    "value": None,
                    "display": "N/A",
                    "severity": "secondary",
                    "hourly_values": [],
                    "range": None,
                }

            location_info["forecasts"].append(forecast_period)

        forecast_data["locations"].append(location_info)

    _safe_print(f"Processed {len(forecast_data['locations'])} locations")
    return forecast_data


def lambda_handler(event, context):
    """Fetch and parse IMS sea forecast XML data"""
    try:
        forecast_data = build_forecast_payload()
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps(forecast_data)
        }
    except Exception as e:
        _safe_print(f"Error in lambda_handler: {e}")
        return {
            'statusCode': 503,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }


def map_location_name(original_name):
    """Map IMS location names to our preferred names"""
    name_mapping = {
        "Gulf of Elat": "Gulf of Eilat"
    }
    return name_mapping.get(original_name, original_name)

def get_location_coordinates(location_name):
    # Validate input to prevent injection
    if not isinstance(location_name, str) or len(location_name) > 100:
        return {"lat": 32.0, "lng": 34.8}
    
    # Whitelist allowed location names
    allowed_locations = {
        "Southern Coast": {"lat": 31.462314, "lng": 34.348573},
        "Central Coast": {"lat": 32.061196, "lng": 34.752568},
        "Northern Coast": {"lat": 32.904018, "lng": 35.069794},
        "Sea of Galilee": {"lat": 32.8, "lng": 35.6},
        "Gulf of Eilat": {"lat": 29.537478, "lng": 34.952816}
    }
    
    # Only return coordinates for whitelisted locations
    if location_name in allowed_locations:
        return allowed_locations[location_name]
    return {"lat": 32.0, "lng": 34.8}