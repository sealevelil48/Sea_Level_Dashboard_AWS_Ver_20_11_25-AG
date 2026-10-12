# backend/lambdas/calibration/main.py
# Three handlers: preview (in-memory), commit (additive UPDATE), suggest (step-detection)
#
# Security controls applied (see inline comments):
#   1. All three endpoints require a correct X-Calibration-Key header.
#   2. station / reference_station are checked against an allowlist.
#   3. start_datetime / end_datetime are validated with datetime.fromisoformat()
#      and must satisfy start < end with a maximum 2-year window.
#   4. Exception details are logged server-side only; clients receive a generic
#      "Internal server error" message.
import json
import logging
import sys
import os
import re
import numpy as np
import pandas as pd
from datetime import datetime, timezone

# Add paths for shared modules (mirrors pattern in get_data/main.py)
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, '..', '..')
sys.path.insert(0, backend_dir)

try:
    from shared.database import engine
    from sqlalchemy import text
    DATABASE_AVAILABLE = True
    print("[OK] Database modules imported successfully for calibration")
except ImportError as e:
    print(f"[ERROR] Database import error in calibration: {e}")
    DATABASE_AVAILABLE = False

try:
    from security import SecurityUtils
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}

# ---------------------------------------------------------------------------
# Security: station allowlist
# The static fallback matches FALLBACK_STATIONS in the frontend.  When the DB
# is available the list is also refreshed at import time from Locations.
# ---------------------------------------------------------------------------
_STATIC_ALLOWED_STATIONS = frozenset({
    "Acre", "Ashdod", "Ashkelon", "Eilat", "Haifa", "Yafo"
})
_ALLOWED_STATIONS = set(_STATIC_ALLOWED_STATIONS)

def _refresh_station_allowlist():
    """Load the full set of station names from the Locations table."""
    if not DATABASE_AVAILABLE or not engine:
        return
    try:
        with engine.connect() as conn:
            result = conn.execute(text('SELECT DISTINCT "Station" FROM "Locations"'))
            names = {row[0] for row in result.fetchall() if row[0]}
            if names:
                _ALLOWED_STATIONS.update(names)
                logger.info(f"[OK] Station allowlist refreshed: {sorted(_ALLOWED_STATIONS)}")
    except Exception as exc:
        logger.warning(f"[WARN] Could not refresh station allowlist: {exc}")

_refresh_station_allowlist()

# Reference stations that may be overlaid for comparison
ALLOWED_REFERENCE_STATIONS = frozenset({"Ashdod", "Ashkelon"})

# Maximum allowed correction window: 2 years
MAX_WINDOW_DAYS = 730

# ---------------------------------------------------------------------------
# Security: API key authentication
# Set CALIBRATION_API_KEY in the environment (or AWS Secrets Manager for prod).
# If the variable is absent the endpoints are locked — no default is accepted.
# ---------------------------------------------------------------------------
_CALIBRATION_API_KEY = os.getenv("CALIBRATION_API_KEY", "")

def _check_auth(event):
    """
    Return None if the request is authenticated, or an error response dict.
    Checks the X-Calibration-Key header (case-insensitive lookup across
    both FastAPI header dict and raw API-Gateway multiValueHeaders).
    """
    if not _CALIBRATION_API_KEY:
        logger.error("[SECURITY] CALIBRATION_API_KEY env var is not set — all calibration requests blocked")
        return _err(503, "Calibration service not configured")

    headers = event.get("headers") or {}
    # FastAPI lowercases header names; API Gateway may not
    key_provided = (
        headers.get("x-calibration-key")
        or headers.get("X-Calibration-Key")
        or headers.get("X-CALIBRATION-KEY")
        or ""
    )
    if not key_provided or key_provided != _CALIBRATION_API_KEY:
        logger.warning("[SECURITY] Calibration request rejected: invalid or missing X-Calibration-Key")
        return _err(401, "Unauthorized")
    return None

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _ok(data):
    return {"statusCode": 200, "headers": CORS_HEADERS, "body": json.dumps(data, default=str)}

def _err(status, msg):
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps({"error": msg})}

def _parse_body(event):
    body = event.get("body", {})
    if isinstance(body, str):
        body = json.loads(body)
    return body or {}

def _validate_station(station):
    """
    Return (cleaned_name, error_response) — error_response is None on success.
    Uses the existing SecurityUtils.validate_station_name pattern from security.py
    and also checks against the server-side allowlist.
    """
    if not isinstance(station, str) or not station.strip():
        return None, _err(400, "station must be a non-empty string")
    station = station.strip()
    if SECURITY_AVAILABLE and not SecurityUtils.validate_station_name(station):
        return None, _err(400, "station contains invalid characters")
    elif not re.match(r'^[a-zA-Z0-9 \-_]+$', station) or len(station) > 50:
        return None, _err(400, "station contains invalid characters")
    if station not in _ALLOWED_STATIONS:
        return None, _err(400, f"Unknown station: '{station}'")
    return station, None

