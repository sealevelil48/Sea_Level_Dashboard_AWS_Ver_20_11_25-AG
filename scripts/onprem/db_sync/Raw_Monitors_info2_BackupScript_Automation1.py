"""
SSMS (contractor SQL Server, read-only) -> PostgreSQL "Monitors_info2", every minute.

Normal run:      python Raw_Monitors_info2_BackupScript_Automation1.py
One-time refill: python Raw_Monitors_info2_BackupScript_Automation1.py --backfill-from 2024-01-01
                 (re-reads SSMS from that date, adds every valid row that is missing, then exits.
                  Safe to run while the normal sync is running.)
"""
import os
import sys
import time
import argparse
import logging
import configparser
from datetime import datetime, timedelta

import pyodbc
import psycopg2
from psycopg2 import pool
from psycopg2.extras import execute_values

# -----------------------------
# Active Stations Configuration
# -----------------------------
# Map station names to the exact TabularTag. Comment out a line to ignore that station.
ACTIVE_STATIONS = {
    "Acre":     "a100m1",
    # "Haifa":    "a98m1",     # Currently disabled
    "Yafo":     "a93m1",
    "Ashdod":   "a99m1",
    "Ashkelon": "a97_m1",
    "Eilat":    "a101m1",
}

START_DATE_IF_EMPTY = datetime(2024, 1, 1)  # used when a station has no rows in PostgreSQL yet
BATCH_SIZE = 5000                           # rows per fetch/insert (keeps memory low on first run)
SLEEP_SECONDS = 60

# Stations send data late and in bursts, and the logger can fill old gaps later.
# So every cycle re-reads a window BEFORE the newest row we already have (existing rows are ignored).
RECENT_LOOKBACK = timedelta(hours=3)        # every minute
DEEP_CHECK_DAYS = 14                        # at start and every DEEP_CHECK_EVERY
DEEP_CHECK_EVERY = timedelta(hours=6)

# Columns allowed to be empty (NULL) - NaN is still never stored, it becomes NULL.
# ()                       -> strict: a row is skipped if ANY column is missing (current setting)
# ("Tab_Value_monT2m",)    -> keep sea-level rows even when only the temperature is missing
OPTIONAL_COLUMNS = ()

# -----------------------------
# Table layout
# -----------------------------
PG_TABLE = "Monitors_info2"
REJECTED_TABLE = "Monitors_info2_rejected"   # bad/duplicate rows found in the table are moved here, not lost
COLUMNS = [
    "Tab_DateTime",         # 0
    "Tab_Value_mDepth",     # 1
    "Tab_TabularTag",       # 2
    "Tab_DateTime_Source",  # 3
    "Tab_Value_mDepthC1",   # 4
    "Tab_Value_monT2m",     # 5
]
NUMERIC_COLUMNS = (1, 4, 5)
# A duplicate = same station + same timestamp
KEY_COLUMNS = ("Tab_TabularTag", "Tab_DateTime")
UNIQUE_INDEX = "ux_monitors_info2_tag_time"
NO_NAN_CHECK = "chk_monitors_info2_no_nan"

_bad_optional = [c for c in OPTIONAL_COLUMNS if c not in COLUMNS or c in KEY_COLUMNS]
if _bad_optional:
    raise SystemExit(f"OPTIONAL_COLUMNS can't contain {_bad_optional} (unknown column or station/time key)")
REQUIRED_COLUMNS = [c for c in COLUMNS if c not in OPTIONAL_COLUMNS]

# -----------------------------
# Paths (always relative to this script, not to wherever it was launched from)
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.ini")
# The continuous sync and the weekly backfill run at the same time, so each gets its own log file
# (two processes must never rotate the same file on Windows).
_BACKFILL_RUN = any(a.startswith("--backfill-from") for a in sys.argv[1:])
LOG_PATH = os.path.join(BASE_DIR, "sql_to_pg_backfill.log" if _BACKFILL_RUN else "sql_to_pg_sync.log")
LOG_MAX_BYTES = 10 * 1024 * 1024   # 10 MB per file
LOG_BACKUPS = 5                    # keeps ~2 weeks of the 1-minute sync log, never more than 60 MB

