import json
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error
from datetime import datetime


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
    url = "https://ims.gov.il/sites/default/files/ims_data/xml_files/isr_rad.xml"

    try:
        _safe_print(f"Fetching UV XML from: {url}")
        with urllib.request.urlopen(url, timeout=10) as response:
            raw_data = response.read()
            for encoding in ['utf-8', 'iso-8859-1', 'windows-1255', 'iso-8859-8', 'cp1255']:
                try:
                    xml_data = raw_data.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                xml_data = raw_data.decode('utf-8', errors='ignore')
    except (urllib.error.URLError, UnicodeDecodeError) as e:
        _safe_print(f"Failed to fetch/decode UV XML: {e}")
        return {}

    root = ET.fromstring(xml_data)
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
    """Fetch and parse IMS sea forecast XML data into a JSON payload."""
    url = "https://ims.gov.il/sites/default/files/ims_data/xml_files/isr_sea.xml"

    try:
        _safe_print(f"Fetching XML from: {url}")
        with urllib.request.urlopen(url, timeout=10) as response:
            raw_data = response.read()
            for encoding in ['utf-8', 'iso-8859-1', 'windows-1255', 'iso-8859-8', 'cp1255']:
                try:
                    xml_data = raw_data.decode(encoding)
                    _safe_print(f"Successfully decoded with {encoding}, length: {len(xml_data)}")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                xml_data = raw_data.decode('utf-8', errors='ignore')
                _safe_print(f"Decoded with errors ignored, length: {len(xml_data)}")
    except (urllib.error.URLError, UnicodeDecodeError) as e:
        _safe_print(f"Failed to fetch/decode XML: {e}, using fallback data")
        xml_data = """<IsraelSeaForecastMorning>
<Originator>
<Organization>Israel Meteorological Service</Organization>
<Generator>Global Distribution of Meteorological Information</Generator>
</Originator>
<Identification>
<Title>Israel Sea Forecast (Morning)</Title>
<IssueDateTime>2025-09-17 00:03</IssueDateTime>
</Identification>
<Location>
<LocationMetaData>
<LocationId>213</LocationId>
<LocationNameEng>Southern Coast</LocationNameEng>
<LocationNameHeb>החוף הדרומי</LocationNameHeb>
</LocationMetaData>
<LocationData>
<TimeUnitData>
<DateTimeFrom>2025-09-17 08:00</DateTimeFrom>
<DateTimeTo>2025-09-17 20:00</DateTimeTo>
<Element>
<ElementName>Sea status and waves height</ElementName>
<ElementValue>50 / 50-80</ElementValue>
</Element>
<Element>
<ElementName>Sea temperature</ElementName>
<ElementValue>30</ElementValue>
</Element>
<Element>
<ElementName>Wind direction and speed</ElementName>
<ElementValue>225-315/10-25</ElementValue>
</Element>
</TimeUnitData>
</LocationData>
</Location>
<Location>
<LocationMetaData>
<LocationId>210</LocationId>
<LocationNameEng>Central Coast</LocationNameEng>
<LocationNameHeb>החוף המרכזי</LocationNameHeb>
</LocationMetaData>
<LocationData>
<TimeUnitData>
<DateTimeFrom>2025-09-17 08:00</DateTimeFrom>
<DateTimeTo>2025-09-17 20:00</DateTimeTo>
<Element>
<ElementName>Sea status and waves height</ElementName>
<ElementValue>50 / 50-80</ElementValue>
</Element>
<Element>
<ElementName>Sea temperature</ElementName>
<ElementValue>30</ElementValue>
</Element>
<Element>
<ElementName>Wind direction and speed</ElementName>
<ElementValue>225-315/10-25</ElementValue>
</Element>
</TimeUnitData>
</LocationData>
</Location>
<Location>
<LocationMetaData>
<LocationId>212</LocationId>
<LocationNameEng>Northern Coast</LocationNameEng>
<LocationNameHeb>החוף הצפוני</LocationNameHeb>
</LocationMetaData>
<LocationData>
<TimeUnitData>
<DateTimeFrom>2025-09-17 08:00</DateTimeFrom>
<DateTimeTo>2025-09-17 20:00</DateTimeTo>
<Element>
<ElementName>Sea status and waves height</ElementName>
<ElementValue>50 / 50-80</ElementValue>
</Element>
<Element>
<ElementName>Sea temperature</ElementName>
<ElementValue>29</ElementValue>
</Element>
<Element>
<ElementName>Wind direction and speed</ElementName>
<ElementValue>225-315/10-25</ElementValue>
</Element>
</TimeUnitData>
</LocationData>
</Location>
<Location>
<LocationMetaData>
<LocationId>211</LocationId>
<LocationNameEng>Sea of Galilee</LocationNameEng>
<LocationNameHeb>כנרת</LocationNameHeb>
</LocationMetaData>
<LocationData>
<TimeUnitData>
<DateTimeFrom>2025-09-17 08:00</DateTimeFrom>
<DateTimeTo>2025-09-17 20:00</DateTimeTo>
<Element>
<ElementName>Sea status and waves height</ElementName>
<ElementValue>40 / 30-80</ElementValue>
</Element>
<Element>
<ElementName>Sea temperature</ElementName>
<ElementValue>29</ElementValue>
</Element>
<Element>
<ElementName>Wind direction and speed</ElementName>
<ElementValue>225-315/10-35</ElementValue>
</Element>
</TimeUnitData>
</LocationData>
</Location>
<Location>
<LocationMetaData>
<LocationId>214</LocationId>
<LocationNameEng>Gulf of Eilat</LocationNameEng>
<LocationNameHeb>מפרץ אילת</LocationNameHeb>
</LocationMetaData>
<LocationData>
<TimeUnitData>
<DateTimeFrom>2025-09-17 08:00</DateTimeFrom>
<DateTimeTo>2025-09-17 20:00</DateTimeTo>
<Element>
<ElementName>Sea status and waves height</ElementName>
<ElementValue>30 / 20-40</ElementValue>
</Element>
<Element>
<ElementName>Sea temperature</ElementName>
<ElementValue>27</ElementValue>
</Element>
<Element>
<ElementName>Wind direction and speed</ElementName>
<ElementValue>360-045/15-30</ElementValue>
</Element>
</TimeUnitData>
</LocationData>
</Location>
</IsraelSeaForecastMorning>"""

    _safe_print("Parsing XML data...")
    root = ET.fromstring(xml_data)
    uv_payload = _build_uv_payload()

    forecast_data = {
        "metadata": {
            "organization": root.find('.//Organization').text if root.find('.//Organization') is not None else '',
            "title": root.find('.//Title').text if root.find('.//Title') is not None else '',
            "issue_datetime": root.find('.//IssueDateTime').text if root.find('.//IssueDateTime') is not None else ''
        },
        "locations": []
    }
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
            'statusCode': 500,
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