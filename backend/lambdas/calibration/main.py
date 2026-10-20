# backend/lambdas/calibration/main.py
# Three handlers: preview (in-memory), commit (SQL-based), suggest (12-hour stable windows)
#
# Phase 2 Features:
#   - lambda_handler_preview: Both offset and interpolate modes (in-memory)
#   - lambda_handler_commit: SQL-based interpolation + offset mode (database UPDATE)
#   - lambda_handler_suggest: 12-hour stable window algorithm (before/after medians)
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
from datetime import datetime, timezone, timedelta

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
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

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
#
# The static set is the sole authoritative list — it matches FALLBACK_STATIONS
# in the frontend and is never overwritten.
#
# The DB refresh (opt-in, controlled by CALIBRATION_ALLOW_DB_STATIONS=true)
# may ADD stations, but only after each candidate passes the same format regex
# used in _validate_station.  Any name that fails the regex is discarded and
# logged as an anomaly.  The total set is capped at _MAX_STATION_COUNT.
# ---------------------------------------------------------------------------
_STATION_NAME_RE = re.compile(r'^[a-zA-Z0-9 \-_]+$')
_MAX_STATION_COUNT = 50

_STATIC_ALLOWED_STATIONS = frozenset({
    "Acre", "Ashdod", "Ashkelon", "Eilat", "Haifa", "Yafo"
})
_ALLOWED_STATIONS = set(_STATIC_ALLOWED_STATIONS)

def _refresh_station_allowlist():
    """
    Optionally expand the allowlist from the Locations table.
    Only runs when CALIBRATION_ALLOW_DB_STATIONS=true is set explicitly.
    Each candidate name is validated against _STATION_NAME_RE before
    being admitted; rejects are logged as anomalies.
    """
    if os.getenv("CALIBRATION_ALLOW_DB_STATIONS", "false").lower() != "true":
        return
    if not DATABASE_AVAILABLE or not engine:
        return
    try:
        with engine.connect() as conn:
            result = conn.execute(text('SELECT DISTINCT "Station" FROM "Locations"'))
            raw_names = {row[0] for row in result.fetchall() if row[0]}

        admitted, rejected = [], []
        for name in raw_names:
            if (
                isinstance(name, str)
                and _STATION_NAME_RE.match(name)
                and len(name) <= 50
            ):
                admitted.append(name)
            else:
                rejected.append(name)

        if rejected:
            # Sanitize before logging: repr() escapes control chars/newlines;
            # truncate each name and cap the list to prevent log flooding.
            safe_rejected = [repr(n)[:80] for n in list(rejected)[:20]]
            logger.warning(
                "[SECURITY] DB station allowlist: rejected %d name(s) that failed "
                "format check: %s",
                len(rejected), safe_rejected
            )

        new_stations = set(admitted) - _STATIC_ALLOWED_STATIONS
        if new_stations:
            safe_new = [repr(n)[:80] for n in sorted(new_stations)[:20]]
            logger.warning(
                "[SECURITY] DB station allowlist: adding %d name(s) beyond the static "
                "set (review these): %s",
                len(new_stations), safe_new
            )

        candidate_set = _STATIC_ALLOWED_STATIONS | set(admitted)
        if len(candidate_set) > _MAX_STATION_COUNT:
            logger.error(
                f"[SECURITY] DB station allowlist exceeds cap ({_MAX_STATION_COUNT}); "
                "using static list only"
            )
            return

        _ALLOWED_STATIONS.update(set(admitted))
        logger.info(f"[OK] Station allowlist refreshed: {sorted(_ALLOWED_STATIONS)}")

    except Exception as exc:
        logger.warning(f"[WARN] Could not refresh station allowlist: {exc}")

_refresh_station_allowlist()

# Reference stations that may be overlaid for comparison
ALLOWED_REFERENCE_STATIONS = _ALLOWED_STATIONS

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
    """
    Ensure start < end and window <= MAX_WINDOW_DAYS.
    Uses timedelta comparison directly (not delta.days) to avoid the
    sub-day truncation bug where timedelta(730 days, 1 hour).days == 730.
    """
    if start_dt >= end_dt:
        return _err(400, "start_datetime must be earlier than end_datetime")
    if (end_dt - start_dt) > timedelta(days=MAX_WINDOW_DAYS):
        return _err(400, f"Correction window cannot exceed {MAX_WINDOW_DAYS} days")
    return None