def _validate_datetime(dt_str, field_name):
    """
    Return (datetime_object, error_response).
    Accepts ISO-8601 strings (with or without seconds).
    """
    if not isinstance(dt_str, str) or not dt_str.strip():
        return None, _err(400, f"{field_name} must be a non-empty string")
    try:
        # datetime-local inputs produce "YYYY-MM-DDTHH:MM" (no seconds); fromisoformat handles both
        dt = datetime.fromisoformat(dt_str.strip())
    except ValueError:
        return None, _err(400, f"{field_name} must be a valid ISO-8601 datetime (e.g. 2026-10-08T15:13:00)")
    # Sanity check: reasonable year range
    if dt.year < 2000 or dt.year > 2100:
        return None, _err(400, f"{field_name} year must be between 2000 and 2100")
    return dt, None

def _validate_window(start_dt, end_dt):
    """Ensure start < end and window <= MAX_WINDOW_DAYS."""
    if start_dt >= end_dt:
        return _err(400, "start_datetime must be earlier than end_datetime")
    delta = end_dt - start_dt
    if delta.days > MAX_WINDOW_DAYS:
        return _err(400, f"Correction window cannot exceed {MAX_WINDOW_DAYS} days")
    return None

def _fetch_raw(station, start_datetime, end_datetime):
    """
    Return DataFrame with columns: Tab_DateTime, Station, raw_value.
    station has already been validated; start/end are datetime objects
    converted to ISO strings for the SQL bind parameter.
    """
    sql = text("""
        SELECT
            m."Tab_DateTime",
            l."Station",
            CAST(m."Tab_Value_mDepthC1" AS FLOAT) AS raw_value
        FROM "Monitors_info2" m
        JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
        WHERE l."Station" = :station
          AND m."Tab_DateTime" >= :start_datetime
          AND m."Tab_DateTime" <= :end_datetime
        ORDER BY m."Tab_DateTime" ASC
    """)
    with engine.connect() as conn:
        result = conn.execute(sql, {
            "station": station,
            "start_datetime": start_datetime.isoformat(),
            "end_datetime": end_datetime.isoformat(),
        })
        rows = result.fetchall()
        cols = list(result.keys())
    return pd.DataFrame(rows, columns=cols)

# ---------------------------------------------------------------------------
# Handler: Preview (in-memory, no DB writes)
# ---------------------------------------------------------------------------

def lambda_handler_preview(event, context):
    """
    Apply a proposed offset in-memory and return the preview data.
    Optionally fetch a reference station for side-by-side comparison.

    Request body: {
        station: str,
        start_datetime: str,   # ISO-8601, e.g. "2026-10-08T15:13:00"
        end_datetime: str,
        offset: float,
        reference_station?: str   # 'Ashdod' | 'Ashkelon' | omit
    }
    Headers: X-Calibration-Key: <key>
    """
    auth_err = _check_auth(event)
    if auth_err:
        return auth_err

    if not DATABASE_AVAILABLE:
        return _err(503, "Database not available")

    body = _parse_body(event)

    station, err = _validate_station(body.get("station"))
    if err:
        return err

    start_dt, err = _validate_datetime(body.get("start_datetime"), "start_datetime")
    if err:
        return err
    end_dt, err = _validate_datetime(body.get("end_datetime"), "end_datetime")
    if err:
        return err

    err = _validate_window(start_dt, end_dt)
    if err:
        return err

    reference_station_raw = body.get("reference_station")
    reference_station = None
    if reference_station_raw and reference_station_raw != "none":
        if reference_station_raw not in ALLOWED_REFERENCE_STATIONS:
            return _err(400, f"reference_station must be one of: {sorted(ALLOWED_REFERENCE_STATIONS)}")
        reference_station = reference_station_raw

    try:
        offset = float(body.get("offset", 0.0))
    except (TypeError, ValueError):
        return _err(400, "offset must be a number")
    if not np.isfinite(offset):
        return _err(400, "offset must be a finite number")

    try:
        df = _fetch_raw(station, start_dt, end_dt)
        if df.empty:
            return _err(404, "No data found for the specified station and time window")

        df["corrected_value"] = df["raw_value"] + offset
        df["Tab_DateTime"] = df["Tab_DateTime"].astype(str)
        data_records = df[["Tab_DateTime", "Station", "raw_value", "corrected_value"]].to_dict(orient="records")

        reference_records = []
        if reference_station:
            ref_df = _fetch_raw(reference_station, start_dt, end_dt)
            if not ref_df.empty:
                ref_df["Tab_DateTime"] = ref_df["Tab_DateTime"].astype(str)
                ref_df = ref_df.rename(columns={"raw_value": "value"})
                reference_records = ref_df[["Tab_DateTime", "Station", "value"]].to_dict(orient="records")

        return _ok({
            "station": station,
            "offset_applied": offset,
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
            "data": data_records,
            "reference_data": reference_records,
        })

    except Exception as e:
        logger.error(f"[ERROR] preview_correction: {e}", exc_info=True)
        return _err(500, "Internal server error")


# ---------------------------------------------------------------------------
# Handler: Commit (additive UPDATE, exact timestamp bounds)
# ---------------------------------------------------------------------------

