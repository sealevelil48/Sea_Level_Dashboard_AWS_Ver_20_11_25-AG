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


# ---------------------------------------------------------------------------
# Phase 3 (Hydras): alignment, coverage, strengths, overwrite rule, references, gap, drift
# ---------------------------------------------------------------------------
REL = {**WINDOW, "correction_type": "relative"}


def test_relative_follow_with_offset_sampling_and_outage_is_refused_below_95pct(cal):
    """Acre samples 30 s out of step and is offline 14:00–15:00 → ~83 % coverage → follow commit refused."""
    status, prev = call(cal.lambda_handler_preview, {**REL, "reference_station": "Acre", "expected_gap": -0.034})
    assert status == 200
    assert 0.80 < prev["coverage"] < 0.86 and prev["commit_allowed"] is False
    assert any(not r["matched"] for r in prev["data"])
    status, body = call(cal.lambda_handler_commit, {**REL, "reference_station": "Acre", "expected_gap": -0.034,
                                                     "request_id": rid()})
    assert status == 422 and "covers" in body["error"]


def test_relative_follow_interpolates_offset_sampling(cal):
    """Outside the outage, 30-s offset sampling still aligns (~100 %), and the plateau is removed."""
    w = {**REL, "start_datetime": "2026-10-08T15:30", "end_datetime": "2026-10-08T18:00",
         "reference_station": "Acre", "expected_gap": -0.034}
    status, prev = call(cal.lambda_handler_preview, w)
    assert status == 200 and prev["coverage"] >= 0.99 and prev["commit_allowed"]
    before = value(cal, ts="2026-10-08 16:00")
    status, body = call(cal.lambda_handler_commit, {**w, "request_id": rid()})
    assert status == 200, body
    assert value(cal, ts="2026-10-08 16:00") == pytest.approx(before - 0.20, abs=0.002)
    call(cal.lambda_handler_revert, {"station": "Haifa", "request_id": rid()})


def test_relative_level_shift_allows_partial_coverage_and_keeps_shape(cal):
    w = {**REL, "reference_station": "Acre", "expected_gap": -0.034, "strength": "level"}
    status, prev = call(cal.lambda_handler_preview, w)
    assert status == 200 and prev["commit_allowed"] is True
    assert prev["parameters"]["level_shift"] == pytest.approx(-0.20, abs=0.002)
    shifts = {round(r["corrected_value"] - r["current_value"], 6) for r in prev["data"]}
    assert len(shifts) == 1                       # one constant: the target keeps its own signal


def test_relative_commit_overwrites_never_accumulates(cal):
    """SQL overwrite rule: committing the same relative correction twice must not double-count the gap."""
    w = {**REL, "reference_station": "Ashdod", "expected_gap": 0.0}
    assert call(cal.lambda_handler_commit, {**w, "request_id": rid()})[0] == 200
    once = value(cal)
    assert call(cal.lambda_handler_commit, {**w, "request_id": rid()})[0] == 200   # different request id
    assert value(cal) == pytest.approx(once, abs=1e-9)
    assert value(cal) == pytest.approx(value(cal, "Ashdod"), abs=1e-9)
    from sqlalchemy import text
    with cal.engine.connect() as c:
        off = c.execute(text('SELECT "Offset" FROM "Calibration_Offsets" WHERE "Tab_TabularTag" = 1 '
                             'AND "Tab_DateTime" = :t'), {"t": PROBE}).scalar()
    assert off == pytest.approx(value(cal) - 0.30 - 0.01 * __import__("math").sin(
        __import__("pandas").Timestamp(PROBE).timestamp() / 3600), abs=1e-6)     # = ref − raw, not 2 × (ref − raw)
    call(cal.lambda_handler_revert, {"station": "Haifa", "request_id": rid()})
    call(cal.lambda_handler_revert, {"station": "Haifa", "request_id": rid()})


def test_relative_rejects_bad_strength_and_tolerance(cal):
    assert call(cal.lambda_handler_preview, {**REL, "reference_station": "Ashdod", "strength": "max"})[0] == 400
    assert call(cal.lambda_handler_preview, {**REL, "reference_station": "Ashdod", "tolerance_seconds": 9999})[0] == 400
    assert call(cal.lambda_handler_preview, {**REL, "reference_station": "Haifa"})[0] == 400   # self-reference


def test_references_report_coverage(cal):
    status, body = call(cal.lambda_handler_references, WINDOW)
    assert status == 200
    refs = {r["station"]: r for r in body["references"]}
    assert "Haifa" not in refs
    assert refs["Ashdod"]["coverage"] == 1.0
    assert 0.80 < refs["Acre"]["coverage"] < 0.86
    assert refs["Eilat"]["coverage"] == 0.0 and refs["Eilat"]["samples_in_window"] == 0
    assert body["references"][0]["station"] == "Ashdod"          # sorted by coverage
    assert call(cal.lambda_handler_references, WINDOW, claims=CLIENT)[0] == 403


def test_suggest_gap_from_baseline(cal):
    status, body = call(cal.lambda_handler_suggest_gap, {"station": "Haifa", "reference_station": "Acre",
                                                         "start_datetime": "2026-10-08T12:00", "baseline_days": 1})
    assert status == 200, body
    assert body["gap"] == pytest.approx(-0.034, abs=0.001) and body["confidence"] == "high"


def test_drift_engine_snaps_to_exact_window(cal):
    w = {"station": "Haifa", "start_datetime": "2026-10-07T00:00", "end_datetime": "2026-10-09T23:59",
         "reference_station": "Ashdod", "expected_gap": 0.0}
    status, body = call(cal.lambda_handler_suggest, w)
    assert status == 200 and body["drift_detected"] is True
    assert len(body["episodes"]) == 1
    assert body["malfunction_start"] == "2026-10-08T12:00:00"
    assert body["malfunction_end"] == "2026-10-08T18:00:00"
    ep = body["episodes"][0]
    assert ep["type"] == "plateau" and ep["suggested_offset"] == pytest.approx(-0.20, abs=0.002)
    assert body["deviation"] and len(body["deviation"]) <= 301


def test_drift_engine_threshold_and_no_drift(cal):
    w = {"station": "Haifa", "start_datetime": "2026-10-07T00:00", "end_datetime": "2026-10-08T06:00",
         "reference_station": "Ashdod", "expected_gap": 0.0}
    status, body = call(cal.lambda_handler_suggest, w)
    assert status == 200 and body["drift_detected"] is False
    assert call(cal.lambda_handler_suggest, {**w, "threshold": 0})[0] == 400