def _validate_correction_type(correction_type):
    """
    Return (correction_type, error_response).
    Validates that correction_type is either 'offset', 'interpolate', or 'relative'.
    """
    if not correction_type:
        correction_type = 'offset'  # Default
    if correction_type not in ('offset', 'interpolate', 'relative'):
        return None, _err(400, "correction_type must be 'offset', 'interpolate', or 'relative'")
    return correction_type, None

def _fetch_raw(station, start_datetime, end_datetime):
    """
    Return DataFrame with columns: Tab_DateTime, Station, raw_value, effective_value.
    station has already been validated; start/end are datetime objects
    converted to ISO strings for the SQL bind parameter.
    effective_value = raw_value + existing calibration offset (for seamless interpolation)
    """
    sql = text("""
        SELECT
            m."Tab_DateTime",
            l."Station",
            CAST(m."Tab_Value_mDepthC1" AS FLOAT) AS raw_value,
            (CAST(m."Tab_Value_mDepthC1" AS FLOAT) + COALESCE(CAST(m."Calibration_Offset" AS FLOAT), 0)) AS effective_value
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

def _fetch_interpolation_boundaries(station, start_dt, end_dt):
    """
    Fetch the effective values at the boundaries of the correction window.
    Returns the first data point before/at start_dt and the last data point before/at end_dt.
    Uses effective_value (raw + existing offset) so interpolation seamlessly connects the visible lines.
    Raises exception if boundaries not found.
    """
    sql = text("""
        SELECT
            (CAST(m."Tab_Value_mDepthC1" AS FLOAT) + COALESCE(CAST(m."Calibration_Offset" AS FLOAT), 0)) AS effective_value,
            m."Tab_DateTime",
            'start' AS boundary
        FROM "Monitors_info2" m
        JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
        WHERE l."Station" = :station
          AND m."Tab_DateTime" <= :start_dt
        ORDER BY m."Tab_DateTime" DESC
        LIMIT 1

        UNION ALL

        SELECT
            (CAST(m."Tab_Value_mDepthC1" AS FLOAT) + COALESCE(CAST(m."Calibration_Offset" AS FLOAT), 0)) AS effective_value,
            m."Tab_DateTime",
            'end' AS boundary
        FROM "Monitors_info2" m
        JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
        WHERE l."Station" = :station
          AND m."Tab_DateTime" >= :end_dt
        ORDER BY m."Tab_DateTime" ASC
        LIMIT 1
    """)
    with engine.connect() as conn:
        result = conn.execute(sql, {
            "station": station,
            "start_dt": start_dt.isoformat(),
            "end_dt": end_dt.isoformat(),
        })
        rows = result.fetchall()

    start_val = None
    end_val = None
    for row in rows:
        if row[2] == 'start':
            start_val = float(row[0])
        elif row[2] == 'end':
            end_val = float(row[0])

    if start_val is None or end_val is None:
        raise ValueError("Cannot find data at correction window boundaries")

    return start_val, end_val

def _fetch_stable_window_data(station, start_dt, end_dt, hours_before=12, hours_after=12):
    """
    Fetch data for three windows: before, correction, and after.
    Used by suggest handler to compute medians and IQR.
    Returns: (before_data, after_data) as Series of raw_value
    """
    before_start = start_dt - timedelta(hours=hours_before)
    after_end = end_dt + timedelta(hours=hours_after)

    # Fetch before window: [before_start, start_dt)
    sql_before = text("""
        SELECT CAST(m."Tab_Value_mDepthC1" AS FLOAT) AS raw_value
        FROM "Monitors_info2" m
        JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
        WHERE l."Station" = :station
          AND m."Tab_DateTime" >= :before_start
          AND m."Tab_DateTime" < :start_dt
        ORDER BY m."Tab_DateTime" ASC
    """)

    # Fetch after window: (end_dt, after_end]
    sql_after = text("""
        SELECT CAST(m."Tab_Value_mDepthC1" AS FLOAT) AS raw_value
        FROM "Monitors_info2" m
        JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
        WHERE l."Station" = :station
          AND m."Tab_DateTime" > :end_dt
          AND m."Tab_DateTime" <= :after_end
        ORDER BY m."Tab_DateTime" ASC
    """)

    with engine.connect() as conn:
        before_result = conn.execute(sql_before, {
            "station": station,
            "before_start": before_start.isoformat(),
            "start_dt": start_dt.isoformat(),
        })
        before_rows = [float(row[0]) for row in before_result.fetchall()]

        after_result = conn.execute(sql_after, {
            "station": station,
            "end_dt": end_dt.isoformat(),
            "after_end": after_end.isoformat(),
        })
        after_rows = [float(row[0]) for row in after_result.fetchall()]

    before_series = pd.Series(before_rows) if before_rows else pd.Series(dtype=float)
    after_series = pd.Series(after_rows) if after_rows else pd.Series(dtype=float)

    return before_series, after_series

def _calculate_window_stats(data_series):
    """
    Calculate median and interquartile range (IQR) for a data window.
    Returns: (median, iqr) — IQR measures consistency/stability.
    """
    if data_series.empty:
        return None, None

    median = data_series.median()
    q1 = data_series.quantile(0.25)
    q3 = data_series.quantile(0.75)
    iqr = q3 - q1

    return median, iqr

def _invalidate_redis_cache():
    """
    Flush Redis cache to force fresh data query on next request.
    Allows dashboard to immediately reflect calibration corrections.
    """
    if not REDIS_AVAILABLE:
        logger.warning("[WARN] Redis not available - cache invalidation skipped")
        return

    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url, decode_responses=True)

        # Get all keys matching the data cache pattern
        # The pattern depends on apiService.js getCacheKey() format
        keys = r.keys("*data*") + r.keys("*stations*") + r.keys("*/api/*")

        if keys:
            deleted_count = r.delete(*keys)
            logger.info(f"[OK] Redis cache invalidated: {deleted_count} keys deleted")
        else:
            logger.info("[OK] Redis cache already empty")

        r.close()
    except Exception as e:
        logger.warning(f"[WARN] Could not invalidate Redis cache: {e}")

# ---------------------------------------------------------------------------
# Handler: Preview (in-memory, no DB writes)
# ---------------------------------------------------------------------------

def lambda_handler_preview(event, context):
    """
    Apply a proposed correction in-memory and return the preview data.
    Supports two modes: vertical offset or linear interpolation (snip).
    Optionally fetch a reference station for side-by-side comparison.

    Request body: {
        station: str,
        start_datetime: str,   # ISO-8601, e.g. "2026-10-08T15:13:00"
        end_datetime: str,
        correction_type: str,  # 'offset' (default) or 'interpolate'
        offset: float,         # Used only for 'offset' mode
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

    correction_type, err = _validate_correction_type(body.get("correction_type", "offset"))
    if err:
        return err

    reference_station_raw = body.get("reference_station")
    reference_station = None
    if reference_station_raw and reference_station_raw != "none":
        if reference_station_raw not in ALLOWED_REFERENCE_STATIONS:
            return _err(400, f"reference_station must be one of: {sorted(ALLOWED_REFERENCE_STATIONS)}")
        reference_station = reference_station_raw

    try:
        df = _fetch_raw(station, start_dt, end_dt)
        if df.empty:
            return _err(404, "No data found for the specified station and time window")

        # Apply correction based on type
        if correction_type == 'offset':
            try:
                offset = float(body.get("offset", 0.0))
            except (TypeError, ValueError):
                return _err(400, "offset must be a number")
            if not np.isfinite(offset):
                return _err(400, "offset must be a finite number")
            df["corrected_value"] = df["raw_value"] + offset

        elif correction_type == 'interpolate':
            # Linear interpolation: connect start and end values
            df_sorted = df.sort_values('Tab_DateTime')
            df_sorted['Tab_DateTime'] = pd.to_datetime(df_sorted['Tab_DateTime'])

            # Get start and end effective values (raw + existing offset)
            # This ensures interpolation seamlessly connects the currently visible lines
            start_rows = df_sorted[df_sorted['Tab_DateTime'] <= start_dt]
            end_rows = df_sorted[df_sorted['Tab_DateTime'] >= end_dt]

            if start_rows.empty or end_rows.empty:
                return _err(422, "Cannot interpolate: missing start or end data points")

            start_val = float(start_rows.iloc[-1]['effective_value'])
            end_val = float(end_rows.iloc[0]['effective_value'])

            # Calculate interpolation line
            time_delta = (end_dt - start_dt).total_seconds()
            value_delta = end_val - start_val

            def interpolate(row):
                # For rows strictly within the correction window (between start_dt and end_dt),
                # replace with interpolated value (straight line from start to end)
                # For rows outside the window, keep the effective value
                if row['Tab_DateTime'] > start_dt and row['Tab_DateTime'] < end_dt:
                    elapsed = (row['Tab_DateTime'] - start_dt).total_seconds()
                    return start_val + (elapsed / time_delta) * value_delta
                else:
                    return row['effective_value']

            df_sorted['Tab_DateTime'] = pd.to_datetime(df_sorted['Tab_DateTime'])
            df_sorted['corrected_value'] = df_sorted.apply(interpolate, axis=1)
            df = df_sorted

        elif correction_type == 'relative':
            if not reference_station:
                return _err(400, "relative mode requires reference_station")

            try:
                expected_gap = float(body.get("expected_gap", 0.0))
            except (TypeError, ValueError):
                return _err(400, "expected_gap must be a number")
            if not np.isfinite(expected_gap):
                return _err(400, "expected_gap must be finite")

            ref_df = _fetch_raw(reference_station, start_dt, end_dt)
            if ref_df.empty:
                return _err(404, f"No reference data for {reference_station} in window")

            df_sorted = df.sort_values('Tab_DateTime')
            df_merged = df_sorted.merge(
                ref_df[['Tab_DateTime', 'effective_value']].rename(columns={'effective_value': 'ref_effective'}),
                on='Tab_DateTime',
                how='inner'
            )

            df_merged['offset_needed'] = (df_merged['ref_effective'] + expected_gap) - df_merged['raw_value']
            df_merged['corrected_value'] = df_merged['ref_effective'] + expected_gap

            df = df_sorted.copy()
            for idx, row in df_merged.iterrows():
                df.loc[df['Tab_DateTime'] == row['Tab_DateTime'], 'corrected_value'] = row['corrected_value']
            df['corrected_value'].fillna(df['effective_value'], inplace=True)

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
            "correction_type": correction_type,
            "offset_applied": float(body.get("offset", 0.0)) if correction_type == 'offset' else None,
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
            "data": data_records,
            "reference_data": reference_records,
        })

    except Exception as e:
        logger.error(f"[ERROR] preview_correction: {e}", exc_info=True)
        return _err(500, "Internal server error")


