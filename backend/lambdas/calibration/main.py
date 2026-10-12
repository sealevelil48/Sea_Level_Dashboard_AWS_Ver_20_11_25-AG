# backend/lambdas/calibration/main.py
# Three handlers: preview (in-memory), commit (additive UPDATE), suggest (step-detection)
import json
import logging
import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}

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

def _fetch_raw(station, start_datetime, end_datetime):
    """
    Return DataFrame with columns: Tab_DateTime, Station, raw_value.

    start_datetime / end_datetime must be full ISO-8601 timestamps
    (e.g. '2026-10-08T15:13:00') so the comparison is sub-minute precise.
    DATE() is intentionally NOT used here.
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
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
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
    """
    if not DATABASE_AVAILABLE:
        return _err(503, "Database not available")

    body = _parse_body(event)
    station = body.get("station")
    start_dt = body.get("start_datetime")
    end_dt = body.get("end_datetime")
    offset = body.get("offset", 0.0)
    reference_station = body.get("reference_station")

    if not station or not start_dt or not end_dt:
        return _err(400, "station, start_datetime, and end_datetime are required")

    try:
        offset = float(offset)
    except (TypeError, ValueError):
        return _err(400, "offset must be a number")

    try:
        df = _fetch_raw(station, start_dt, end_dt)
        if df.empty:
            return _err(404, f"No data found for {station} in the given range")

        df["corrected_value"] = df["raw_value"] + offset
        df["Tab_DateTime"] = df["Tab_DateTime"].astype(str)

        data_records = df[["Tab_DateTime", "Station", "raw_value", "corrected_value"]].to_dict(orient="records")

        reference_records = []
        if reference_station and reference_station != "none":
            ref_df = _fetch_raw(reference_station, start_dt, end_dt)
            if not ref_df.empty:
                ref_df["Tab_DateTime"] = ref_df["Tab_DateTime"].astype(str)
                ref_df = ref_df.rename(columns={"raw_value": "value"})
                reference_records = ref_df[["Tab_DateTime", "Station", "value"]].to_dict(orient="records")

        return _ok({
            "station": station,
            "offset_applied": offset,
            "start_datetime": start_dt,
            "end_datetime": end_dt,
            "data": data_records,
            "reference_data": reference_records,
        })

    except Exception as e:
        logger.error(f"[ERROR] preview_correction: {e}")
        return _err(500, str(e))


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
    """
    if not DATABASE_AVAILABLE:
        return _err(503, "Database not available")

    body = _parse_body(event)
    station = body.get("station")
    start_dt = body.get("start_datetime")
    end_dt = body.get("end_datetime")
    offset = body.get("offset")

    if not station or not start_dt or not end_dt or offset is None:
        return _err(400, "station, start_datetime, end_datetime, and offset are required")

    try:
        offset = float(offset)
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
                "start_datetime": start_dt,
                "end_datetime": end_dt,
            })
            rows_updated = result.rowcount

        logger.info(f"[OK] Committed offset {offset} for {station} ({rows_updated} rows)")
        return _ok({
            "success": True,
            "station": station,
            "offset_applied": offset,
            "rows_updated": rows_updated,
            "start_datetime": start_dt,
            "end_datetime": end_dt,
        })

    except Exception as e:
        logger.error(f"[ERROR] commit_correction: {e}")
        return _err(500, str(e))


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
    """
    if not DATABASE_AVAILABLE:
        return _err(503, "Database not available")

    body = _parse_body(event)
    station = body.get("station")
    start_dt = body.get("start_datetime")
    end_dt = body.get("end_datetime")

    if not station or not start_dt or not end_dt:
        return _err(400, "station, start_datetime, and end_datetime are required")

    try:
        df = _fetch_raw(station, start_dt, end_dt)
        if df.empty:
            return _err(404, f"No data found for {station} in the given range")

        df["Tab_DateTime"] = pd.to_datetime(df["Tab_DateTime"])
        df = df.set_index("Tab_DateTime")
        hourly = df["raw_value"].resample("1H").median().dropna()

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
        logger.error(f"[ERROR] suggest_correction: {e}")
        return _err(500, str(e))


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
    return _err(404, f"Unknown calibration endpoint: {path}")
