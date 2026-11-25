# backend/lambdas/calibration/main.py
"""
Calibration correction service — admin only.

Handlers: samples / preview / suggest / references / suggest-gap / history (read-only),
commit and revert (write).

Editor operations (OTT Hydras-style graphical + tabular editor):
  offset       shift values by a constant (datum/reference offset)
  interpolate  linear interpolation across the window or the selected points (also re-fills deleted ones)
  relative     follow / level-shift to a reference station (+ expected gap)
  delete       remove bad samples from the validated series (raw sample kept)
  restore      back to the original raw value (removes correction and deletion)
  manual       typed values per timestamp (tabular editing)
Every operation can act on the whole window or on selected samples (`timestamps`).

Data model (migration 003_calibration_layer.sql):
  * Raw data in "Monitors_info2" is never modified (on AWS it is a replica of on-prem).
  * Corrections live in "Calibration_Offsets"; readers use the "Monitors_effective" view.
  * Every commit/revert writes "Calibration_Audit" + "Calibration_Audit_Rows" (previous
    offsets) in the SAME transaction as the change, so any commit can be undone.

Security:
  * Caller identity comes from the Cognito authorizer (API Gateway) or the local
    FastAPI adapter — see shared/auth.py. Every handler requires an admin.
  * station / reference_station are checked against an allowlist; datetimes are parsed
    and bounded (max 2-year window); all SQL uses bind parameters.
  * Commits are idempotent: the client sends request_id (UUID); a repeated request_id
    returns the original result instead of applying the correction twice.
  * Exception details are logged server-side only.
"""
import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, '..', '..')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from shared.auth import identity_from_event  # noqa: E402
from shared.calibration_math import (  # noqa: E402
    DEFAULT_TOLERANCE_S, MAX_TOLERANCE_S, MIN_COVERAGE_FOLLOW, MIN_COVERAGE_LEVEL,
    DriftParams, align_reference, coverage, detect_drift, suggest_gap,
)

try:
    from shared.database import engine
    from sqlalchemy import text
    DATABASE_AVAILABLE = engine is not None
except ImportError as e:  # pragma: no cover
    logging.getLogger(__name__).error(f"Database import error in calibration: {e}")
    engine, DATABASE_AVAILABLE = None, False

logger = logging.getLogger(__name__)

JSON_HEADERS = {"Content-Type": "application/json", "Cache-Control": "no-store"}

_STATION_NAME_RE = re.compile(r'^[a-zA-Z0-9 \-_]{1,50}$')
_ALLOWED_STATIONS = frozenset(
    s.strip() for s in os.getenv("CALIBRATION_STATIONS", "Acre,Ashdod,Ashkelon,Eilat,Haifa,Yafo").split(",") if s.strip()
)
MAX_WINDOW_DAYS = 730
MAX_OFFSET_M = 10.0
DRIFT_THRESHOLD_M = float(os.getenv("CALIBRATION_DRIFT_THRESHOLD", "0.05"))
STABLE_WINDOW_HOURS = 12

# ---------------------------------------------------------------------------
# Response helpers / validation
# ---------------------------------------------------------------------------

def _ok(data):
    return {"statusCode": 200, "headers": JSON_HEADERS, "body": json.dumps(data, default=str)}


def _err(status, msg):
    return {"statusCode": status, "headers": JSON_HEADERS, "body": json.dumps({"error": msg})}


