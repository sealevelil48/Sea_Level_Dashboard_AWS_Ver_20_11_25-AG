"""IMS Mediterranean mariners forecast (medit_sea.xml) → JSON. Moved out of the server module."""
import logging

import requests

try:  # hardened XML parser (no entity expansion); falls back to stdlib
    from defusedxml.ElementTree import fromstring
except ImportError:  # pragma: no cover
    from xml.etree.ElementTree import fromstring

logger = logging.getLogger(__name__)

IMS_MARINERS_URL = "https://ims.gov.il/sites/default/files/ims_data/xml_files/medit_sea.xml"


def _decode(raw: bytes) -> str:
    for enc in ("windows-1255", "iso-8859-8", "utf-8"):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if "ã" not in text[:500] and "é" not in text[:500]:  # mojibake markers
            return text
    return raw.decode("utf-8", errors="replace")


def _text(node, path):
    found = node.find(path) if node is not None else None
    return found.text if found is not None and found.text is not None else ""


def fetch_mariners_forecast(timeout: int = 10) -> dict:
    resp = requests.get(IMS_MARINERS_URL, timeout=timeout)
    resp.raise_for_status()
    root = fromstring(_decode(resp.content))
    metadata = {
        "organization": _text(root, ".//Organization"),
        "title": _text(root, ".//Title"),
        "issue_datetime": _text(root, ".//IssueDateTime"),
    }
    locations = []
    for loc in root.findall(".//Location"):
        meta = loc.find("LocationMetaData")
        item = {
            "id": _text(meta, "LocationId"),
            "name_eng": _text(meta, "LocationNameEng"),
            "name_heb": _text(meta, "LocationNameHeb"),
            "forecasts": [],
        }
        data = loc.find("LocationData")
        for tu in (data.findall("TimeUnitData") if data is not None else []):
            item["forecasts"].append({
                "from": _text(tu, "DateTimeFrom"),
                "to": _text(tu, "DateTimeTo"),
                "elements": {_text(el, "ElementName"): _text(el, "ElementValue") for el in tu.findall("Element")},
            })
        locations.append(item)
    return {"metadata": metadata, "locations": locations}