# -----------------------------
# Logging
# -----------------------------
from logging.handlers import RotatingFileHandler  # noqa: E402

_file_handler = RotatingFileHandler(LOG_PATH, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUPS, encoding="utf-8")
_file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s"))
# The .bat redirects the console into logs\*_run.log: only warnings/errors go there, so it stays small.
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_file_handler, console_handler])

# -----------------------------
# Configuration
# -----------------------------
config = configparser.ConfigParser()
if not config.read(CONFIG_PATH, encoding="utf-8"):
    logging.error(f"config.ini not found at {CONFIG_PATH}")
    sys.exit(1)

for section in ("postgresql", "sqlserver"):
    if section not in config:
        logging.error(f"Section [{section}] missing from config.ini")
        sys.exit(1)


def cfg(section, key, default=None):
    """Read a config value and strip accidental quotes/spaces ('FUJITSU' -> FUJITSU)."""
    value = config[section].get(key, default)
    if value is None:
        logging.error(f"Missing key '{key}' in [{section}] of config.ini")
        sys.exit(1)
    return value.strip().strip("'\"")


PG = {k: cfg("postgresql", k) for k in ("dbname", "user", "password", "host", "port")}
SQL = {k: cfg("sqlserver", k) for k in ("host", "dbname", "user", "password", "schema", "table")}
SQL["driver"] = cfg("sqlserver", "driver", "")

PREFERRED_DRIVERS = [
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server",  # old driver built into Windows - works as a last resort
]


def pick_driver():
    installed = pyodbc.drivers()
    if SQL["driver"]:
        if SQL["driver"] in installed:
            return SQL["driver"]
        logging.warning(f"Configured driver '{SQL['driver']}' not installed. Installed: {installed}")
    for d in PREFERRED_DRIVERS:
        if d in installed:
            return d
    logging.error(f"No SQL Server ODBC driver found. Installed drivers: {installed}")
    sys.exit(1)


ODBC_DRIVER = pick_driver()


def odbc_escape(value):
    """Wrap a value in braces so characters like ; = } in passwords don't break the connection string."""
    return "{" + value.replace("}", "}}") + "}"


def q(name):
    """Quote a PostgreSQL identifier."""
    return '"' + name.replace('"', '""') + '"'


# -----------------------------
# Database Connections
# -----------------------------
def get_sql_server_conn():
    """Connect read-only to the contractor's SQL Server with the viewer account."""
    try:
        parts = [
            f"DRIVER={{{ODBC_DRIVER}}}",
            f"SERVER={SQL['host']}",
            f"DATABASE={SQL['dbname']}",
            f"UID={SQL['user']}",
            f"PWD={odbc_escape(SQL['password'])}",
        ]
        if ODBC_DRIVER.startswith("ODBC Driver"):
            # Driver 18 encrypts by default and rejects self-signed certs on internal servers
            parts.append("TrustServerCertificate=yes")
        return pyodbc.connect(";".join(parts) + ";", timeout=15, readonly=True)
    except Exception as e:
        logging.error(f"Failed to connect to SQL Server ({ODBC_DRIVER}): {e}")
        return None


def _create_pg_pool(attempts=20, wait_seconds=30):
    """At boot PostgreSQL may start after this task: wait for it (default up to 10 minutes) instead of dying."""
    for attempt in range(1, attempts + 1):
        try:
            p = pool.SimpleConnectionPool(
                1, 5,
                dbname=PG["dbname"], user=PG["user"], password=PG["password"],
                host=PG["host"], port=PG["port"], connect_timeout=15,
            )
            logging.info("PostgreSQL pool created successfully")
            return p
        except Exception as e:
            logging.error(f"Failed to create PostgreSQL pool (attempt {attempt}/{attempts}): {e}")
            if attempt == attempts:
                raise
            time.sleep(wait_seconds)


