"""
On-prem PostgreSQL → Aurora replica sync (architect's design: "Lambda / DMS, pull every 1 min").

Runs on an EventBridge schedule. Each run:
  * Monitors_info2: copies rows newer than (Aurora's latest timestamp − overlap). The overlap window
    is replaced (delete + insert in one transaction) so late-arriving or edited on-prem rows are
    picked up and nothing is duplicated, even without a unique key on the source table.
    Corrections are NOT touched: they live in "Calibration_Offsets" (cloud-owned).
  * Locations: small reference table, refreshed when it changes.
  * SeaTides: last few days replaced.
  * First run / catch-up: starts at SYNC_START_DATE and copies at most SYNC_MAX_DAYS_PER_RUN
    days per invocation, so a large history fills in over consecutive runs.

Environment:
  ONPREM_SECRET_ARN   Secrets Manager secret {host, port, dbname, username, password} — read-only user
  DB_SECRET_ARN       Aurora writer secret for the sync user (INSERT/DELETE on replica tables only)
  SYNC_OVERLAP_MINUTES (default 15) · SYNC_START_DATE (default 2020-01-01) · SYNC_MAX_DAYS_PER_RUN (default 7)

Network: the function runs in the VPC and reaches the on-prem server over the company's
Site-to-Site VPN / Direct Connect. If that link is not available, use AWS DMS (CDC) instead.
"""
import json
import logging
import os
import time
from datetime import datetime, timedelta

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

logger = logging.getLogger()
logger.setLevel(logging.INFO)

OVERLAP = timedelta(minutes=int(os.getenv("SYNC_OVERLAP_MINUTES", "15")))
START = datetime.fromisoformat(os.getenv("SYNC_START_DATE", "2020-01-01"))
MAX_SPAN = timedelta(days=int(os.getenv("SYNC_MAX_DAYS_PER_RUN", "7")))
SKIP_COLUMNS = {"Calibration_Offset"}  # legacy in-table corrections never flow from on-prem


def _connect(secret_arn, app_name):
    import boto3
    s = json.loads(boto3.client("secretsmanager").get_secret_value(SecretId=secret_arn)["SecretString"])
    return psycopg2.connect(host=s["host"], port=s.get("port", 5432), dbname=s.get("dbname"), user=s["username"],
                            password=s["password"], connect_timeout=10, sslmode=os.getenv("SYNC_SSLMODE", "prefer"),
                            application_name=app_name, options="-c statement_timeout=240000")


def _columns(cur, table):
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s "
                "AND table_schema = current_schema() ORDER BY ordinal_position", (table,))
    return [r[0] for r in cur.fetchall()]


def _common_columns(src, dst, table):
    with src.cursor() as a, dst.cursor() as b:
        dst_cols = set(_columns(b, table))
        return [c for c in _columns(a, table) if c in dst_cols and c not in SKIP_COLUMNS]


def _copy_range(src, dst, table, time_col, lo, hi, cols):
    """Replace dst rows with lo < time_col <= hi by the source rows, atomically."""
    col_list = sql.SQL(", ").join(map(sql.Identifier, cols))
    with src.cursor(name=f"sync_{table}") as rc:  # server-side cursor: constant memory
        rc.itersize = 10000
        rc.execute(sql.SQL("SELECT {} FROM {} WHERE {} > %s AND {} <= %s").format(
            col_list, sql.Identifier(table), sql.Identifier(time_col), sql.Identifier(time_col)), (lo, hi))
        with dst.cursor() as wc:
            wc.execute(sql.SQL("DELETE FROM {} WHERE {} > %s AND {} <= %s").format(
                sql.Identifier(table), sql.Identifier(time_col), sql.Identifier(time_col)), (lo, hi))
            insert = sql.SQL("INSERT INTO {} ({}) VALUES %s").format(sql.Identifier(table), col_list).as_string(wc)
            total = 0
            while True:
                batch = rc.fetchmany(10000)
                if not batch:
                    break
                execute_values(wc, insert, batch, page_size=5000)
                total += len(batch)
    return total


def sync_monitors(src, dst):
    cols = _common_columns(src, dst, "Monitors_info2")
    with dst.cursor() as c:
        c.execute('SELECT max("Tab_DateTime") FROM "Monitors_info2"')
        latest = c.fetchone()[0]
    with src.cursor() as c:
        c.execute('SELECT max("Tab_DateTime") FROM "Monitors_info2"')
        source_latest = c.fetchone()[0]
    if source_latest is None:
        return {"rows": 0, "note": "source empty"}
    lo = (latest - OVERLAP) if latest else START
    hi = min(source_latest, lo + MAX_SPAN + OVERLAP)
    rows = _copy_range(src, dst, "Monitors_info2", "Tab_DateTime", lo, hi, cols)
    return {"rows": rows, "from": lo.isoformat(), "to": hi.isoformat(), "caught_up": hi >= source_latest}


def sync_locations(src, dst):
    cols = _common_columns(src, dst, "Locations")
    col_list = sql.SQL(", ").join(map(sql.Identifier, cols))
    q = sql.SQL("SELECT {} FROM {} ORDER BY 1").format(col_list, sql.Identifier("Locations"))
    with src.cursor() as a, dst.cursor() as b:
        a.execute(q)
        src_rows = a.fetchall()
        b.execute(q)
        if b.fetchall() == src_rows:
            return {"changed": False}
        b.execute('DELETE FROM "Locations"')
        execute_values(b, sql.SQL("INSERT INTO {} ({}) VALUES %s").format(
            sql.Identifier("Locations"), col_list).as_string(b), src_rows)
    return {"changed": True, "rows": len(src_rows)}


def sync_tides(src, dst):
    cols = _common_columns(src, dst, "SeaTides")
    if not cols:
        return {"skipped": True}
    lo = datetime.now() - timedelta(days=3)
    hi = datetime.now() + timedelta(days=400)  # tide tables are published ahead
    return {"rows": _copy_range(src, dst, "SeaTides", "Date", lo, hi, cols)}


def handler(event, context):
    started = time.time()
    src = _connect(os.environ["ONPREM_SECRET_ARN"], "sealevel-sync-reader")
    dst = _connect(os.environ["DB_SECRET_ARN"], "sealevel-sync-writer")
    try:
        src.set_session(readonly=True)
        result = {}
        for name, fn in (("monitors", sync_monitors), ("locations", sync_locations), ("tides", sync_tides)):
            try:
                result[name] = fn(src, dst)
                dst.commit()
            except Exception:
                dst.rollback()
                logger.exception("sync step %s failed", name)
                result[name] = {"error": True}
        result["seconds"] = round(time.time() - started, 2)
        logger.info(json.dumps({"sync": result}, default=str))
        if any(isinstance(v, dict) and v.get("error") for v in result.values()):
            raise RuntimeError("sync failed — see logs")  # surfaces as a Lambda error → CloudWatch alarm
        return result
    finally:
        src.close()
        dst.close()