def lambda_handler_commit(event, context):
    """
    Persist the calibration offset to the database.
    Uses COALESCE + additive increment so multiple corrections compound safely.
    Uses exact timestamp bounds — no DATE() truncation.

    Request body: {
        station: str,
        start_datetime: str,
        end_datetime: str,
        offset: float
    }
    Headers: X-Calibration-Key: <key>
    """
    auth_err = _check_auth(event)
    if auth_err:
        return auth_err

    if not DATABASE_AVAILABLE:
        return _err(503, "Database not available")

    body = _parse_body(event)

    station, err = _validate_station(body.get("station"))
    if err:
        return err

    start_dt, err = _validate_datetime(body.get("start_datetime"), "start_datetime")
    if err:
        return err
    end_dt, err = _validate_datetime(body.get("end_datetime"), "end_datetime")
    if err:
        return err

    err = _validate_window(start_dt, end_dt)
    if err:
        return err

    offset_raw = body.get("offset")
    if offset_raw is None:
        return _err(400, "offset is required")
    try:
        offset = float(offset_raw)
    except (TypeError, ValueError):
        return _err(400, "offset must be a number")
    if not np.isfinite(offset):
        return _err(400, "offset must be a finite number")
    if abs(offset) > 10.0:
        return _err(400, "offset magnitude must be <= 10.0 metres")

    # Additive UPDATE: accumulates corrections, never overwrites prior ones.
    # Direct timestamp comparison — no DATE() cast — preserves sub-minute precision.
    update_sql = text("""
        UPDATE "Monitors_info2" AS m
        SET "Calibration_Offset" = COALESCE("Calibration_Offset", 0) + :offset
        FROM "Locations" AS l
        WHERE m."Tab_TabularTag" = l."Tab_TabularTag"
          AND l."Station" = :station
          AND m."Tab_DateTime" >= :start_datetime
          AND m."Tab_DateTime" <= :end_datetime
    """)

    try:
        with engine.begin() as conn:
            result = conn.execute(update_sql, {
                "offset": offset,
                "station": station,
                "start_datetime": start_dt.isoformat(),
                "end_datetime": end_dt.isoformat(),
            })
            rows_updated = result.rowcount

        logger.info(f"[OK] Committed offset {offset} for {station} ({rows_updated} rows)")
        return _ok({
            "success": True,
            "station": station,
            "offset_applied": offset,
            "rows_updated": rows_updated,
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
        })

    except Exception as e:
        logger.error(f"[ERROR] commit_correction: {e}", exc_info=True)
        return _err(500, "Internal server error")


# ---------------------------------------------------------------------------
# Handler: Suggest (step-detection on hourly medians)
# ---------------------------------------------------------------------------

def lambda_handler_suggest(event, context):
    """
    Detect the largest single-step shift in the data and suggest the corrective offset.

    Request body: {
        station: str,
        start_datetime: str,
        end_datetime: str
    }
    Headers: X-Calibration-Key: <key>
    """
    auth_err = _check_auth(event)
    if auth_err:
        return auth_err

    if not DATABASE_AVAILABLE:
        return _err(503, "Database not available")

    body = _parse_body(event)

    station, err = _validate_station(body.get("station"))
    if err:
        return err

    start_dt, err = _validate_datetime(body.get("start_datetime"), "start_datetime")
    if err:
        return err
    end_dt, err = _validate_datetime(body.get("end_datetime"), "end_datetime")
    if err:
        return err

    err = _validate_window(start_dt, end_dt)
    if err:
        return err

    try:
        df = _fetch_raw(station, start_dt, end_dt)
        if df.empty:
            return _err(404, "No data found for the specified station and time window")

        df["Tab_DateTime"] = pd.to_datetime(df["Tab_DateTime"])
        df = df.set_index("Tab_DateTime")
        hourly = df["raw_value"].resample("1h").median().dropna()

        if len(hourly) < 2:
            return _err(422, "Not enough data to detect a step shift (need at least 2 hours)")

        diffs = hourly.diff().dropna()
        max_shift_idx = diffs.abs().idxmax()
        max_shift_val = float(diffs[max_shift_idx])
        suggested_offset = round(-max_shift_val, 4)
        confidence = "high" if abs(max_shift_val) > 0.05 else "low"

        return _ok({
            "station": station,
            "suggested_offset": suggested_offset,
            "confidence": confidence,
            "shift_detected_at": str(max_shift_idx),
            "method": "step_detection",
        })

    except Exception as e:
        logger.error(f"[ERROR] suggest_correction: {e}", exc_info=True)
        return _err(500, "Internal server error")


# ---------------------------------------------------------------------------
# Default entry point (for AWS Lambda compatibility)
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    """Route to the correct sub-handler based on the path."""
    path = event.get("path", "")
    if "preview" in path:
        return lambda_handler_preview(event, context)
    if "commit" in path:
        return lambda_handler_commit(event, context)
    if "suggest" in path:
        return lambda_handler_suggest(event, context)
    return _err(404, "Unknown calibration endpoint")