pg_pool = _create_pg_pool()


# -----------------------------
# One-time table protection (runs at every start, safe to repeat)
# -----------------------------
def enforce_table_rules():
    """
    Make PostgreSQL itself refuse bad data in Monitors_info2:
      1. Move rows with NULL / NaN / Infinity in a required column to Monitors_info2_rejected
         (NaN in an OPTIONAL column just becomes NULL)
      2. Move duplicate rows (same station + same timestamp, keeping one) to Monitors_info2_rejected
      3. UNIQUE index on (station, time), NOT NULL on required columns, CHECK against NaN/Infinity
      4. If OPTIONAL_COLUMNS is set: put back rejected rows whose only problem was an optional column
    Fast on every start after the first one: the full-table cleanup only runs when a rule is missing.
    """
    conn = pg_pool.getconn()
    try:
        with conn.cursor() as cur:
            # Don't wait forever if another session (e.g. an unfinished DELETE) holds the table
            cur.execute("SET lock_timeout = '30s'")

            cur.execute(
                """SELECT column_name, data_type, is_nullable FROM information_schema.columns
                   WHERE table_schema = current_schema() AND table_name = %s""",
                (PG_TABLE,),
            )
            info = {name: (dtype, nullable == "YES") for name, dtype, nullable in cur.fetchall()}
            if not info:
                raise RuntimeError(f'Table "{PG_TABLE}" not found in PostgreSQL database {PG["dbname"]}')
            missing = [c for c in COLUMNS if c not in info]
            if missing:
                raise RuntimeError(f'Columns missing from "{PG_TABLE}": {missing}')

            float_types = ("double precision", "real", "numeric")
            text_types = ("text", "character varying", "character")
            num_cols = [c for c in COLUMNS if info[c][0] in float_types]
            txt_cols = [c for c in COLUMNS if info[c][0] in text_types]

            def is_bad(c, alias=""):
                """SQL condition: column c holds a missing/invalid value."""
                col = alias + q(c)
                cond = [f"{col} IS NULL"]
                if c in num_cols:
                    cond.append(f"{col} IN ('NaN', 'Infinity', '-Infinity')")
                if c in txt_cols:
                    cond.append(f"btrim({col}) IN ('', 'NAN', 'NaN', 'nan', '\"NAN\"', 'NULL')")
                return "(" + " OR ".join(cond) + ")"

            def cleaned(c, alias=""):
                """SQL expression: the value of c, with NaN/junk turned into NULL."""
                col = alias + q(c)
                if c in num_cols:
                    return f"CASE WHEN {col} IN ('NaN', 'Infinity', '-Infinity') THEN NULL ELSE {col} END"
                if c in txt_cols:
                    return f"CASE WHEN btrim({col}) IN ('', 'NAN', 'NaN', 'nan', '\"NAN\"', 'NULL') THEN NULL ELSE {col} END"
                return col

            cols = ", ".join(q(c) for c in COLUMNS)
            t, rej = q(PG_TABLE), q(REJECTED_TABLE)
            k1, k2 = (q(c) for c in KEY_COLUMNS)

            # Any unique index / primary key on exactly (station, time) counts - whatever its name
            cur.execute(
                """SELECT i.indexrelid::regclass::text
                   FROM pg_index i
                   WHERE i.indrelid = %s::regclass AND i.indisunique AND i.indisvalid
                     AND i.indpred IS NULL AND i.indexprs IS NULL AND i.indnatts = 2
                     AND (SELECT array_agg(a.attname::text ORDER BY a.attname::text)
                          FROM pg_attribute a
                          WHERE a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)) = %s""",
                (t, sorted(KEY_COLUMNS)),
            )
            row = cur.fetchone()
            existing_unique = row[0] if row else None
            cur.execute("SELECT 1 FROM pg_constraint WHERE conname = %s", (NO_NAN_CHECK,))
            has_check = cur.fetchone() is not None

            required_nullable = [c for c in REQUIRED_COLUMNS if info[c][1]]
            optional_not_null = [c for c in OPTIONAL_COLUMNS if not info[c][1]]
            rules_ok = (existing_unique and (has_check or not num_cols)
                        and not required_nullable and not optional_not_null)

            bad_moved = dup_moved = 0
            if rules_ok:
                logging.info(f'Table rules already active on "{PG_TABLE}"')
            else:
                logging.info(f'Setting up protection of "{PG_TABLE}": cleaning and adding rules. '
                             f'On a large table this can take several minutes, please wait...')

                # Holding table for anything we remove, so nothing is silently lost
                cur.execute(f"CREATE TABLE IF NOT EXISTS {rej} AS SELECT {cols} FROM {t} WITH NO DATA")
                cur.execute(
                    f"ALTER TABLE {rej} ADD COLUMN IF NOT EXISTS rejected_reason text, "
                    f"ADD COLUMN IF NOT EXISTS rejected_at timestamp DEFAULT now()"
                )

                # Optional columns first need to accept NULL
                for c in optional_not_null:
                    cur.execute(f"ALTER TABLE {t} ALTER COLUMN {q(c)} DROP NOT NULL")

                # NaN / junk in an optional column -> NULL (the row itself is fine)
                for c in OPTIONAL_COLUMNS:
                    if c in num_cols or c in txt_cols:
                        cur.execute(f"UPDATE {t} SET {q(c)} = NULL WHERE {is_bad(c)} AND {q(c)} IS NOT NULL")

                # 1. Rows with a missing/invalid REQUIRED value
                bad_where = " OR ".join(is_bad(c) for c in REQUIRED_COLUMNS)
                cur.execute(f"""
                    WITH moved AS (DELETE FROM {t} WHERE {bad_where} RETURNING {cols})
                    INSERT INTO {rej} ({cols}, rejected_reason)
                    SELECT {cols}, 'null_or_nan' FROM moved
                """)
                bad_moved = cur.rowcount

                # 2. Duplicates (same station + timestamp): keep the first physical row.
                #    Skipped when a unique index already exists - duplicates are impossible then.
                if not existing_unique:
                    cur.execute(f"""
                        WITH moved AS (
                            DELETE FROM {t}
                            WHERE ctid IN (
                                SELECT ctid FROM (
                                    SELECT ctid, row_number() OVER (PARTITION BY {k1}, {k2} ORDER BY ctid) AS rn
                                    FROM {t}
                                ) d WHERE d.rn > 1
                            )
                            RETURNING {cols}
                        )
                        INSERT INTO {rej} ({cols}, rejected_reason)
                        SELECT {cols}, 'duplicate' FROM moved
                    """)
                    dup_moved = cur.rowcount

                # 3. Database-level rules
                if existing_unique:
                    logging.info(f"Using your existing unique index {existing_unique} on ({', '.join(KEY_COLUMNS)})")
                else:
                    cur.execute(f"CREATE UNIQUE INDEX {q(UNIQUE_INDEX)} ON {t} ({k1}, {k2})")
                for c in required_nullable:
                    cur.execute(f"ALTER TABLE {t} ALTER COLUMN {q(c)} SET NOT NULL")
                if num_cols and not has_check:
                    # NULL passes this check (NULL is handled by NOT NULL), NaN/Infinity never do
                    check = " AND ".join(f"{q(c)} NOT IN ('NaN', 'Infinity', '-Infinity')" for c in num_cols)
                    cur.execute(f"ALTER TABLE {t} ADD CONSTRAINT {q(NO_NAN_CHECK)} CHECK ({check})")

            # 4. Put back rejected rows whose only problem was an optional column
            restored = 0
            if OPTIONAL_COLUMNS:
                cur.execute("SELECT to_regclass(%s)", (rej,))
                if cur.fetchone()[0]:
                    valid = " AND ".join(f"NOT {is_bad(c, 'r.')}" for c in REQUIRED_COLUMNS)
                    exprs = ", ".join(cleaned(c, "r.") for c in COLUMNS)
                    cur.execute(f"""
                        WITH ins AS (
                            INSERT INTO {t} ({cols})
                            SELECT {exprs} FROM {rej} r
                            WHERE r.rejected_reason = 'null_or_nan' AND {valid}
                            ON CONFLICT ({k1}, {k2}) DO NOTHING
                            RETURNING {k1}, {k2}
                        )
                        DELETE FROM {rej} r USING ins
                        WHERE r.{k1} = ins.{k1} AND r.{k2} = ins.{k2} AND r.rejected_reason = 'null_or_nan'
                    """)
                    restored = cur.rowcount

        conn.commit()
        if bad_moved or dup_moved:
            logging.warning(
                f'Cleaned "{PG_TABLE}": moved {bad_moved} NULL/NaN rows and {dup_moved} duplicate rows '
                f'to "{REJECTED_TABLE}"'
            )
        if restored:
            logging.warning(f'Restored {restored} rows from "{REJECTED_TABLE}" '
                            f'(their only problem was in {", ".join(OPTIONAL_COLUMNS)} - now NULL there)')
        opt = f", may be empty: {', '.join(OPTIONAL_COLUMNS)}" if OPTIONAL_COLUMNS else ", no empty values"
        logging.info(f'Rules on "{PG_TABLE}": unique ({", ".join(KEY_COLUMNS)}), no NaN{opt}')
    except Exception:
        conn.rollback()
        raise
    finally:
        pg_pool.putconn(conn)


