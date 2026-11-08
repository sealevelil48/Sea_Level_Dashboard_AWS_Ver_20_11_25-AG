"""
Run database migrations and provision least-privilege login users. Invoked once per deploy.

Uses the Aurora master secret (MASTER_SECRET_ARN). For each app secret it creates/updates a
LOGIN user with the secret's password and grants the matching group role from 004_app_roles.sql:
  READER_SECRET_ARN → sealevel_reader · CALIBRATOR_SECRET_ARN → sealevel_calibrator · SYNC_SECRET_ARN → sealevel_sync

The replica tables (Monitors_info2, Locations, SeaTides) must already exist — they come from the
initial load of the on-prem database (pg_dump --schema-only, or the DMS full load).
"""
import json
import logging
import os
from pathlib import Path

import psycopg2
from psycopg2 import sql

logger = logging.getLogger()
logger.setLevel(logging.INFO)

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
ORDER = ["add_performance_indexes.sql", "003_calibration_layer.sql", "004_app_roles.sql"]
USERS = {"READER_SECRET_ARN": "sealevel_reader", "CALIBRATOR_SECRET_ARN": "sealevel_calibrator",
         "SYNC_SECRET_ARN": "sealevel_sync"}


def _secret(arn):
    import boto3
    return json.loads(boto3.client("secretsmanager").get_secret_value(SecretId=arn)["SecretString"])


def handler(event, context):
    master = _secret(os.environ["MASTER_SECRET_ARN"])
    conn = psycopg2.connect(host=master["host"], port=master.get("port", 5432), user=master["username"],
                            password=master["password"], dbname=os.getenv("DB_NAME", "sealevel"), sslmode="require")
    conn.autocommit = True
    applied = []
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('\"Monitors_info2\"')")
        if cur.fetchone()[0] is None:
            raise RuntimeError("Monitors_info2 not found — run the initial on-prem load first (see docs/aws/DEPLOYMENT.md)")
        for name in ORDER:
            cur.execute((MIGRATIONS / name).read_text())
            applied.append(name)
        for env_name, group in USERS.items():
            if not os.getenv(env_name):
                continue
            s = _secret(os.environ[env_name])
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (s["username"],))
            verb = "ALTER" if cur.fetchone() else "CREATE"
            cur.execute(sql.SQL(verb + " ROLE {} LOGIN PASSWORD %s").format(sql.Identifier(s["username"])), (s["password"],))
            cur.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(group), sql.Identifier(s["username"])))
            applied.append(f"user:{s['username']}→{group}")
    conn.close()
    logger.info("migrations applied: %s", applied)
    return {"applied": applied}
