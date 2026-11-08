# backend/lambdas/calibration/main.py
"""
Calibration correction service — admin only.

Handlers: preview (read-only), suggest (read-only), commit (write), revert (write), history (read).

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


def _correction_type(body):
    ct = body.get("correction_type") or "offset"
    if ct not in ("offset", "interpolate", "relative"):
        raise _BadRequest(400, "correction_type must be 'offset', 'interpolate' or 'relative'")
    return ct


def _request_id(body):
    rid = body.get("request_id")
    if rid is None:
        raise _BadRequest(400, "request_id (UUID) is required for commits")
    try:
        return str(uuid.UUID(str(rid)))
    except ValueError:
        raise _BadRequest(400, "request_id must be a UUID")

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


def _compute_targets(conn, body, station, start, end, ctype, reference):
    """
    Return (df, params) where df has Tab_TabularTag, Tab_DateTime, raw_value, current_value,
    corrected_value. Shared by preview and commit so both always agree.
    """
    df = _fetch_window(conn, station, start, end)
    if df.empty:
        raise _BadRequest(404, "No data found for the specified station and time window")

    if ctype == "offset":
        offset = _number(body, "offset", default=0.0)
        df["corrected_value"] = df["current_value"] + offset   # additive on top of existing corrections
        params = {"offset": offset}

    elif ctype == "interpolate":
        (t0, start_val), (t1, end_val) = _boundaries(conn, station, start, end)
        frac = (df["Tab_DateTime"] - t0).dt.total_seconds() / (t1 - t0).total_seconds()
        df["corrected_value"] = start_val + frac.clip(0, 1) * (end_val - start_val)
        params = {"start_value": start_val, "end_value": end_val,
                  "anchor_start": t0.isoformat(), "anchor_end": t1.isoformat()}

    else:  # relative
        if not reference:
            raise _BadRequest(400, "relative mode requires reference_station")
        gap = _number(body, "expected_gap", default=0.0)
        ref = _fetch_window(conn, reference, start, end)
        if ref.empty:
            raise _BadRequest(404, f"No reference data for {reference} in window")
        ref_vals = ref.set_index("Tab_DateTime")["current_value"]
        df["corrected_value"] = df["Tab_DateTime"].map(ref_vals) + gap
        df = df[df["corrected_value"].notna()].copy()       # only timestamps both stations share
        if df.empty:
            raise _BadRequest(404, "No overlapping timestamps between stations")
        params = {"reference_station": reference, "expected_gap": gap}

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
        SELECT "Tab_TabularTag" AS tag, "Tab_DateTime" AS dt, "Offset" AS off
          FROM "Calibration_Offsets" WITH NO DATA
    """))
    values = list(zip(df["Tab_TabularTag"].tolist(),
                      [d.to_pydatetime() for d in df["Tab_DateTime"]],
                      df["new_offset"].astype(float).tolist()))
    cur = conn.connection.dbapi_connection.cursor()
    try:
        execute_values(cur, "INSERT INTO _cal_new (tag, dt, off) VALUES %s", values, page_size=5000)
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
    delta = df["corrected_value"] - df["current_value"]
    return _ok({
        "station": station,
        "correction_type": ctype,
        "parameters": params,
        "offset_applied": params.get("offset"),
        "start_datetime": start.isoformat(),
        "end_datetime": end.isoformat(),
        "rows_affected": int(len(df)),
        "change_summary": {"min": float(delta.min()), "max": float(delta.max()), "mean": float(delta.mean())},
        "data": [
            {"Tab_DateTime": str(r.Tab_DateTime), "Station": station, "raw_value": r.raw_value,
             "current_value": r.current_value, "corrected_value": r.corrected_value}
            for r in df.itertuples(index=False)
        ],
        "reference_data": refs,
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

        df, params = _compute_targets(conn, body, station, start, end, ctype, reference)
        df["new_offset"] = df["corrected_value"] - df["raw_value"]

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
            INSERT INTO "Calibration_Audit_Rows" ("Audit_Id", "Tab_TabularTag", "Tab_DateTime", "Old_Offset")
            SELECT :aid, n.tag, n.dt, o."Offset"
              FROM _cal_new n
              LEFT JOIN "Calibration_Offsets" o ON o."Tab_TabularTag" = n.tag AND o."Tab_DateTime" = n.dt
        """), {"aid": audit_id})
        conn.execute(text("""
            INSERT INTO "Calibration_Offsets" ("Tab_TabularTag", "Tab_DateTime", "Offset", "Audit_Id")
            SELECT n.tag, n.dt, n.off, :aid FROM _cal_new n
            ON CONFLICT ("Tab_TabularTag", "Tab_DateTime")
            DO UPDATE SET "Offset" = EXCLUDED."Offset", "Audit_Id" = EXCLUDED."Audit_Id"
        """), {"aid": audit_id})
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
            UPDATE "Calibration_Offsets" o SET "Offset" = r."Old_Offset", "Audit_Id" = :rev
              FROM "Calibration_Audit_Rows" r
             WHERE r."Audit_Id" = :a AND r."Old_Offset" IS NOT NULL
               AND o."Tab_TabularTag" = r."Tab_TabularTag" AND o."Tab_DateTime" = r."Tab_DateTime"
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
        # Relative mode with drift detection
        if reference and body.get("expected_gap") is not None:
            gap = _number(body, "expected_gap")
            tgt = _fetch_window(conn, station, start, end)
            ref = _fetch_window(conn, reference, start, end)
            if tgt.empty or ref.empty:
                raise _BadRequest(404, f"Missing data for {station} or {reference} in window")
            merged = tgt.merge(ref[["Tab_DateTime", "current_value"]].rename(columns={"current_value": "ref"}),
                               on="Tab_DateTime", how="inner")
            if merged.empty:
                raise _BadRequest(404, "No overlapping timestamps between stations")
            merged["deviation"] = ((merged["current_value"] - merged["ref"]) - gap).abs()
            drifted = merged[merged["deviation"] > DRIFT_THRESHOLD_M]
            if drifted.empty:
                return _ok({"station": station, "status": "no_drift_detected", "reference_station": reference,
                            "expected_gap": gap,
                            "message": "Delta between stations matches the expected gap throughout the window"})
            first, last = drifted["Tab_DateTime"].min(), drifted["Tab_DateTime"].max()
            return _ok({"station": station, "drift_detected": True, "reference_station": reference,
                        "expected_gap": gap, "malfunction_start": first.isoformat(), "malfunction_end": last.isoformat(),
                        "drift_samples": int(len(drifted)), "max_deviation": float(drifted["deviation"].max()),
                        "message": f"Drift detected: {first} to {last}"})

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
    for suffix, handler in (("/preview", lambda_handler_preview), ("/commit", lambda_handler_commit),
                            ("/suggest", lambda_handler_suggest), ("/revert", lambda_handler_revert),
                            ("/history", lambda_handler_history)):
        if path.endswith(suffix):
            return handler(event, context)
    return _err(404, "Unknown calibration endpoint")