# -----------------------------
# Row cleaning (before anything is sent to PostgreSQL)
# -----------------------------
MISSING_TEXT = {"", "nan", "null", "none", "n/a"}


def to_float(value):
    """'0.041' -> 0.041 ; '"NAN"', '', None, 'abc', nan, inf -> None (invalid)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        f = float(value)
    else:
        text = str(value).strip().strip("'\"").strip()
        try:
            f = float(text)
        except ValueError:
            return None
    if f != f or f in (float("inf"), float("-inf")):  # NaN or infinity
        return None
    return f


def clean_other(value):
    """Non-numeric columns: strip stray quotes; treat empty/'NAN'/'NULL' text as missing."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip().strip("'\"").strip()
        return None if text.lower() in MISSING_TEXT else text
    return value


def clean_row(row):
    """Return a clean tuple, or None if a REQUIRED column is missing/invalid (the whole row is skipped).
    Optional columns with a missing/NaN value become None (NULL)."""
    values = []
    for i, v in enumerate(row):
        v = to_float(v) if i in NUMERIC_COLUMNS else clean_other(v)
        if v is None and COLUMNS[i] not in OPTIONAL_COLUMNS:
            return None
        values.append(v)
    return tuple(values)


# -----------------------------
# Sync Logic
# -----------------------------
# Invalid source rows we already reported, so the look-back window doesn't report them every minute
REPORTED_INVALID = {}   # station tag -> set of timestamps