class _BadRequest(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status, self.msg = status, msg


def _require_admin(event):
    ident = identity_from_event(event)
    if ident is None:
        return None, _err(401, "Sign-in required")
    if not ident.is_admin:
        logger.warning("[SECURITY] Calibration denied for non-admin user sub=%s", ident.sub)
        return None, _err(403, "Calibration is restricted to administrators")
    return ident, None


def _parse_body(event):
    body = event.get("body") or {}
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            raise _BadRequest(400, "Invalid JSON body")
    if not isinstance(body, dict):
        raise _BadRequest(400, "JSON object expected")
    return body


def _station(value, field="station"):
    if not isinstance(value, str) or not _STATION_NAME_RE.match(value.strip()):
        raise _BadRequest(400, f"{field} contains invalid characters")
    value = value.strip()
    if value not in _ALLOWED_STATIONS:
        raise _BadRequest(400, f"Unknown {field}: '{value}'")
    return value


def _optional_reference(body, station):
    raw = body.get("reference_station")
    if not raw or raw == "none":
        return None
    ref = _station(raw, "reference_station")
    if ref == station:
        raise _BadRequest(400, "reference_station must differ from station")
    return ref


def _dt(value, field):
    if not isinstance(value, str) or not value.strip():
        raise _BadRequest(400, f"{field} must be a non-empty string")
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        raise _BadRequest(400, f"{field} must be ISO-8601 (e.g. 2026-10-08T15:13:00)")
    if dt.tzinfo is not None:  # DB stores naive local timestamps
        dt = dt.replace(tzinfo=None)
    if not 2000 <= dt.year <= 2100:
        raise _BadRequest(400, f"{field} year must be between 2000 and 2100")
    return dt


def _window(body):
    start, end = _dt(body.get("start_datetime"), "start_datetime"), _dt(body.get("end_datetime"), "end_datetime")
    if start >= end:
        raise _BadRequest(400, "start_datetime must be earlier than end_datetime")
    if end - start > timedelta(days=MAX_WINDOW_DAYS):
        raise _BadRequest(400, f"Correction window cannot exceed {MAX_WINDOW_DAYS} days")
    return start, end


def _number(body, field, default=None, max_abs=MAX_OFFSET_M):
    raw = body.get(field, default)
    if raw is None:
        raise _BadRequest(400, f"{field} is required")
    try:
        val = float(raw)
    except (TypeError, ValueError):
        raise _BadRequest(400, f"{field} must be a number")
    if not np.isfinite(val):
        raise _BadRequest(400, f"{field} must be finite")
    if abs(val) > max_abs:
        raise _BadRequest(400, f"{field} magnitude must be <= {max_abs} m")
    return val


CORRECTION_TYPES = ("offset", "interpolate", "relative", "delete", "restore", "manual")
MAX_SELECTED = 20000          # selected samples / typed values per request
MAX_EDITOR_SAMPLES = 20000    # ~2 weeks at 1-minute sampling
MAX_ANCHOR_GAP = timedelta(days=1)


def _correction_type(body):
    ct = body.get("correction_type") or "offset"
    if ct not in CORRECTION_TYPES:
        raise _BadRequest(400, "correction_type must be one of: " + ", ".join(CORRECTION_TYPES))
    return ct


def _parse_ts_list(raw, field):
    if not isinstance(raw, list):
        raise _BadRequest(400, f"{field} must be a list")
    if len(raw) > MAX_SELECTED:
        raise _BadRequest(400, f"{field}: at most {MAX_SELECTED} samples per request")
    try:
        ts = pd.to_datetime(pd.Series([str(t).strip() for t in raw]), format="ISO8601")
    except (ValueError, TypeError):
        raise _BadRequest(400, f"{field} must contain ISO-8601 timestamps")
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_localize(None)
    return ts


def _selection(body, df):
    """Boolean mask of the samples the operation acts on: `timestamps` if given, else the whole window."""
    raw = body.get("timestamps")
    if raw is None:
        return np.ones(len(df), dtype=bool), None
    ts = _parse_ts_list(raw, "timestamps")
    if ts.empty:
        raise _BadRequest(400, "timestamps is empty — select at least one sample")
    mask = df["Tab_DateTime"].isin(set(ts)).to_numpy()
    missing = len(set(ts)) - int(mask.sum())
    if missing:
        raise _BadRequest(400, f"{missing} selected sample(s) are not in the window for this station")
    return mask, int(mask.sum())


def _manual_values(body):
    raw = body.get("values")
    if not isinstance(raw, list) or not raw:
        raise _BadRequest(400, "manual mode needs values: [{Tab_DateTime, value}, ...]")
    ts = _parse_ts_list([v.get("Tab_DateTime") if isinstance(v, dict) else None for v in raw], "values")
    vals = []
    for v in raw:
        try:
            x = float(v.get("value"))
        except (TypeError, ValueError, AttributeError):
            raise _BadRequest(400, "every value must be a number (metres)")
        if not np.isfinite(x) or abs(x) > 100:
            raise _BadRequest(400, "values must be finite and within ±100 m")
        vals.append(x)
    return pd.Series(vals, index=pd.DatetimeIndex(ts)).groupby(level=0).last()


def _request_id(body):
    rid = body.get("request_id")
    if rid is None:
        raise _BadRequest(400, "request_id (UUID) is required for commits")
    try:
        return str(uuid.UUID(str(rid)))
    except ValueError:
        raise _BadRequest(400, "request_id must be a UUID")

def _tolerance(body):
    raw = body.get("tolerance_seconds", DEFAULT_TOLERANCE_S)
    try:
        tol = int(raw)
    except (TypeError, ValueError):
        raise _BadRequest(400, "tolerance_seconds must be an integer")
    if not 0 <= tol <= MAX_TOLERANCE_S:
        raise _BadRequest(400, f"tolerance_seconds must be between 0 and {MAX_TOLERANCE_S}")
    return tol


def _drift_params(body):
    try:
        return DriftParams(
            threshold_m=float(body.get("threshold", 0.05)),
            smooth_minutes=int(body.get("smooth_minutes", 30)),
            merge_minutes=int(body.get("merge_minutes", 30)),
            min_minutes=int(body.get("min_minutes", 20)),
        ).validate()
    except (TypeError, ValueError) as exc:
        raise _BadRequest(400, str(exc))


# ---------------------------------------------------------------------------
# Queries (all read from the corrected view)
# ---------------------------------------------------------------------------

_WINDOW_SQL = """
    SELECT m."Tab_DateTime", l."Station", m."Tab_TabularTag",
           m."Raw_mDepthC1"        AS raw_value,
           m."Tab_Value_mDepthC1"  AS current_value
    FROM "Monitors_effective" m
    JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
    WHERE l."Station" = :station
      AND m."Tab_DateTime" >= :start AND m."Tab_DateTime" <= :end
      AND m."Tab_Value_mDepthC1" IS NOT NULL
    ORDER BY m."Tab_DateTime"
"""


_EDITOR_SQL = """
    SELECT m."Tab_DateTime", m."Tab_TabularTag",
           CAST(m."Tab_Value_mDepthC1" AS DOUBLE PRECISION) AS raw_value,
           COALESCE(o."Offset", 0)    AS "offset",
           COALESCE(o."Deleted", false) AS deleted
    FROM "Monitors_info2" m
    JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
    LEFT JOIN "Calibration_Offsets" o
      ON o."Tab_TabularTag" = m."Tab_TabularTag" AND o."Tab_DateTime" = m."Tab_DateTime"
    WHERE l."Station" = :station
      AND m."Tab_DateTime" >= :start AND m."Tab_DateTime" <= :end
      AND m."Tab_Value_mDepthC1" IS NOT NULL
    ORDER BY m."Tab_DateTime"
    LIMIT :limit
"""


def _fetch_editor_window(conn, station, start, end, limit=MAX_EDITOR_SAMPLES * 5):
    """Every raw sample in the window, including deleted ones (the editor's view of the data)."""
    res = conn.execute(text(_EDITOR_SQL), {"station": station, "start": start, "end": end, "limit": limit + 1})
    df = pd.DataFrame(res.fetchall(), columns=list(res.keys()))
    if len(df) > limit:
        raise _BadRequest(422, f"The window has more than {limit} samples — shorten it")
    if not df.empty:
        df["Tab_DateTime"] = pd.to_datetime(df["Tab_DateTime"])
        df[["raw_value", "offset"]] = df[["raw_value", "offset"]].astype(float)
        df["deleted"] = df["deleted"].astype(bool)
        df["current_value"] = np.where(df["deleted"], np.nan, df["raw_value"] + df["offset"])
    return df


def _fetch_window(conn, station, start, end):
    res = conn.execute(text(_WINDOW_SQL), {"station": station, "start": start, "end": end})
    df = pd.DataFrame(res.fetchall(), columns=list(res.keys()))
    if not df.empty:
        df["Tab_DateTime"] = pd.to_datetime(df["Tab_DateTime"])
        df[["raw_value", "current_value"]] = df[["raw_value", "current_value"]].astype(float)
    return df


def _boundaries(conn, station, start, end):
    """
    Anchor points for interpolation: the last good sample BEFORE the window and the first
    sample AFTER it (current corrected values). Samples inside [start, end] are the ones
    being replaced, so they must not be used as anchors.
    """
    sql = text("""
        (SELECT 'start' AS b, m."Tab_DateTime" AS t, m."Tab_Value_mDepthC1" AS v
           FROM "Monitors_effective" m JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
          WHERE l."Station" = :station AND m."Tab_DateTime" < :start AND m."Tab_Value_mDepthC1" IS NOT NULL
          ORDER BY m."Tab_DateTime" DESC LIMIT 1)
        UNION ALL
        (SELECT 'end' AS b, m."Tab_DateTime" AS t, m."Tab_Value_mDepthC1" AS v
           FROM "Monitors_effective" m JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
          WHERE l."Station" = :station AND m."Tab_DateTime" > :end AND m."Tab_Value_mDepthC1" IS NOT NULL
          ORDER BY m."Tab_DateTime" ASC LIMIT 1)
    """)
    found = {row[0]: (pd.Timestamp(row[1]), float(row[2]))
             for row in conn.execute(sql, {"station": station, "start": start, "end": end})}
    if "start" not in found or "end" not in found:
        raise _BadRequest(422, "Cannot interpolate: need data before the start and after the end of the window")
    gap = max(start - found["start"][0].to_pydatetime(), found["end"][0].to_pydatetime() - end)
    if gap > timedelta(days=1):
        raise _BadRequest(422, "Cannot interpolate: nearest good sample is more than 1 day from the window edge")
    return found["start"], found["end"]


def _interpolate_selected(conn, station, df, target, start, end):
    """Linear interpolation of the selected samples from the nearest good, unselected samples."""
    ext = _fetch_editor_window(conn, station, start - MAX_ANCHOR_GAP, end + MAX_ANCHOR_GAP)
    chosen = set(df.loc[target, "Tab_DateTime"])
    anchors = ext[~ext["deleted"] & ~ext["Tab_DateTime"].isin(chosen)]
    if anchors.empty:
        raise _BadRequest(422, "Cannot interpolate: no good samples around the selection")
    at = anchors["Tab_DateTime"].astype("int64").to_numpy()
    av = anchors["current_value"].to_numpy()
    t = df.loc[target, "Tab_DateTime"].astype("int64").to_numpy()
    left = np.searchsorted(at, t, side="right") - 1
    right = np.searchsorted(at, t, side="left")
    max_gap = int(MAX_ANCHOR_GAP.total_seconds() * 1e9)
    ok = (left >= 0) & (right < len(at))
    if not ok.all():
        raise _BadRequest(422, "Cannot interpolate: need good data before and after every selected sample")
    if ((t - at[left]) > max_gap).any() or ((at[right] - t) > max_gap).any():
        raise _BadRequest(422, "Cannot interpolate: nearest good sample is more than 1 day away")
    return np.interp(t, at, av)


def _compute_targets(conn, body, station, start, end, ctype, reference, for_commit=False):
    """
    Return (df, params). df holds every sample of the window with raw_value, current_value
    (NaN = deleted), corrected_value, new_offset, new_deleted and `changed` (rows to write).
    Shared by preview and commit so both always agree.
    """
    df = _fetch_editor_window(conn, station, start, end)
    if df.empty:
        raise _BadRequest(404, "No data found for the specified station and time window")
    selected, n_selected = _selection(body, df)
    good = ~df["deleted"].to_numpy()
    df["corrected_value"] = df["current_value"]
    df["new_offset"] = df["offset"]
    df["new_deleted"] = df["deleted"]
    df["matched"] = True
    params = {}
    if n_selected is not None:
        params["selected_samples"] = n_selected

    if ctype == "offset":
        offset = _number(body, "offset", default=0.0)
        target = selected & good                                 # deleted samples stay deleted
        df.loc[target, "corrected_value"] = df.loc[target, "current_value"] + offset   # additive
        params["offset"] = offset

    elif ctype == "interpolate":
        target = selected.copy()                                 # also re-fills deleted samples
        if n_selected is None:
            (t0, start_val), (t1, end_val) = _boundaries(conn, station, start, end)
            frac = (df["Tab_DateTime"] - t0).dt.total_seconds() / (t1 - t0).total_seconds()
            df["corrected_value"] = start_val + frac.clip(0, 1) * (end_val - start_val)
            params.update({"start_value": start_val, "end_value": end_val,
                           "anchor_start": t0.isoformat(), "anchor_end": t1.isoformat()})
        else:
            df.loc[target, "corrected_value"] = _interpolate_selected(conn, station, df, target, start, end)
            params["anchors"] = "nearest good unselected samples"
        df.loc[target, "new_deleted"] = False

    elif ctype == "delete":
        target = selected & good
        df.loc[target, "corrected_value"] = np.nan
        df.loc[target, "new_deleted"] = True                     # offset kept, so restore is exact

    elif ctype == "restore":
        target = selected & ((df["offset"].to_numpy() != 0) | df["deleted"].to_numpy())
        df.loc[target, "corrected_value"] = df.loc[target, "raw_value"]
        df.loc[target, "new_deleted"] = False

    elif ctype == "manual":
        values = _manual_values(body)
        idx = pd.DatetimeIndex(df["Tab_DateTime"])
        missing = len(values.index.difference(idx))
        if missing:
            raise _BadRequest(400, f"{missing} typed value(s) are not samples of this station in the window")
        target = idx.isin(values.index)
        df.loc[target, "corrected_value"] = values.reindex(idx[target]).to_numpy()
        df.loc[target, "new_deleted"] = False
        if (np.abs(df.loc[target, "corrected_value"] - df.loc[target, "raw_value"]) > MAX_OFFSET_M).any():
            raise _BadRequest(400, f"a typed value differs from the raw value by more than {MAX_OFFSET_M} m")
        params["typed_values"] = int(target.sum())

    else:  # relative — Target ≈ Reference + Gap
        if not reference:
            raise _BadRequest(400, "relative mode requires reference_station")
        gap = _number(body, "expected_gap", default=0.0)
        tolerance = _tolerance(body)
        strength = body.get("strength") or "follow"
        if strength not in ("follow", "level"):
            raise _BadRequest(400, "strength must be 'follow' or 'level'")
        target = selected & good
        sub = df[target]
        if sub.empty:
            raise _BadRequest(404, "No (undeleted) samples in the selection")
        ref = _fetch_window(conn, reference, start, end)
        if ref.empty:
            raise _BadRequest(404, f"No reference data for {reference} in window")
        # Align the reference onto the target's own timestamps (stations rarely sample in lock-step).
        ref_aligned = align_reference(sub["Tab_DateTime"], ref["Tab_DateTime"], ref["current_value"], tolerance)
        ref_vals = ref_aligned.to_numpy()
        matched = ~np.isnan(ref_vals)
        df.loc[target, "matched"] = matched
        cov = coverage(ref_aligned)
        needed = MIN_COVERAGE_FOLLOW if strength == "follow" else MIN_COVERAGE_LEVEL
        if not matched.any():
            raise _BadRequest(404, "No reference samples within the alignment tolerance")
        # Required correction on matched samples, relative to the CURRENT (already corrected) value
        needed_shift = pd.Series((ref_vals + gap) - sub["current_value"].to_numpy(),
                                 index=pd.DatetimeIndex(sub["Tab_DateTime"]))
        if strength == "follow":
            # Matched samples follow the reference exactly; unmatched samples get the correction
            # interpolated in time from their neighbours, so the window has no uncorrected holes.
            shift = needed_shift.interpolate(method="time", limit_direction="both")
            df.loc[target, "corrected_value"] = sub["current_value"].to_numpy() + shift.to_numpy()
        else:
            # Level shift: one robust constant keeps the target's own short-term signal (seiches, waves).
            const = float(needed_shift[matched].median())
            df.loc[target, "corrected_value"] = sub["current_value"].to_numpy() + const
        params.update({"reference_station": reference, "expected_gap": gap, "strength": strength,
                       "tolerance_seconds": tolerance, "coverage": round(cov, 4), "min_coverage": needed})
        if strength == "level":
            params["level_shift"] = round(const, 4)
        if for_commit and cov < needed:
            raise _BadRequest(422, f"Reference covers {cov:.0%} of the window; {needed:.0%} is required "
                                   f"for '{strength}'. Shorten the window, widen the tolerance or pick another reference.")

    df["changed"] = target
    write = target & ~df["new_deleted"].to_numpy()
    df.loc[write, "new_offset"] = df.loc[write, "corrected_value"] - df.loc[write, "raw_value"]
    if not np.isfinite(df.loc[target & ~df["new_deleted"].to_numpy(), "new_offset"]).all():
        raise _BadRequest(422, "Correction produced invalid values")
    if for_commit and not target.any():
        raise _BadRequest(422, "Nothing to change in this window/selection")
    return df, params


def _reference_rows(conn, reference, start, end):
    if not reference:
        return []
    ref = _fetch_window(conn, reference, start, end)
    return [{"Tab_DateTime": str(t), "Station": reference, "value": v}
            for t, v in zip(ref["Tab_DateTime"], ref["current_value"])]

def _stage_new_offsets(conn, df):
    """Bulk-load (tag, datetime, new_offset) into a transaction-scoped temp table."""
    from psycopg2.extras import execute_values
    conn.execute(text("""
        CREATE TEMP TABLE _cal_new ON COMMIT DROP AS
        SELECT "Tab_TabularTag" AS tag, "Tab_DateTime" AS dt, "Offset" AS off, "Deleted" AS del
          FROM "Calibration_Offsets" WITH NO DATA
    """))
    values = list(zip(df["Tab_TabularTag"].tolist(),
                      [d.to_pydatetime() for d in df["Tab_DateTime"]],
                      df["new_offset"].astype(float).tolist(),
                      df["new_deleted"].astype(bool).tolist()))
    cur = conn.connection.dbapi_connection.cursor()
    try:
        execute_values(cur, "INSERT INTO _cal_new (tag, dt, off, del) VALUES %s", values, page_size=5000)
    finally:
        cur.close()
    return len(values)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _guarded(fn):
    def wrapper(event, context):
        ident, err = _require_admin(event)
        if err:
            return err
        if not DATABASE_AVAILABLE:
            return _err(503, "Database not available")
        try:
            return fn(event, ident)
        except _BadRequest as br:
            return _err(br.status, br.msg)
        except Exception:
            logger.exception("[ERROR] calibration handler %s failed", fn.__name__)
            return _err(500, "Internal server error")
    wrapper.__name__ = fn.__name__
    return wrapper


def _num(v):
    return None if v is None or not np.isfinite(v) else float(v)


@_guarded
def lambda_handler_preview(event, ident):
    body = _parse_body(event)
    station = _station(body.get("station"))
    start, end = _window(body)
    ctype = _correction_type(body)
    reference = _optional_reference(body, station)
    with engine.connect() as conn:
        df, params = _compute_targets(conn, body, station, start, end, ctype, reference)
        refs = _reference_rows(conn, reference, start, end)
    changed = df["changed"].to_numpy()
    delta = (df["corrected_value"] - df["current_value"])[changed].dropna()
    return _ok({
        "station": station,
        "correction_type": ctype,
        "parameters": params,
        "offset_applied": params.get("offset"),
        "start_datetime": start.isoformat(),
        "end_datetime": end.isoformat(),
        "rows_affected": int(changed.sum()),
        "rows_deleted": int((df["new_deleted"] & ~df["deleted"]).sum()),
        "rows_restored": int((~df["new_deleted"] & df["deleted"]).sum()),
        "change_summary": {"min": _num(delta.min()) if len(delta) else 0.0,
                           "max": _num(delta.max()) if len(delta) else 0.0,
                           "mean": _num(delta.mean()) if len(delta) else 0.0},
        "coverage": params.get("coverage"),
        "commit_allowed": bool(changed.any()) and (
            params.get("coverage") is None or params["coverage"] >= params.get("min_coverage", 0)),
        "data": [
            {"Tab_DateTime": str(r.Tab_DateTime), "Station": station, "raw_value": _num(r.raw_value),
             "current_value": _num(r.current_value), "corrected_value": _num(r.corrected_value),
             "deleted": bool(r.deleted), "will_be_deleted": bool(r.new_deleted),
             "changed": bool(r.changed), "matched": bool(r.matched)}
            for r in df.itertuples(index=False)
        ],
        "reference_data": refs,
    })


@_guarded
def lambda_handler_samples(event, ident):
    """The editor's table/graph data: every raw sample of the window with its correction state."""
    body = _parse_body(event)
    station = _station(body.get("station"))
    start, end = _window(body)
    with engine.connect() as conn:
        df = _fetch_editor_window(conn, station, start, end, limit=MAX_EDITOR_SAMPLES)
    return _ok({
        "station": station, "start_datetime": start.isoformat(), "end_datetime": end.isoformat(),
        "count": int(len(df)), "deleted": int(df["deleted"].sum()) if len(df) else 0,
        "corrected": int((df["offset"] != 0).sum()) if len(df) else 0,
        "samples": [
            {"Tab_DateTime": str(r.Tab_DateTime), "raw_value": _num(r.raw_value), "offset": _num(r.offset),
             "value": _num(r.current_value), "deleted": bool(r.deleted)}
            for r in df.itertuples(index=False)
        ],
    })


@_guarded
def lambda_handler_commit(event, ident):
    body = _parse_body(event)
    request_id = _request_id(body)
    station = _station(body.get("station"))
    start, end = _window(body)
    ctype = _correction_type(body)
    reference = _optional_reference(body, station)

    with engine.begin() as conn:
        # Idempotency: the same request_id never applies twice (client retries, double clicks).
        prev = conn.execute(text('SELECT "Id", "Rows_Affected", "Station" FROM "Calibration_Audit" WHERE "Request_Id" = :rid'),
                            {"rid": request_id}).fetchone()
        if prev:
            return _ok({"success": True, "duplicate": True, "audit_id": prev[0], "rows_updated": prev[1], "station": prev[2]})

        # Serialize commits per station so overlapping corrections can't interleave.
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"calibration:{station}"})

        df, params = _compute_targets(conn, body, station, start, end, ctype, reference, for_commit=True)
        df = df[df["changed"]]

        audit_id = conn.execute(text("""
            INSERT INTO "Calibration_Audit" ("Request_Id", "Action", "Station", "Correction_Type",
                "Start_DateTime", "End_DateTime", "Parameters", "Rows_Affected", "User_Email", "User_Sub")
            VALUES (:rid, 'commit', :station, :ctype, :start, :end, CAST(:params AS JSONB), :n, :email, :sub)
            RETURNING "Id"
        """), {"rid": request_id, "station": station, "ctype": ctype, "start": start, "end": end,
               "params": json.dumps(params), "n": int(len(df)), "email": ident.email, "sub": ident.sub}).scalar_one()

        n_rows = _stage_new_offsets(conn, df)
        # Snapshot previous offsets (NULL where there was none) for undo, then upsert — set-based.
        conn.execute(text("""
            INSERT INTO "Calibration_Audit_Rows" ("Audit_Id", "Tab_TabularTag", "Tab_DateTime", "Old_Offset", "Old_Deleted")
            SELECT :aid, n.tag, n.dt, o."Offset", o."Deleted"
              FROM _cal_new n
              LEFT JOIN "Calibration_Offsets" o ON o."Tab_TabularTag" = n.tag AND o."Tab_DateTime" = n.dt
        """), {"aid": audit_id})
        conn.execute(text("""
            INSERT INTO "Calibration_Offsets" ("Tab_TabularTag", "Tab_DateTime", "Offset", "Deleted", "Audit_Id")
            SELECT n.tag, n.dt, n.off, n.del, :aid FROM _cal_new n
            ON CONFLICT ("Tab_TabularTag", "Tab_DateTime")
            DO UPDATE SET "Offset" = EXCLUDED."Offset", "Deleted" = EXCLUDED."Deleted",
                          "Audit_Id" = EXCLUDED."Audit_Id"
        """), {"aid": audit_id})
        # Rows back to "no correction" (restore): drop them instead of keeping offset 0 rows.
        conn.execute(text("""
            DELETE FROM "Calibration_Offsets" o USING _cal_new n
             WHERE o."Tab_TabularTag" = n.tag AND o."Tab_DateTime" = n.dt
               AND n.off = 0 AND n.del = false
        """))
        rows = range(n_rows)

    logger.info("[AUDIT] commit id=%s station=%s type=%s rows=%s user=%s", audit_id, station, ctype, len(rows), ident.email)
    _invalidate_cache()
    return _ok({"success": True, "audit_id": audit_id, "station": station, "correction_type": ctype,
                "parameters": params, "offset_applied": params.get("offset"), "rows_updated": len(rows),
                "start_datetime": start.isoformat(), "end_datetime": end.isoformat()})


