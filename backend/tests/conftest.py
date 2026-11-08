"""Shared pytest setup: import paths + an optional real PostgreSQL (TEST_DB_URI)."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

TEST_DB_URI = os.getenv("TEST_DB_URI")
if TEST_DB_URI:
    os.environ["DB_URI"] = TEST_DB_URI
os.environ.setdefault("REDIS_ENABLED", "false")
os.environ.setdefault("ADMIN_EMAILS", "benp@mapi.gov.il")


def _psql(uri, sql_file):
    from sqlalchemy import create_engine
    eng = create_engine(uri)
    raw = eng.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute(Path(sql_file).read_text())
        raw.commit()
    finally:
        raw.close()
        eng.dispose()


@pytest.fixture(scope="session")
def database():
    """Fresh synthetic dataset + all migrations. Skips when no TEST_DB_URI is configured."""
    if not TEST_DB_URI:
        pytest.skip("TEST_DB_URI not set (needs PostgreSQL)")
    _psql(TEST_DB_URI, BACKEND / "tests" / "fixtures" / "schema.sql")
    _psql(TEST_DB_URI, BACKEND / "migrations" / "add_calibration_offset.sql")
    _psql(TEST_DB_URI, BACKEND / "migrations" / "003_calibration_layer.sql")
    return TEST_DB_URI
