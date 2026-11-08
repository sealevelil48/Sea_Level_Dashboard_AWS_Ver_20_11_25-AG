"""Calibration service against a real PostgreSQL (see conftest.database)."""
import json
import uuid

import pytest

ADMIN = {"sub": "admin-1", "email": "benp@mapi.gov.il", "email_verified": "true"}
CLIENT = {"sub": "client-1", "email": "client@example.com", "email_verified": "true"}
WINDOW = {"station": "Haifa", "start_datetime": "2026-10-08T12:00", "end_datetime": "2026-10-08T18:00"}
PROBE = "2026-10-08 15:00"


@pytest.fixture(scope="module")
def cal(database):
    from lambdas.calibration import main
    assert main.DATABASE_AVAILABLE
    return main


def call(handler, body, claims=ADMIN):
    event = {"body": json.dumps(body)}
    if claims:
        event["requestContext"] = {"authorizer": {"claims": claims}}
    resp = handler(event, None)
    return resp["statusCode"], json.loads(resp["body"])


def value(cal, station="Haifa", ts=PROBE):
    from sqlalchemy import text
    with cal.engine.connect() as c:
        return c.execute(text('SELECT m."Tab_Value_mDepthC1" FROM "Monitors_effective" m JOIN "Locations" l '
                              'USING ("Tab_TabularTag") WHERE l."Station" = :s AND m."Tab_DateTime" = :t'),
                         {"s": station, "t": ts}).scalar()


def rid():
    return str(uuid.uuid4())


def test_requires_sign_in_and_admin(cal):
    assert call(cal.lambda_handler_preview, WINDOW, claims=None)[0] == 401
    assert call(cal.lambda_handler_preview, WINDOW, claims=CLIENT)[0] == 403
    assert call(cal.lambda_handler_commit, {**WINDOW, "offset": 1, "request_id": rid()}, claims=CLIENT)[0] == 403


def test_unverified_admin_email_is_not_admin(cal):
    assert call(cal.lambda_handler_preview, WINDOW, claims={**ADMIN, "email_verified": "false"})[0] == 403


def test_suggest_finds_plateau(cal):
    status, body = call(cal.lambda_handler_suggest, WINDOW)
    assert status == 200
    assert body["suggested_offset"] == pytest.approx(-0.20, abs=0.01)
    assert body["confidence"] == "high"


def test_offset_commit_is_idempotent_and_revertible(cal):
    before = value(cal)
    req = rid()
    status, body = call(cal.lambda_handler_commit, {**WINDOW, "offset": -0.2, "request_id": req})
    assert status == 200 and body["rows_updated"] == 361
    assert value(cal) == pytest.approx(before - 0.2)
    # Same request id again (client retry / double click) → not applied twice
    status, body = call(cal.lambda_handler_commit, {**WINDOW, "offset": -0.2, "request_id": req})
    assert status == 200 and body["duplicate"] is True
    assert value(cal) == pytest.approx(before - 0.2)
    assert call(cal.lambda_handler_revert, {"station": "Haifa", "request_id": rid()})[0] == 200
    assert value(cal) == pytest.approx(before)


def test_interpolate_commit_works(cal):
    before = value(cal)
    status, body = call(cal.lambda_handler_commit, {**WINDOW, "correction_type": "interpolate", "request_id": rid()})
    assert status == 200, body
    assert value(cal) == pytest.approx(0.10, abs=0.02)
    call(cal.lambda_handler_revert, {"station": "Haifa", "request_id": rid()})
    assert value(cal) == pytest.approx(before)


def test_relative_commit_matches_reference(cal):
    status, _ = call(cal.lambda_handler_commit, {**WINDOW, "correction_type": "relative", "reference_station": "Ashdod",
                                                  "expected_gap": 0.0, "request_id": rid()})
    assert status == 200
    assert value(cal) == pytest.approx(value(cal, "Ashdod"))
    call(cal.lambda_handler_revert, {"station": "Haifa", "request_id": rid()})


def test_preview_matches_commit(cal):
    status, prev = call(cal.lambda_handler_preview, {**WINDOW, "correction_type": "interpolate"})
    assert status == 200
    expected = {r["Tab_DateTime"]: r["corrected_value"] for r in prev["data"]}
    call(cal.lambda_handler_commit, {**WINDOW, "correction_type": "interpolate", "request_id": rid()})
    assert value(cal) == pytest.approx(expected["2026-10-08 15:00:00"])
    call(cal.lambda_handler_revert, {"station": "Haifa", "request_id": rid()})


def test_audit_history_records_user(cal):
    status, body = call(cal.lambda_handler_history, {"station": "Haifa"})
    assert status == 200
    assert body["history"] and all(h["User_Email"] == "benp@mapi.gov.il" for h in body["history"])


@pytest.mark.parametrize("body,code", [
    ({**WINDOW, "station": "Haifa'; DROP TABLE x;--"}, 400),
    ({**WINDOW, "station": "Atlantis"}, 400),
    ({**WINDOW, "start_datetime": "nope"}, 400),
    ({**WINDOW, "end_datetime": "2026-10-08T11:00"}, 400),
    ({**WINDOW, "end_datetime": "2029-10-08T11:00"}, 400),
    ({**WINDOW, "offset": 50}, 400),
])
def test_input_validation(cal, body, code):
    assert call(cal.lambda_handler_preview, body)[0] == code


def test_commit_requires_request_id(cal):
    assert call(cal.lambda_handler_commit, {**WINDOW, "offset": 0.1})[0] == 400


def test_corrections_visible_in_aggregated_data(cal):
    """Readers (hourly/daily aggregation) must see corrected values, not raw."""
    from lambdas.get_data.main import load_data_from_db_optimized
    call(cal.lambda_handler_commit, {**WINDOW, "offset": -0.2, "request_id": rid()})
    try:
        df = load_data_from_db_optimized(start_date="2026-10-01", end_date="2026-10-10", station="Haifa")
        assert df is not None and not df.empty
        assert df["Tab_Value_mDepthC1"].max() < 0.2   # the +0.20 plateau is gone at every level
    finally:
        call(cal.lambda_handler_revert, {"station": "Haifa", "request_id": rid()})
