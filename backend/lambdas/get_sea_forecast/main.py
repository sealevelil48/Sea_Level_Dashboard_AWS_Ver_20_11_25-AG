import json
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error


def _safe_print(message):
    """Avoid crashing when stdout is no longer connected (broken pipe)."""
    try:
        print(message)
    except (BrokenPipeError, OSError, ValueError):
        pass


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