# Sea Level Dashboard - API Documentation

Version 2.0.0 | Base URL: `http://localhost:30886` (Development) | Last Updated: November 2025

## Table of Contents

1. [Introduction](#introduction)
2. [Authentication](#authentication)
3. [Base URL and Versioning](#base-url-and-versioning)
4. [Response Formats](#response-formats)
5. [Error Handling](#error-handling)
6. [Rate Limiting](#rate-limiting)
7. [Core Endpoints](#core-endpoints)
8. [Data Endpoints](#data-endpoints)
9. [Analytics Endpoints](#analytics-endpoints)
10. [Prediction Endpoints](#prediction-endpoints)
11. [Anomaly Detection Endpoints](#anomaly-detection-endpoints)
12. [Weather and Forecast Endpoints](#weather-and-forecast-endpoints)
13. [Status and Health Endpoints](#status-and-health-endpoints)
14. [Code Examples](#code-examples)
15. [Changelog](#changelog)

---

## Introduction

The Sea Level Dashboard API provides programmatic access to sea level monitoring data, predictions, and analytics for Israeli coastal stations. The API follows REST principles and returns JSON-formatted responses.

### Key Features

- Real-time and historical sea level data
- Multi-station batch queries for performance
- Advanced anomaly detection using Southern Baseline Rules
- Machine learning-based predictions (Kalman Filter, Prophet)
- Weather and mariners forecasts integration
- Comprehensive analytics and statistics

### API Standards

- **Protocol**: HTTP/HTTPS
- **Format**: JSON
- **Methods**: GET, POST, OPTIONS
- **Encoding**: UTF-8
- **Timezone**: All timestamps in ISO 8601 format (UTC or local time with timezone)

---

## Authentication

### Current Status: Public Access

The API currently does not require authentication. All endpoints are publicly accessible.

### Future Authentication (v3.0)

Planned authentication methods:
- API Key authentication
- JWT tokens
- OAuth 2.0

---

## Base URL and Versioning

### Development
```
http://127.0.0.1:30886
```

### Production
```
https://your-domain.com
```

### API Versioning

Currently using implicit v2 (no version in URL). Future versions will use:
```
https://your-domain.com/api/v3/...
```

### Interactive Documentation

**Swagger UI (OpenAPI):**
```
http://localhost:30886/docs
```

**ReDoc:**
```
http://localhost:30886/redoc
```

---

## Response Formats

### Success Response

```json
{
  "data": [...],
  "metadata": {
    "count": 100,
    "page": 1,
    "per_page": 100
  },
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### Error Response

```json
{
  "error": "Invalid date format",
  "message": "Date must be in YYYY-MM-DD format",
  "status_code": 400,
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### Standard Headers

**Request Headers:**
```
Content-Type: application/json
Accept: application/json
```

**Response Headers:**
```
Content-Type: application/json; charset=utf-8
X-Response-Time: 45ms
X-Cache: HIT
Cache-Control: public, max-age=120
Access-Control-Allow-Origin: *
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 400 | Bad Request | Invalid parameters |
| 404 | Not Found | Resource not found |
| 408 | Request Timeout | Processing timeout |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Feature not available |

### Error Response Format

```json
{
  "error": "Error type",
  "message": "Detailed error message",
  "status_code": 400,
  "details": {
    "parameter": "start_date",
    "provided_value": "invalid",
    "expected_format": "YYYY-MM-DD"
  },
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### Common Error Scenarios

**Invalid Date Format (400)**
```json
{
  "error": "Invalid date format. Use YYYY-MM-DD format.",
  "example": "2025-11-01",
  "provided_start_date": "15/01/2025",
  "provided_end_date": "31/01/2025"
}
```

**Date Range Too Large (400)**
```json
{
  "error": "Date range too large. Maximum 365 days allowed.",
  "requested_days": 400,
  "max_days": 365
}
```

**Station Not Found (404)**
```json
{
  "error": "Station 'InvalidStation' not found",
  "valid_stations": ["Acre", "Yafo", "Ashkelon", "Eilat"],
  "hint": "Use 'All Stations' to get data from all stations"
}
```

---

## Rate Limiting

### Current Limits

No explicit rate limiting implemented. Fair use policy applies.

### Future Limits (v3.0)

Planned rate limits:
- **Free Tier**: 100 requests/hour
- **Standard**: 1000 requests/hour
- **Premium**: Unlimited

Rate limit headers (planned):
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 987
X-RateLimit-Reset: 1642342800
```

---

## Core Endpoints

### Get Stations

Retrieve list of all monitoring stations.

**Endpoint:**
```
GET /api/stations
```

**Parameters:** None

**Response:**
```json
{
  "stations": [
    "Acre",
    "Haifa",
    "Ashdod",
    "Ashkelon",
    "Yafo",
    "Eilat",
    "All Stations"
  ],
  "count": 7,
  "database_available": true
}
```

**Example:**
```bash
curl http://localhost:30886/api/stations
```

**Response Codes:**
- `200 OK`: Success
- `500 Internal Server Error`: Database connection failed

---

## Data Endpoints

### Get Data

Retrieve historical sea level data for a station.

**Endpoint:**
```
GET /api/data
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| station | string | No | "All Stations" | Station name or "All Stations" |
| start_date | string | No | 7 days ago | Start date (YYYY-MM-DD) |
| end_date | string | No | Today | End date (YYYY-MM-DD) |
| data_source | string | No | "default" | Data source type |
| limit | integer | No | 15000 | Maximum records |

**Response:**
```json
[
  {
    "Station": "Acre",
    "Tab_DateTime": "2025-01-15T10:30:00",
    "Tab_Value": 1.234,
    "Tab_Temp": 18.5
  },
  {
    "Station": "Acre",
    "Tab_DateTime": "2025-01-15T10:36:00",
    "Tab_Value": 1.246,
    "Tab_Temp": 18.5
  }
]
```

**Example:**
```bash
# Get last 7 days for Acre
curl "http://localhost:30886/api/data?station=Acre"

# Get specific date range
curl "http://localhost:30886/api/data?station=Acre&start_date=2025-01-01&end_date=2025-01-31"

# Get all stations
curl "http://localhost:30886/api/data?station=All%20Stations&start_date=2025-01-15&end_date=2025-01-15"
```

**Validation Rules:**
- `start_date` must be before `end_date`
- Date range cannot exceed 365 days
- Station must exist in database (or be "All Stations")

**Performance:**
- Response time: 50-500ms (depending on range and cache)
- Cached for 2 minutes
- Header `X-Cache: HIT` indicates cache hit

**Response Codes:**
- `200 OK`: Success (may return empty array if no data)
- `400 Bad Request`: Invalid parameters
- `404 Not Found`: Station not found
- `500 Internal Server Error`: Database error

---

### Get Data Batch

Retrieve data for multiple stations in a single request (optimized).

**Endpoint:**
```
GET /api/data/batch
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| stations | string | Yes | - | Comma-separated station names |
| start_date | string | No | 7 days ago | Start date (YYYY-MM-DD) |
| end_date | string | No | Today | End date (YYYY-MM-DD) |
| data_source | string | No | "default" | Data source type |
| show_anomalies | boolean | No | false | Include anomaly markers |
| include_outliers | boolean | No | false | Include outlier flags |

**Response:**
```json
[
  {
    "Station": "Acre",
    "Tab_DateTime": "2025-01-15T10:30:00",
    "Tab_Value": 1.234,
    "Tab_Temp": 18.5,
    "is_anomaly": false
  },
  {
    "Station": "Yafo",
    "Tab_DateTime": "2025-01-15T10:30:00",
    "Tab_Value": 1.198,
    "Tab_Temp": 19.2,
    "is_anomaly": false
  }
]
```

**Example:**
```bash
# Get data for three stations
curl "http://localhost:30886/api/data/batch?stations=Acre,Yafo,Eilat&start_date=2025-01-01&end_date=2025-01-07"

# Include anomaly detection
curl "http://localhost:30886/api/data/batch?stations=Acre,Yafo&start_date=2025-01-01&end_date=2025-01-31&show_anomalies=true"
```

**Performance Benefits:**
- Single database query for all stations
- 2-3x faster than individual requests
- Response time: 100-800ms (cached)

**Response Codes:**
- `200 OK`: Success
- `400 Bad Request`: Invalid parameters
- `500 Internal Server Error`: Database error

---

### Get Live Data

Retrieve the most recent measurements for all stations.

**Endpoint:**
```
GET /api/live-data
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| station | string | No | All | Filter by specific station |

**Response:**
```json
[
  {
    "Station": "Acre",
    "Tab_DateTime": "2025-01-15T10:36:00",
    "Tab_Value": 1.246,
    "Tab_Temp": 18.5,
    "minutes_old": 0
  },
  {
    "Station": "Yafo",
    "Tab_DateTime": "2025-01-15T10:36:00",
    "Tab_Value": 1.198,
    "Tab_Temp": 19.2,
    "minutes_old": 0
  }
]
```

**Example:**
```bash
# Get all stations
curl http://localhost:30886/api/live-data

# Get specific station
curl "http://localhost:30886/api/live-data?station=Acre"
```

**Update Frequency:**
- Data updated every 6 minutes
- API cached for 1 minute

**Response Codes:**
- `200 OK`: Success
- `500 Internal Server Error`: Database error

---

## Analytics Endpoints

### Get Analytics

Perform server-side analytics calculations using SQL window functions.

**Endpoint:**
```
GET /api/analytics
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| analysis_type | string | Yes | - | Type of analysis (see below) |
| station | string | No | "All Stations" | Station name |
| station1 | string | No | - | First station (for comparisons) |
| station2 | string | No | - | Second station (for comparisons) |
| start_date | string | No | 7 days ago | Start date |
| end_date | string | No | Today | End date |
| window_hours | string | No | "3,6,24" | Rolling window sizes (comma-separated) |
| period_days | integer | No | 7 | Trendline period |
| lag_hours | integer | No | 1 | Lag/lead hours |

**Analysis Types:**

1. **Rolling Average** (`rolling_avg`)
   - Calculates moving averages over specified windows
   - Use `window_hours` to specify window sizes (e.g., "3,6,24")

2. **Trendline** (`trendline`)
   - Fits linear trendline to data
   - Use `period_days` to specify trend period

3. **Station Difference** (`station_diff`)
   - Calculates difference between two stations
   - Requires `station1` and `station2` parameters

4. **Lag/Lead Analysis** (`lag_lead`)
   - Compares current value with lagged/future values
   - Use `lag_hours` to specify offset

**Example: Rolling Average**
```bash
curl "http://localhost:30886/api/analytics?analysis_type=rolling_avg&station=Acre&start_date=2025-01-01&end_date=2025-01-31&window_hours=3,6,24"
```

**Response:**
```json
{
  "analysis_type": "rolling_avg",
  "station": "Acre",
  "data": [
    {
      "Tab_DateTime": "2025-01-01T00:00:00",
      "Tab_Value": 1.234,
      "rolling_avg_3h": 1.230,
      "rolling_avg_6h": 1.228,
      "rolling_avg_24h": 1.225
    }
  ]
}
```

**Example: Station Difference**
```bash
curl "http://localhost:30886/api/analytics?analysis_type=station_diff&station1=Acre&station2=Yafo&start_date=2025-01-01&end_date=2025-01-07"
```

**Response:**
```json
{
  "analysis_type": "station_diff",
  "station1": "Acre",
  "station2": "Yafo",
  "data": [
    {
      "Tab_DateTime": "2025-01-01T00:00:00",
      "station1_value": 1.234,
      "station2_value": 1.198,
      "difference": 0.036
    }
  ]
}
```

**Response Codes:**
- `200 OK`: Success
- `400 Bad Request`: Invalid analysis type or parameters
- `500 Internal Server Error`: Calculation error

---

## Prediction Endpoints

### Get Predictions

Generate sea level forecasts using machine learning models.

**Endpoint:**
```
GET /api/predictions
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| stations | string | Yes | - | Station name(s), comma-separated |
| model | string | No | "kalman" | Prediction model |
| steps | integer | No | 240 | Forecast steps (6-minute intervals) |
| forecast_hours | integer | No | - | Alternative to steps (in hours) |

**Models:**

| Model | Best For | Accuracy | Speed |
|-------|----------|----------|-------|
| kalman | 24-72 hours | ±3-5 cm | Fast (< 1s) |
| prophet | Weekly forecasts | ±10-15 cm | Slow (3-5s) |

**Response:**
```json
{
  "Acre": {
    "timestamps": [
      "2025-01-15T10:42:00",
      "2025-01-15T10:48:00"
    ],
    "values": [1.248, 1.251],
    "confidence_lower": [1.201, 1.203],
    "confidence_upper": [1.295, 1.299],
    "model_used": "kalman",
    "forecast_horizon_hours": 24
  },
  "metadata": {
    "generated_at": "2025-01-15T10:36:00",
    "model_parameters": {
      "process_noise": 0.001,
      "measurement_noise": 0.01
    }
  }
}
```

**Example:**
```bash
# 48-hour forecast for Acre using Kalman Filter
curl "http://localhost:30886/api/predictions?stations=Acre&model=kalman&forecast_hours=48"

# Weekly forecast for multiple stations using Prophet
curl "http://localhost:30886/api/predictions?stations=Acre,Yafo,Eilat&model=prophet&forecast_hours=168"
```

**Conversion:**
- 1 hour = 10 steps (6-minute intervals)
- 24 hours = 240 steps
- 48 hours = 480 steps
- 168 hours (7 days) = 1680 steps

**Response Codes:**
- `200 OK`: Success
- `400 Bad Request`: Invalid parameters or model
- `500 Internal Server Error`: Model fitting failed

---

## Anomaly Detection Endpoints

### Get Outliers

Detect anomalies using Enhanced Southern Baseline Rules (Python-based).

**Endpoint:**
```
GET /api/outliers
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| station | string | No | "All Stations" | Station name |
| start_date | string | No | 7 days ago | Start date |
| end_date | string | No | Today | End date |

**Response:**
```json
{
  "outliers": [
    {
      "Station": "Acre",
      "Tab_DateTime": "2025-01-05T14:30:00",
      "Tab_Value": 2.456,
      "expected_value": 1.234,
      "deviation": 1.222,
      "rule_violated": "extreme_deviation",
      "confidence": 0.95
    }
  ],
  "total_records": 1680,
  "outliers_detected": 23,
  "outlier_percentage": 1.37,
  "validation": {
    "total_validations": 1680,
    "total_exclusions": 45,
    "exclusion_rate": 2.68,
    "outliers_detected": 23,
    "baseline_calculations": 1635
  },
  "processing_time_seconds": 1.23,
  "timestamp": "2025-01-15T10:36:00"
}
```

**Example:**
```bash
curl "http://localhost:30886/api/outliers?station=Acre&start_date=2025-01-01&end_date=2025-01-31"
```

**Performance:**
- Typical: 0.5-2 seconds for 7 days
- Maximum: 30 seconds timeout
- Automatic limiting to 5000 records for safety

**Response Codes:**
- `200 OK`: Success (empty result if no data)
- `408 Request Timeout`: Processing timeout
- `500 Internal Server Error`: Processing failed
- `503 Service Unavailable`: Feature not available

---

### Get Outliers (Optimized)

Detect anomalies using SQL-based Southern Baseline Rules (10-50x faster).

**Endpoint:**
```
GET /api/outliers/optimized
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| station | string | No | "All Stations" | Station name |
| start_date | string | No | 7 days ago | Start date |
| end_date | string | No | Today | End date |
| use_cache | boolean | No | true | Use materialized view cache |

**Response:** (Same structure as `/api/outliers` but with `performance` field)

```json
{
  "outliers": [...],
  "total_records": 1680,
  "outliers_detected": 23,
  "outlier_percentage": 1.37,
  "validation": {...},
  "performance": {
    "query_time_seconds": 0.15,
    "cache_used": true,
    "records_processed": 1680
  },
  "timestamp": "2025-01-15T10:36:00"
}
```

**Example:**
```bash
# Use cache (fast)
curl "http://localhost:30886/api/outliers/optimized?station=Acre&start_date=2025-01-08&end_date=2025-01-15&use_cache=true"

# Force fresh calculation (slower but most current)
curl "http://localhost:30886/api/outliers/optimized?station=Acre&start_date=2025-01-01&end_date=2025-01-15&use_cache=false"
```

**Performance Comparison:**

| Date Range | Standard | Optimized (cached) | Speedup |
|------------|----------|-------------------|---------|
| 7 days | 1.2s | 0.15s | 8x |
| 30 days | 4.5s | 0.30s | 15x |
| 90 days | 12.0s | 0.80s | 15x |

**Response Codes:**
- `200 OK`: Success
- `500 Internal Server Error`: Query failed
- `503 Service Unavailable`: Feature not available

---

### Refresh Outliers Cache

Manually refresh the materialized view cache for outliers.

**Endpoint:**
```
POST /api/outliers/refresh-cache
```

**Parameters:** None

**Response:**
```json
{
  "success": true,
  "records_processed": 45000,
  "processing_time_seconds": 2.34,
  "timestamp": "2025-01-15T10:36:00"
}
```

**Example:**
```bash
curl -X POST http://localhost:30886/api/outliers/refresh-cache
```

**Use Cases:**
- Scheduled cron job (hourly/daily)
- Manual refresh after data ingestion
- Troubleshooting stale cache

**Response Codes:**
- `200 OK`: Success
- `500 Internal Server Error`: Refresh failed
- `503 Service Unavailable`: Feature not available

---

### Get Outliers Metrics

Retrieve performance metrics for the outliers API.

**Endpoint:**
```
GET /api/outliers/metrics
```

**Parameters:** None

**Response:**
```json
{
  "cache_hit_rate": 78.5,
  "total_queries": 1523,
  "avg_query_time_ms": 150,
  "cache_last_refreshed": "2025-01-15T10:00:00",
  "cache_size_mb": 12.4
}
```

**Example:**
```bash
curl http://localhost:30886/api/outliers/metrics
```

**Response Codes:**
- `200 OK`: Success
- `503 Service Unavailable`: Feature not available

---

### Get Corrections

Generate correction suggestions for detected outliers.

**Endpoint:**
```
GET /api/corrections
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| station | string | No | "All Stations" | Station name |
| start_date | string | No | 7 days ago | Start date |
| end_date | string | No | Today | End date |

**Response:**
```json
{
  "suggestions": [
    {
      "station": "Acre",
      "timestamp": "2025-01-05T14:30:00",
      "original_value": 2.456,
      "suggested_value": 1.234,
      "confidence": 0.92,
      "method": "station_baseline",
      "neighbors": [
        {
          "station": "Haifa",
          "value": 1.245,
          "distance_km": 15
        }
      ]
    }
  ],
  "total_suggestions": 23,
  "timestamp": "2025-01-15T10:36:00"
}
```

**Example:**
```bash
curl "http://localhost:30886/api/corrections?station=Acre&start_date=2025-01-01&end_date=2025-01-31"
```

**Correction Methods:**
- `interpolation`: Time-based interpolation (highest confidence)
- `station_baseline`: Based on neighboring stations
- `historical_average`: Historical pattern matching

**Response Codes:**
- `200 OK`: Success
- `500 Internal Server Error`: Calculation failed
- `503 Service Unavailable`: Feature not available

---

## Weather and Forecast Endpoints

### Get Sea Forecast

Retrieve IMS sea conditions forecast.

**Endpoint:**
```
GET /api/sea-forecast
```

**Parameters:** None

**Response:**
```json
{
  "locations": [
    {
      "id": "1",
      "name_eng": "Northern Coast",
      "name_heb": "החוף הצפוני",
      "forecasts": [
        {
          "from": "2025-01-15T00:00:00",
          "to": "2025-01-15T12:00:00",
          "elements": {
            "wave_height": "1-2 meters",
            "wind_direction": "NW",
            "wind_speed": "15-20 knots",
            "sea_state": "Moderate"
          }
        }
      ]
    }
  ]
}
```

**Example:**
```bash
curl http://localhost:30886/api/sea-forecast
```

**Update Frequency:**
- IMS updates twice daily (06:00, 18:00 local time)
- API caches for 6 hours

**Response Codes:**
- `200 OK`: Success
- `500 Internal Server Error`: IMS API unavailable

---

### Get Mariners Forecast

Retrieve detailed mariners forecast from IMS.

**Endpoint:**
```
GET /api/mariners-forecast
```

**Parameters:** None

**Response:**
```json
{
  "metadata": {
    "organization": "Israel Meteorological Service",
    "title": "Mediterranean Sea Forecast",
    "issue_datetime": "2025-01-15T06:00:00"
  },
  "locations": [
    {
      "id": "1",
      "name_eng": "Rosh Hanikra to Haifa",
      "name_heb": "ראש הנקרה - חיפה",
      "forecasts": [
        {
          "from": "2025-01-15T12:00:00",
          "to": "2025-01-16T00:00:00",
          "elements": {
            "wave_height": "1.5-2.5m",
            "wave_direction": "NW",
            "wind_speed": "15-25kt",
            "wind_direction": "NW",
            "weather": "Partly cloudy",
            "visibility": "Good"
          }
        }
      ]
    }
  ]
}
```

**Example:**
```bash
curl http://localhost:30886/api/mariners-forecast
```

**Regions Covered:**
- Rosh Hanikra to Haifa (Northern)
- Haifa to Ashkelon (Central)
- Ashkelon to Rafah (Southern)
- Eilat (Red Sea)

**Response Codes:**
- `200 OK`: Success
- `500 Internal Server Error`: IMS API unavailable

---

### Get IMS Warnings

Retrieve active weather warnings.

**Endpoint:**
```
GET /api/ims-warnings
```

**Parameters:** None

**Response:**
```json
{
  "warnings": [
    {
      "id": "W123",
      "severity": "yellow",
      "type": "high_wind",
      "regions": ["Northern Coast", "Central Coast"],
      "effective": "2025-01-15T10:00:00",
      "expires": "2025-01-15T22:00:00",
      "description": "Strong westerly winds expected",
      "description_heb": "צפויות רוחות מערביות חזקות"
    }
  ]
}
```

**Example:**
```bash
curl http://localhost:30886/api/ims-warnings
```

**Severity Levels:**
- `green`: Normal conditions
- `yellow`: Watch/Advisory
- `orange`: Warning
- `red`: Severe Warning

**Response Codes:**
- `200 OK`: Success
- `500 Internal Server Error`: IMS API unavailable

---

## Status and Health Endpoints

### Health Check

Check API and system health.

**Endpoint:**
```
GET /api/health
```

**Parameters:** None

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:36:00",
  "platform": "win32",
  "python_version": "3.9.7 (default, Sep 16 2021, 13:09:58)",
  "server_status": "online",
  "database": "connected",
  "cache": {
    "status": "connected",
    "hits": 1234,
    "misses": 345,
    "hit_rate": "78.2%",
    "keys": 156
  },
  "metrics": {
    "query_count": 1523,
    "avg_response_time_ms": 45,
    "cache_hit_rate": "78.2%"
  }
}
```

**Example:**
```bash
curl http://localhost:30886/api/health
```

**Status Values:**
- `healthy`: All systems operational
- `degraded`: Some features unavailable
- `unhealthy`: Critical issues

**Use Cases:**
- Load balancer health checks
- Monitoring systems
- Uptime tracking

**Response Codes:**
- `200 OK`: System healthy
- `503 Service Unavailable`: System unhealthy

---

## Code Examples

### Python

#### Basic Request

```python
import requests

# Get stations
response = requests.get('http://localhost:30886/api/stations')
stations = response.json()
print(stations['stations'])

# Get data for Acre
response = requests.get(
    'http://localhost:30886/api/data',
    params={
        'station': 'Acre',
        'start_date': '2025-01-01',
        'end_date': '2025-01-31'
    }
)
data = response.json()
print(f"Retrieved {len(data)} records")
```

#### Error Handling

```python
import requests

try:
    response = requests.get(
        'http://localhost:30886/api/data',
        params={
            'station': 'InvalidStation',
            'start_date': '2025-01-01',
            'end_date': '2025-01-31'
        },
        timeout=10
    )
    response.raise_for_status()
    data = response.json()
except requests.exceptions.HTTPError as e:
    error_data = e.response.json()
    print(f"Error: {error_data['error']}")
    print(f"Message: {error_data['message']}")
except requests.exceptions.Timeout:
    print("Request timed out")
except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
```

#### Batch Data Fetching

```python
import requests
import pandas as pd

# Get data for multiple stations
response = requests.get(
    'http://localhost:30886/api/data/batch',
    params={
        'stations': 'Acre,Yafo,Eilat',
        'start_date': '2025-01-01',
        'end_date': '2025-01-07'
    }
)
data = response.json()

# Convert to pandas DataFrame
df = pd.DataFrame(data)

# Group by station
for station, group in df.groupby('Station'):
    print(f"{station}: {len(group)} records")
    print(f"  Mean: {group['Tab_Value'].mean():.3f}m")
    print(f"  Std: {group['Tab_Value'].std():.3f}m")
```

#### Predictions

```python
import requests
import matplotlib.pyplot as plt
from datetime import datetime

# Get 48-hour prediction for Acre
response = requests.get(
    'http://localhost:30886/api/predictions',
    params={
        'stations': 'Acre',
        'model': 'kalman',
        'forecast_hours': 48
    }
)
result = response.json()
acre_forecast = result['Acre']

# Plot
timestamps = [datetime.fromisoformat(ts) for ts in acre_forecast['timestamps']]
values = acre_forecast['values']
confidence_lower = acre_forecast['confidence_lower']
confidence_upper = acre_forecast['confidence_upper']

plt.figure(figsize=(12, 6))
plt.plot(timestamps, values, 'b-', label='Forecast')
plt.fill_between(timestamps, confidence_lower, confidence_upper,
                 alpha=0.3, label='95% Confidence Interval')
plt.xlabel('Time')
plt.ylabel('Sea Level (m)')
plt.title('Acre 48-Hour Forecast (Kalman Filter)')
plt.legend()
plt.grid(True)
plt.show()
```

### JavaScript (Node.js)

#### Basic Request

```javascript
const axios = require('axios');

async function getStations() {
  try {
    const response = await axios.get('http://localhost:30886/api/stations');
    console.log('Stations:', response.data.stations);
    return response.data;
  } catch (error) {
    console.error('Error:', error.message);
    if (error.response) {
      console.error('Response:', error.response.data);
    }
  }
}

async function getData(station, startDate, endDate) {
  try {
    const response = await axios.get('http://localhost:30886/api/data', {
      params: {
        station: station,
        start_date: startDate,
        end_date: endDate
      }
    });
    console.log(`Retrieved ${response.data.length} records for ${station}`);
    return response.data;
  } catch (error) {
    console.error('Error:', error.message);
    return [];
  }
}

// Usage
getStations();
getData('Acre', '2025-01-01', '2025-01-31');
```

### JavaScript (Browser/React)

```javascript
// Using Fetch API
async function fetchData(station, startDate, endDate) {
  try {
    const params = new URLSearchParams({
      station: station,
      start_date: startDate,
      end_date: endDate
    });

    const response = await fetch(
      `http://localhost:30886/api/data?${params}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    console.log(`Fetched ${data.length} records`);
    return data;

  } catch (error) {
    console.error('Fetch error:', error);
    return [];
  }
}

// React component example
import React, { useState, useEffect } from 'react';

function SeaLevelChart() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch(
          'http://localhost:30886/api/data?station=Acre&start_date=2025-01-01&end_date=2025-01-31'
        );

        if (!response.ok) throw new Error('Network response was not ok');

        const result = await response.json();
        setData(result);
        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div>
      <h2>Sea Level Data for Acre</h2>
      <p>{data.length} records loaded</p>
      {/* Chart rendering code */}
    </div>
  );
}
```

### curl

```bash
# Get stations
curl http://localhost:30886/api/stations

# Get data with parameters
curl "http://localhost:30886/api/data?station=Acre&start_date=2025-01-01&end_date=2025-01-31"

# Batch request
curl "http://localhost:30886/api/data/batch?stations=Acre,Yafo,Eilat&start_date=2025-01-01&end_date=2025-01-07"

# Predictions
curl "http://localhost:30886/api/predictions?stations=Acre&model=kalman&forecast_hours=48"

# Outliers (optimized)
curl "http://localhost:30886/api/outliers/optimized?station=Acre&start_date=2025-01-01&end_date=2025-01-31&use_cache=true"

# Health check
curl http://localhost:30886/api/health

# Save response to file
curl -o data.json "http://localhost:30886/api/data?station=Acre&start_date=2025-01-01&end_date=2025-01-31"

# Pretty print JSON (with jq)
curl "http://localhost:30886/api/stations" | jq '.'
```

---

## Changelog

### Version 2.0.0 (Current)

**New Features:**
- Added optimized outliers endpoint with 10-50x performance improvement
- Implemented materialized view caching for frequently accessed data
- Added batch data endpoint for multi-station queries
- Integrated Southern Baseline Rules for anomaly detection
- Added Kalman Filter and Prophet prediction models
- Implemented rolling averages and trendline analytics
- Added IMS weather warnings integration
- Added mariners forecast endpoint

**Performance Improvements:**
- Response compression (GZip)
- Redis caching layer
- Database query optimization
- Connection pooling

**Breaking Changes:**
- None (backward compatible with v1.x)

### Version 1.0.0

**Initial Release:**
- Basic data retrieval endpoints
- Station information
- Simple predictions
- Health check

---

## Support and Resources

### Interactive Documentation

- Swagger UI: `http://localhost:30886/docs`
- ReDoc: `http://localhost:30886/redoc`
- OpenAPI Spec: `http://localhost:30886/openapi.json`

### Additional Documentation

- User Manual: See USER_MANUAL.md
- Developer Guide: See README.md
- JSDoc Examples: See JSDOC_EXAMPLES.md
- Python Docstrings: See PYTHON_DOCSTRINGS_EXAMPLES.md

### Support Channels

- GitHub Issues: [repository-url]/issues
- Email: support@example.com
- Documentation: [docs-url]

---

**End of API Documentation**

*Version: 2.0.0*
*Last Updated: November 2025*
*For user documentation, see USER_MANUAL.md*