def get_latest_timestamp_for_station(pg_conn, station_tag):
    """Most recent timestamp already in PostgreSQL for this station."""
    try:
        with pg_conn.cursor() as cur:
            cur.execute(
                f'SELECT MAX("Tab_DateTime") FROM {q(PG_TABLE)} WHERE "Tab_TabularTag" = %s;',
                (station_tag,),
            )
            result = cur.fetchone()[0]
        pg_conn.commit()
        return result if result else START_DATE_IF_EMPTY
    except Exception as e:
        pg_conn.rollback()  # otherwise the aborted transaction blocks every later query
        logging.error(f"Error getting last sync time for {station_tag}: {e}")
        return None


BACKFILL_CHUNK = timedelta(days=30)   # backfill reads SSMS one month at a time (progress + lighter load)


def copy_range(sql_conn, pg_conn, station_tag, since, until, last):
    """Read one station from SSMS for [since, until) (until=None -> up to now) and insert missing rows.
    Returns counts: new (newer than `last`), filled (older than `last` but missing), invalid, dups, checked."""
    # To keep only every 10 minutes, add:  AND DATEPART(MINUTE, Tab_DateTime) % 10 = 0
    sql_query = f"""
        SELECT Tab_DateTime, Tab_Value_mDepth, Tab_TabularTag,
               Tab_DateTime_Source, Tab_Value_mDepthC1, Tab_Value_monT2m
        FROM [{SQL['schema']}].[{SQL['table']}]
        WHERE Tab_TabularTag = ? AND Tab_DateTime >= ?{" AND Tab_DateTime < ?" if until else ""}
        ORDER BY Tab_DateTime ASC
    """
    cols = ", ".join(q(c) for c in COLUMNS)
    insert_query = f"""
        INSERT INTO {q(PG_TABLE)} ({cols})
        VALUES %s
        ON CONFLICT ({", ".join(q(c) for c in KEY_COLUMNS)}) DO NOTHING
        RETURNING "Tab_DateTime"
    """
    sql_cursor = sql_conn.cursor()
    sql_cursor.execute(sql_query, (station_tag, since, until) if until else (station_tag, since))

    reported = REPORTED_INVALID.setdefault(station_tag, set())
    c = dict(new=0, filled=0, invalid=0, dups=0, checked=0)
    while True:
        rows = sql_cursor.fetchmany(BATCH_SIZE)
        if not rows:
            break
        c["checked"] += len(rows)
        data, batch_keys = [], set()
        for r in rows:
            row = clean_row(r)
            if row is None:
                if r[0] not in reported:
                    reported.add(r[0])
                    c["invalid"] += 1
                continue
            if row[0] in batch_keys:
                c["dups"] += 1
                continue
            batch_keys.add(row[0])
            data.append(row)

        if data:
            with pg_conn.cursor() as pg_cursor:
                inserted_times = execute_values(pg_cursor, insert_query, data,
                                                page_size=len(data), fetch=True)
            pg_conn.commit()  # commit per batch so progress survives a crash
            for (ts,) in inserted_times:
                if ts > last:
                    c["new"] += 1
                else:
                    c["filled"] += 1   # older than our newest row but was missing -> late or gap
    sql_cursor.close()
    return c


