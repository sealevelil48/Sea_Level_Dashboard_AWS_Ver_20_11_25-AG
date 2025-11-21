# Sea Level Dashboard — Public API Documentation (Client)

This document is a client-facing reference you can display on your website. It describes the public HTTP API exposed by the Sea Level Dashboard backend (`backend/local_server.py`). The API is REST-style and returns JSON.

Base URL
- For local dev: `http://localhost:30886` (default `BACKEND_PORT=30886`)
- Production: use your deployed domain (e.g. `https://api.yourdomain.com`).

Authentication
- The current server does not enforce authentication in the main routes by default. If your production deployment requires auth, add it to the gateway or proxy layer and update clients accordingly.

OpenAPI / Interactive Docs
- The backend exposes interactive API docs at: `GET /docs` (served by FastAPI).

Common Notes & Conventions
- Dates: use `YYYY-MM-DD`. If `start_date` or `end_date` are omitted some endpoints default to the last 7 days.
- Max date range: endpoints reject ranges > 365 days.
- Limits: `GET /api/data` default `limit=15000`. Batch/outlier endpoints limit processing (outliers often cap at 5000 rows for performance).
- Responses: JSON objects or arrays. On error the API returns a JSON body with `error` and an appropriate HTTP status code.

Endpoints (summary + examples)

- **GET /api/health**
  - Purpose: Get server health, DB/cache status and metrics.
  - Example:
    ```bash
    curl -s http://localhost:30886/api/health
    ```

- **GET /api/stations**
  - Purpose: List available monitoring stations.
  - Example:
    ```bash
    curl -s http://localhost:30886/api/stations
    ```

- **GET /api/data**
  - Purpose: Retrieve time-series data for a station or all stations.
  - Query parameters:
    - `station` (string) — station name or `All Stations` (default)
    - `start_date` (YYYY-MM-DD) — optional, default = 7 days ago
    - `end_date` (YYYY-MM-DD) — optional, default = today
    - `data_source` (string) — optional
    - `limit` (int) — maximum rows (default 15000)
  - Validation: rejects invalid date formats and ranges > 365 days.
  - Example:
    ```bash
    curl -s "http://localhost:30886/api/data?station=Haifa&start_date=2025-11-10&end_date=2025-11-17&limit=2000"
    ```
  - Notes: API adds headers `X-Response-Time` and `X-Cache` to indicate performance.

- **GET /api/data/batch**
  - Purpose: Batch query multiple stations in a single call.
  - Query parameters: `stations` (comma-separated names), `start_date`, `end_date`, `data_source`, `show_anomalies`.
  - Example:
    ```bash
    curl -s "http://localhost:30886/api/data/batch?stations=Haifa,Yafo&start_date=2025-11-01&end_date=2025-11-07"
    ```

- **GET /api/live-data**
  - Purpose: Get the latest reading(s) for a station or all stations.
  - Query parameters: `station` optional.
  - Example:
    ```bash
    curl -s "http://localhost:30886/api/live-data?station=Haifa"
    ```

- **GET /api/predictions**
  - Purpose: Retrieve predictions (e.g., Kalman/ARIMA) for one or more stations.
  - Query parameters: `stations` or `station` (required), `model` (default `kalman`), `steps` (default 240) or `forecast_hours`.
  - Example:
    ```bash
    curl -s "http://localhost:30886/api/predictions?station=Haifa&model=kalman&steps=240"
    ```

- **GET /api/sea-forecast**
  - Purpose: Get sea/wave forecast (IMS integration).
  - Example:
    ```bash
    curl -s http://localhost:30886/api/sea-forecast
    ```

- **GET /api/ims-warnings**
  - Purpose: IMS weather warnings.

- **GET /api/mariners-forecast** and **/api/mariners-forecast-direct**
  - Purpose: Fetch and parse IMS XML mariners forecast. The server attempts several Hebrew encodings (`windows-1255`, `iso-8859-8`, `utf-8`) to decode returned XML robustly.

- **GET /api/outliers**
  - Purpose: Run outlier detection (uses baseline rules). Requires baseline integration to be available.
  - Query parameters: `start_date`, `end_date`, `station` (default `All Stations`).
  - Notes: Server caps processing to avoid long runs; large results are trimmed to recent 5000 records.

- **GET /api/corrections**
  - Purpose: Return correction suggestions for detected outliers (baseline rules). Loads all stations' data before computing corrections.

- **GET /api/validation_report**
  - Purpose: Return comprehensive validation report computed by `BaselineIntegratedProcessor`.

- **GET /api/stations/map**
  - Purpose: Stations with coordinates for map display.

Response Formats & Error Codes
- Success responses return `200` (or `2xx`) and JSON content.
- Common error codes:
  - `400` — Bad request (invalid date format, missing required param)
  - `404` — Not found (e.g., station not found)
  - `408` — Processing timeout (e.g., outlier detection on too-large dataset)
  - `500` — Internal server error

Example JavaScript (fetch)
```js
// Simple fetch example - replace baseUrl with your deployed API
const baseUrl = 'http://localhost:30886';
async function getStationData(station, start, end) {
  const q = new URLSearchParams({ station, start_date: start, end_date: end });
  const r = await fetch(`${baseUrl}/api/data?${q}`);
  if (!r.ok) throw new Error('API error: ' + r.status);
  return r.json();
}

getStationData('Haifa','2025-11-10','2025-11-17').then(data => console.log(data)).catch(console.error);
```

Deployment & CORS
- FastAPI's CORS origins are configured via `CORS_ORIGINS` env var or `.env`. For public usage whitelist your website origin(s).

Rate Limits & SLAs
- The server does not implement a built-in rate limiter. For public clients, place the API behind a gateway (e.g., API Management, CloudFront + WAF, Nginx) and enforce rate limits, API keys, and monitoring.

Security Considerations
- Sanitize inputs on the client and server. The project includes `backend/security.py` with helpers used by the server.
- Avoid exposing the DB credentials in public docs. Use a gateway or proxy for authentication, logging, and IP restrictions in production.

How to link this in your website
- Option 1: Provide a direct link to the interactive docs at `https://yourdomain.com/docs`.
- Option 2: Embed a static HTML page (this file converted to HTML) in a developer section.

Questions / Next steps
- I can:
  - Convert this file to HTML and add it to `frontend/public/` or `frontend/src/pages/`.
  - Extract live examples from a specific lambda (e.g., `get_data`) and add sample responses.
  - Add a short OpenAPI-derived JSON snippet for automatic API explorers.

Tell me which next step you prefer and I will apply it.