@_guarded
def lambda_handler_revert(event, ident):
    """Undo the most recent un-reverted commit for a station (or a specific audit_id if it is the latest)."""
    body = _parse_body(event)
    request_id = _request_id(body)
    station = _station(body.get("station"))
    with engine.begin() as conn:
        prev = conn.execute(text('SELECT "Reverts_Audit_Id", "Rows_Affected" FROM "Calibration_Audit" WHERE "Request_Id" = :rid'),
                            {"rid": request_id}).fetchone()
        if prev:
            return _ok({"success": True, "duplicate": True, "reverted_audit_id": prev[0], "rows_restored": prev[1]})
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"calibration:{station}"})
        target = conn.execute(text("""
            SELECT "Id" FROM "Calibration_Audit"
             WHERE "Station" = :station AND "Action" = 'commit' AND "Reverted_By_Id" IS NULL
             ORDER BY "Id" DESC LIMIT 1
        """), {"station": station}).scalar()
        if target is None:
            raise _BadRequest(404, f"No commit to revert for {station}")
        if body.get("audit_id") is not None and int(body["audit_id"]) != target:
            raise _BadRequest(409, "Only the most recent commit for a station can be reverted")

        n = conn.execute(text('SELECT COUNT(*) FROM "Calibration_Audit_Rows" WHERE "Audit_Id" = :a'), {"a": target}).scalar()
        rev_id = conn.execute(text("""
            INSERT INTO "Calibration_Audit" ("Request_Id", "Action", "Station", "Rows_Affected",
                                             "User_Email", "User_Sub", "Reverts_Audit_Id")
            VALUES (:rid, 'revert', :station, :n, :email, :sub, :target) RETURNING "Id"
        """), {"rid": request_id, "station": station, "n": n, "email": ident.email, "sub": ident.sub,
               "target": target}).scalar_one()
        # Restore previous values: delete rows that had no correction, reset the rest.
        conn.execute(text("""
            DELETE FROM "Calibration_Offsets" o USING "Calibration_Audit_Rows" r
             WHERE r."Audit_Id" = :a AND r."Old_Offset" IS NULL
               AND o."Tab_TabularTag" = r."Tab_TabularTag" AND o."Tab_DateTime" = r."Tab_DateTime"
        """), {"a": target})
        conn.execute(text("""
            INSERT INTO "Calibration_Offsets" ("Tab_TabularTag", "Tab_DateTime", "Offset", "Deleted", "Audit_Id")
            SELECT r."Tab_TabularTag", r."Tab_DateTime", r."Old_Offset", COALESCE(r."Old_Deleted", false), :rev
              FROM "Calibration_Audit_Rows" r
             WHERE r."Audit_Id" = :a AND r."Old_Offset" IS NOT NULL
            ON CONFLICT ("Tab_TabularTag", "Tab_DateTime")
            DO UPDATE SET "Offset" = EXCLUDED."Offset", "Deleted" = EXCLUDED."Deleted", "Audit_Id" = EXCLUDED."Audit_Id"
        """), {"a": target, "rev": rev_id})
        conn.execute(text('UPDATE "Calibration_Audit" SET "Reverted_By_Id" = :rev WHERE "Id" = :a'),
                     {"rev": rev_id, "a": target})
    logger.info("[AUDIT] revert id=%s of=%s station=%s user=%s", rev_id, target, station, ident.email)
    _invalidate_cache()
    return _ok({"success": True, "revert_audit_id": rev_id, "reverted_audit_id": target, "rows_restored": n})