def describe(c):
    parts = [f"{c['new']} new"]
    if c["filled"]:
        parts.append(f"filled {c['filled']} missing/late rows")
    if c["invalid"]:
        parts.append(f"skipped {c['invalid']} rows with NULL/NaN")
    if c["dups"]:
        parts.append(f"{c['dups']} duplicate rows in source ignored")
    return ", ".join(parts)


def sync_station(sql_conn, pg_conn, station_name, station_tag, mode="recent", backfill_from=None):
    """
    mode "recent":   re-read the last RECENT_LOOKBACK before our newest row (every minute)
    mode "deep":     re-read the last DEEP_CHECK_DAYS (at start and every DEEP_CHECK_EVERY)
    mode "backfill": re-read everything since backfill_from, one month at a time, with progress
    Rows that already exist are ignored, so only new AND missing/late rows are inserted.
    """
    last = get_latest_timestamp_for_station(pg_conn, station_tag)
    if last is None:
        return 0
    reported = REPORTED_INVALID.setdefault(station_tag, set())

    if mode == "backfill":
        logging.info(f"{station_name}: backfill from {backfill_from:%Y-%m-%d}, one month at a time...")
        total = dict(new=0, filled=0, invalid=0, dups=0, checked=0)
        start = backfill_from
        while True:
            end = start + BACKFILL_CHUNK
            is_last_chunk = end > last
            c = copy_range(sql_conn, pg_conn, station_tag, start, None if is_last_chunk else end, last)
            for k in total:
                total[k] += c[k]
            shown_end = "now" if is_last_chunk else f"{end:%Y-%m-%d}"
            logging.info(f"   {station_name} {start:%Y-%m-%d} -> {shown_end}: "
                         f"checked {c['checked']}, " + describe(c))
            if is_last_chunk:
                break
            start = end
        logging.info(f"{station_name}: BACKFILL TOTAL checked {total['checked']}, " + describe(total))
        return total["new"] + total["filled"]

    since = last - (timedelta(days=DEEP_CHECK_DAYS) if mode == "deep" else RECENT_LOOKBACK)
    c = copy_range(sql_conn, pg_conn, station_tag, since, None, last)

    # forget reported invalid rows that are far outside any window we still read
    cutoff = last - timedelta(days=DEEP_CHECK_DAYS + 1)
    reported.difference_update({ts for ts in reported if ts < cutoff})

    if c["new"] or c["filled"] or c["invalid"] or c["dups"]:
        logging.info(f"{station_name}: " + describe(c))
    return c["new"] + c["filled"]