# ---------------------------------------------------------------------------
# Handler: Commit (SQL-based UPDATE, supports both offset and interpolate)
# ---------------------------------------------------------------------------

def lambda_handler_commit(event, context):
    """
    Persist the calibration correction to the database.
    Supports two modes:
      - 'offset': Additive vertical shift (COALESCE + increment)
      - 'interpolate': SQL-based linear interpolation (calculates per-row offset)

    Request body: {
        station: str,
        start_datetime: str,
        end_datetime: str,
        correction_type: str,  # 'offset' or 'interpolate'
        offset: float          # Used only for 'offset' mode
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

    correction_type, err = _validate_correction_type(body.get("correction_type", "offset"))
    if err:
        return err

    reference_station_raw = body.get("reference_station")
    reference_station = None
    if reference_station_raw and reference_station_raw != "none":
        if reference_station_raw not in ALLOWED_REFERENCE_STATIONS:
            return _err(400, f"reference_station must be one of: {sorted(ALLOWED_REFERENCE_STATIONS)}")
        reference_station = reference_station_raw

    try:
        # --- Offset Mode ---
        if correction_type == 'offset':
            offset_raw = body.get("offset")
            if offset_raw is None:
                return _err(400, "offset is required for offset mode")
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

            with engine.begin() as conn:
                result = conn.execute(update_sql, {
                    "offset": offset,
                    "station": station,
                    "start_datetime": start_dt.isoformat(),
                    "end_datetime": end_dt.isoformat(),
                })
                rows_updated = result.rowcount

            logger.info(f"[OK] Committed offset correction for {station} ({rows_updated} rows)")

            # Invalidate Redis cache so dashboard fetches fresh corrected data immediately
            _invalidate_redis_cache()

            return _ok({
                "success": True,
                "station": station,
                "correction_type": "offset",
                "offset_applied": offset,
                "rows_updated": rows_updated,
                "start_datetime": start_dt.isoformat(),
                "end_datetime": end_dt.isoformat(),
            })

        # --- Interpolate Mode ---
        elif correction_type == 'interpolate':
            # Fetch boundary values: value at start_dt and value at end_dt
            start_val, end_val = _fetch_interpolation_boundaries(station, start_dt, end_dt)

            # Calculate time and value deltas
            total_seconds = (end_dt - start_dt).total_seconds()
            value_delta = end_val - start_val

            # PostgreSQL UPDATE with interpolation formula:
            # The offset at each point is: interpolated_value - raw_value
            # where interpolated_value = start_val + (elapsed_time / total_time) * value_delta
            interpolate_sql = text("""
                UPDATE "Monitors_info2" AS m
                SET "Calibration_Offset" =
                    ( :start_val + (EXTRACT(EPOCH FROM (m."Tab_DateTime" - :start_dt)) / :total_seconds) * :value_delta )
                    - CAST(m."Tab_Value_mDepthC1" AS FLOAT)
                FROM "Locations" AS l
                WHERE m."Tab_TabularTag" = l."Tab_TabularTag"
                  AND l."Station" = :station
                  AND m."Tab_DateTime" >= :start_dt
                  AND m."Tab_DateTime" <= :end_dt
            """)

            with engine.begin() as conn:
                result = conn.execute(interpolate_sql, {
                    "start_val": start_val,
                    "end_dt": end_dt.isoformat(),
                    "start_dt": start_dt.isoformat(),
                    "total_seconds": total_seconds,
                    "value_delta": value_delta,
                    "station": station,
                })
                rows_updated = result.rowcount

            logger.info(
                f"[OK] Committed interpolation for {station} ({rows_updated} rows)"
            )

            # Invalidate Redis cache
            _invalidate_redis_cache()

            return _ok({
                "success": True,
                "station": station,
                "correction_type": "interpolate",
                "start_value": start_val,
                "end_value": end_val,
                "rows_updated": rows_updated,
                "start_datetime": start_dt.isoformat(),
                "end_datetime": end_dt.isoformat(),
            })

        # --- Relative Mode ---
        elif correction_type == 'relative':
            if not reference_station:
                return _err(400, "relative mode requires reference_station")

            try:
                expected_gap = float(body.get("expected_gap", 0.0))
            except (TypeError, ValueError):
                return _err(400, "expected_gap must be a number")
            if not np.isfinite(expected_gap):
                return _err(400, "expected_gap must be finite")

            relative_sql = text(f"""
                UPDATE "Monitors_info2" AS target_m
                SET "Calibration_Offset" = (
                    (CAST(ref_m."Tab_Value_mDepthC1" AS FLOAT) + COALESCE(CAST(ref_m."Calibration_Offset" AS FLOAT), 0) + :expected_gap)
                    - CAST(target_m."Tab_Value_mDepthC1" AS FLOAT)
                )
                FROM "Monitors_info2" AS ref_m
                JOIN "Locations" AS target_l ON target_m."Tab_TabularTag" = target_l."Tab_TabularTag"
                JOIN "Locations" AS ref_l ON ref_m."Tab_TabularTag" = ref_l."Tab_TabularTag"
                WHERE target_l."Station" = :station
                  AND ref_l."Station" = :reference_station
                  AND target_m."Tab_DateTime" = ref_m."Tab_DateTime"
                  AND target_m."Tab_DateTime" >= :start_dt
                  AND target_m."Tab_DateTime" <= :end_dt
            """)

            with engine.begin() as conn:
                result = conn.execute(relative_sql, {
                    "station": station,
                    "reference_station": reference_station,
                    "start_dt": start_dt.isoformat(),
                    "end_dt": end_dt.isoformat(),
                    "expected_gap": expected_gap,
                })
                rows_updated = result.rowcount

            logger.info(f"[OK] Committed relative calibration for {station} vs {reference_station}")
            _invalidate_redis_cache()

            return _ok({
                "success": True,
                "station": station,
                "correction_type": "relative",
                "reference_station": reference_station,
                "expected_gap": expected_gap,
                "rows_updated": rows_updated,
                "start_datetime": start_dt.isoformat(),
                "end_datetime": end_dt.isoformat(),
            })

    except ValueError as ve:
        logger.error(f"[ERROR] commit_correction validation: {ve}")
        return _err(422, str(ve))
    except Exception as e:
        logger.error(f"[ERROR] commit_correction: {e}", exc_info=True)
        return _err(500, "Internal server error")


# ---------------------------------------------------------------------------
# Handler: Suggest (12-hour stable window algorithm)
# ---------------------------------------------------------------------------

def lambda_handler_suggest(event, context):
    """
    Detect calibration offset using 12-hour stable window algorithm.

    Algorithm:
      1. Fetch 12 hours BEFORE start_datetime (before_window)
      2. Fetch 12 hours AFTER end_datetime (after_window)
      3. Calculate median of each window, ignore data between (spike area)
      4. Suggested offset = before_median - after_median
      5. Confidence based on IQR consistency of each window

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
        reference_station_raw = body.get("reference_station")
        reference_station = None
        if reference_station_raw and reference_station_raw != "none":
            if reference_station_raw not in ALLOWED_REFERENCE_STATIONS:
                return _err(400, f"reference_station must be one of: {sorted(ALLOWED_REFERENCE_STATIONS)}")
            reference_station = reference_station_raw

        # Relative mode with drift detection
        if reference_station and body.get("expected_gap") is not None:
            target_df = _fetch_raw(station, start_dt, end_dt)
            ref_df = _fetch_raw(reference_station, start_dt, end_dt)

            if target_df.empty or ref_df.empty:
                return _err(404, f"Missing data for {station} or {reference_station} in window")

            merged = target_df.merge(
                ref_df[['Tab_DateTime', 'effective_value']].rename(columns={'effective_value': 'ref_val'}),
                on='Tab_DateTime',
                how='inner'
            )

            if merged.empty:
                return _err(404, "No overlapping timestamps between stations")

            merged['delta'] = merged['effective_value'] - merged['ref_val']

            try:
                expected_delta = float(body.get("expected_gap", 0.0))
            except (TypeError, ValueError):
                return _err(400, "expected_gap must be a number")

            merged['deviation'] = (merged['delta'] - expected_delta).abs()

            DRIFT_THRESHOLD = 0.05
            drifted = merged[merged['deviation'] > DRIFT_THRESHOLD]

            if drifted.empty:
                return _ok({
                    "station": station,
                    "status": "no_drift_detected",
                    "reference_station": reference_station,
                    "expected_gap": expected_delta,
                    "message": "Delta between stations matches expected gap throughout window"
                })

            first_drift_ts = drifted['Tab_DateTime'].min()
            last_drift_ts = drifted['Tab_DateTime'].max()

            return _ok({
                "station": station,
                "drift_detected": True,
                "reference_station": reference_station,
                "expected_gap": expected_delta,
                "malfunction_start": first_drift_ts.isoformat(),
                "malfunction_end": last_drift_ts.isoformat(),
                "drift_samples": len(drifted),
                "max_deviation": float(drifted['deviation'].max()),
                "message": f"Drift detected: {first_drift_ts} to {last_drift_ts}"
            })
        else:
            # Fall back to existing 12-hour stable window algorithm (keep original code)
            # Fetch stable windows: before (12h before start) and after (12h after end)
            before_data, after_data = _fetch_stable_window_data(station, start_dt, end_dt)

            if before_data.empty or after_data.empty:
                return _err(
                    422,
                    "Insufficient data to detect shift: need stable data 12 hours before and after the correction window"
                )

            # Calculate medians and IQR for each window
            before_median, before_iqr = _calculate_window_stats(before_data)
            after_median, after_iqr = _calculate_window_stats(after_data)

            if before_median is None or after_median is None:
                return _err(422, "Could not calculate statistics for stable windows")

            # Suggested offset: the median difference (before - after)
            # This represents the shift to correct for
            suggested_offset = round(before_median - after_median, 4)

            # Confidence based on IQR consistency
            # Low IQR in both windows = high confidence (stable plateaus)
            # High IQR in either window = low confidence (noisy data)
            avg_iqr = (before_iqr + after_iqr) / 2.0
            confidence_threshold = 0.05  # Threshold for IQR stability
            confidence = "high" if avg_iqr < confidence_threshold else "medium" if avg_iqr < 0.15 else "low"

            return _ok({
                "station": station,
                "suggested_offset": suggested_offset,
                "confidence": confidence,
                "method": "12_hour_stable_window",
                "before_median": round(before_median, 4),
                "after_median": round(after_median, 4),
                "average_iqr": round(avg_iqr, 4),
                "samples_before": len(before_data),
                "samples_after": len(after_data),
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