@_guarded
def lambda_handler_history(event, ident):
    body = _parse_body(event)
    params = {"limit": 50}
    where = ""
    if body.get("station"):
        params["station"] = _station(body["station"])
        where = 'WHERE "Station" = :station'
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT "Id", "Action", "Station", "Correction_Type", "Start_DateTime", "End_DateTime",
                   "Parameters", "Rows_Affected", "User_Email", "Created_At", "Reverts_Audit_Id", "Reverted_By_Id"
              FROM "Calibration_Audit" {where} ORDER BY "Id" DESC LIMIT :limit
        """), params).mappings().all()   # noqa: S608 — `where` is a constant string
    return _ok({"history": [dict(r) for r in rows]})


@_guarded
def lambda_handler_suggest(event, ident):
    body = _parse_body(event)
    station = _station(body.get("station"))
    start, end = _window(body)
    reference = _optional_reference(body, station)

    with engine.connect() as conn:
        # Relative mode: Drift Detection Engine
        if reference and body.get("expected_gap") is not None:
            gap = _number(body, "expected_gap")
            params = _drift_params(body)
            tolerance = _tolerance(body)
            tgt = _fetch_window(conn, station, start, end)
            ref = _fetch_window(conn, reference, start, end)
            if tgt.empty or ref.empty:
                raise _BadRequest(404, f"Missing data for {station} or {reference} in window")
            aligned = align_reference(tgt["Tab_DateTime"], ref["Tab_DateTime"], ref["current_value"], tolerance)
            cov = coverage(aligned)
            if cov < MIN_COVERAGE_LEVEL:
                raise _BadRequest(422, f"Reference covers only {cov:.0%} of the window — drift detection needs 50%")
            deviation = (tgt["current_value"].to_numpy() - aligned.to_numpy()) - gap
            result = detect_drift(tgt["Tab_DateTime"], deviation, params)
            episodes = result["episodes"]
            out = {"station": station, "reference_station": reference, "expected_gap": gap,
                   "coverage": round(cov, 4), "episodes": episodes, "slow_drift": result["slow_drift"],
                   "deviation": result["series"], "params": result["params"]}
            if not episodes:
                out.update(status="no_drift_detected", drift_detected=False,
                           message=f"Delta stays within ±{params.threshold_m:.3f} m of the expected gap")
                return _ok(out)
            first = episodes[0]
            out.update(drift_detected=True, malfunction_start=first["start"], malfunction_end=first["end"],
                       drift_samples=sum(e["samples"] for e in episodes),
                       max_deviation=max(e["max_deviation"] for e in episodes),
                       message=f"{len(episodes)} drift episode(s); first {first['start']} → {first['end']}")
            return _ok(out)

        # Offset suggestion: bring the window back to the level of the surrounding stable data.
        inside = _fetch_window(conn, station, start, end)
        before = _fetch_window(conn, station, start - timedelta(hours=STABLE_WINDOW_HOURS), start - timedelta(microseconds=1))
        after = _fetch_window(conn, station, end + timedelta(microseconds=1), end + timedelta(hours=STABLE_WINDOW_HOURS))

    if inside.empty:
        raise _BadRequest(404, "No data inside the correction window")
    if before.empty and after.empty:
        raise _BadRequest(422, f"Need stable data within {STABLE_WINDOW_HOURS} h before or after the window")

    surround = pd.concat([before["current_value"], after["current_value"]])
    inside_med = float(inside["current_value"].median())
    surround_med = float(surround.median())
    suggested = round(surround_med - inside_med, 4)

    def iqr(s):
        return float(s.quantile(0.75) - s.quantile(0.25)) if len(s) else None

    b_med = float(before["current_value"].median()) if len(before) else None
    a_med = float(after["current_value"].median()) if len(after) else None
    # Confidence: stable surroundings that agree with each other on both sides.
    spread = max(v for v in [iqr(before["current_value"]), iqr(after["current_value"]), 0.0] if v is not None)
    disagreement = abs(b_med - a_med) if b_med is not None and a_med is not None else 0.1
    score = max(spread, disagreement)
    confidence = "high" if score < 0.05 else "medium" if score < 0.15 else "low"

    return _ok({
        "station": station, "suggested_offset": suggested, "confidence": confidence,
        "method": "window_vs_surrounding_median",
        "inside_median": round(inside_med, 4), "surrounding_median": round(surround_med, 4),
        "before_median": None if b_med is None else round(b_med, 4),
        "after_median": None if a_med is None else round(a_med, 4),
        "step_change_before_after": None if (b_med is None or a_med is None) else round(a_med - b_med, 4),
        "before_samples": int(len(before)), "after_samples": int(len(after)), "inside_samples": int(len(inside)),
    })


@_guarded
def lambda_handler_references(event, ident):
    """Every other station with its coverage of the target's window (for the Compare dropdown)."""
    body = _parse_body(event)
    station = _station(body.get("station"))
    start, end = _window(body)
    tolerance = _tolerance(body)
    out = []
    with engine.connect() as conn:
        tgt = _fetch_window(conn, station, start, end)
        last = {r[0]: r[1] for r in conn.execute(text("""
            SELECT l."Station", max(m."Tab_DateTime") FROM "Monitors_info2" m
            JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag" GROUP BY l."Station"
        """))}
        for ref_station in sorted(_ALLOWED_STATIONS - {station}):
            ref = _fetch_window(conn, ref_station, start, end)
            if tgt.empty or ref.empty:
                cov = 0.0
            else:
                cov = coverage(align_reference(tgt["Tab_DateTime"], ref["Tab_DateTime"], ref["current_value"], tolerance))
            out.append({"station": ref_station, "samples_in_window": int(len(ref)), "coverage": round(cov, 4),
                        "last_reading": str(last[ref_station]) if last.get(ref_station) else None})
    out.sort(key=lambda r: (-r["coverage"], r["station"]))
    return _ok({"station": station, "target_samples": int(len(tgt)), "references": out})