def sync_databases(mode="recent", backfill_from=None):
    sql_conn = get_sql_server_conn()
    if not sql_conn:
        logging.error("No SQL Server connection. Skipping cycle.")
        return

    pg_conn = pg_pool.getconn()
    pg_conn.autocommit = False
    total = 0
    try:
        for station_name, station_tag in ACTIVE_STATIONS.items():
            try:
                total += sync_station(sql_conn, pg_conn, station_name, station_tag, mode, backfill_from)
            except Exception as e:
                pg_conn.rollback()
                logging.error(f"Error syncing {station_name}: {e}")
        if total or mode != "recent":
            label = {"recent": "Cycle", "deep": f"Deep check ({DEEP_CHECK_DAYS} days)",
                     "backfill": "Backfill"}[mode]
            logging.info(f"{label} done: {total} rows added across active stations.")
    finally:
        sql_conn.close()
        pg_pool.putconn(pg_conn)


def main():
    parser = argparse.ArgumentParser(description="Sync SSMS -> PostgreSQL Monitors_info2")
    parser.add_argument("--backfill-from", metavar="YYYY-MM-DD",
                        help="one-time: re-read SSMS from this date, add all missing valid rows, then exit")
    args = parser.parse_args()
    backfill_from = None
    if args.backfill_from:
        try:
            backfill_from = datetime.strptime(args.backfill_from, "%Y-%m-%d")
        except ValueError:
            logging.error("--backfill-from must look like 2024-01-01")
            sys.exit(1)

    logging.info("=" * 50)
    logging.info("Starting SQL Server to PostgreSQL Sync Service"
                 + (f" - BACKFILL from {backfill_from:%Y-%m-%d}" if backfill_from else ""))
    logging.info(f"ODBC driver: {ODBC_DRIVER}")
    logging.info(f"Active Stations: {list(ACTIVE_STATIONS.keys())}")
    logging.info("=" * 50)

    try:
        enforce_table_rules()
    except Exception as e:
        logging.error(f"Could not apply table rules (no NULL / NaN / duplicates): {e}")
        if "lock timeout" in str(e).lower():
            logging.error("Another session is holding the table (maybe an old DELETE that never finished). "
                          "Run BLOCK 0 in check_tables.sql to find and stop it.")
        logging.error("Stopping so no bad data can be written. Fix the error above and run again.")
        sys.exit(1)

    if backfill_from:
        sync_databases("backfill", backfill_from)
        logging.info("Backfill finished.")
        return

    last_deep = None
    while True:
        try:
            if last_deep is None or datetime.now() - last_deep >= DEEP_CHECK_EVERY:
                sync_databases("deep")
                last_deep = datetime.now()
            else:
                sync_databases("recent")
            time.sleep(SLEEP_SECONDS)
        except KeyboardInterrupt:
            logging.info("Shutting down gracefully...")
            break
        except Exception as e:
            logging.error(f"Critical error in main loop: {e}")
            time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()