@_guarded
def lambda_handler_suggest_gap(event, ident):
    """Typical gap target − reference over a calm baseline BEFORE the window (default 7 days)."""
    body = _parse_body(event)
    station = _station(body.get("station"))
    reference = _optional_reference(body, station)
    if not reference:
        raise _BadRequest(400, "reference_station is required")
    start = _dt(body.get("start_datetime"), "start_datetime")
    try:
        days = int(body.get("baseline_days", 7))
    except (TypeError, ValueError):
        raise _BadRequest(400, "baseline_days must be an integer")
    if not 1 <= days <= 90:
        raise _BadRequest(400, "baseline_days must be between 1 and 90")
    tolerance = _tolerance(body)
    b_start, b_end = start - timedelta(days=days), start - timedelta(microseconds=1)
    with engine.connect() as conn:
        tgt = _fetch_window(conn, station, b_start, b_end)
        ref = _fetch_window(conn, reference, b_start, b_end)
    if tgt.empty or ref.empty:
        raise _BadRequest(404, f"No baseline data for {station} or {reference} in the {days} days before the window")
    aligned = align_reference(tgt["Tab_DateTime"], ref["Tab_DateTime"], ref["current_value"], tolerance)
    result = suggest_gap(pd.Series(tgt["current_value"].to_numpy() - aligned.to_numpy()))
    if result is None:
        raise _BadRequest(422, "Not enough overlapping baseline data to estimate the gap")
    result.update(station=station, reference_station=reference, baseline_days=days,
                  baseline_start=b_start.isoformat(), baseline_end=start.isoformat())
    return _ok(result)


def _invalidate_cache():
    """Best-effort Redis invalidation (Redis is optional; not deployed on AWS for now)."""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return
    try:
        import redis
        r = redis.from_url(redis_url, socket_timeout=2)
        for pattern in ("*data*", "*stations*", "query:*"):
            batch = list(r.scan_iter(match=pattern, count=500))
            if batch:
                r.delete(*batch)
        r.close()
    except Exception as exc:
        logger.warning("Redis cache invalidation skipped: %s", type(exc).__name__)


def lambda_handler(event, context):
    """Route by path (API Gateway proxy integration)."""
    path = (event.get("path") or event.get("rawPath") or "").rstrip("/")
    for suffix, handler in (("/samples", lambda_handler_samples),
                            ("/preview", lambda_handler_preview), ("/commit", lambda_handler_commit),
                            ("/suggest-gap", lambda_handler_suggest_gap), ("/suggest", lambda_handler_suggest),
                            ("/references", lambda_handler_references), ("/revert", lambda_handler_revert),
                            ("/history", lambda_handler_history)):
        if path.endswith(suffix):
            return handler(event, context)
    return _err(404, "Unknown calibration endpoint")
