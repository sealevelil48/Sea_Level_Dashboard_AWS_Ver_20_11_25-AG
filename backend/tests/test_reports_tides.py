"""Website reports (monthly/yearly), tides and admin-only access — against the test PostgreSQL."""
import io
import zipfile

import pytest


@pytest.fixture(scope="module")
def engine(database):
    from shared.database import engine
    assert engine is not None
    return engine


def test_monthly_report_layout(engine):
    from shared import reports
    rep = reports.monthly_report(engine, 2026, 10)
    names = sorted(rep.files)
    assert "10/Haifa/sea_level_data_Haifa_2026-10-31.xlsx" in names
    assert "10/Haifa/sea_level_graph_Haifa_2026-10-31.png" in names
    assert not any("/Eilat/" in n for n in names)          # no data → skipped, with a note
    assert any("Eilat: no data" in n for n in rep.notes)
    from openpyxl import load_workbook
    ws = load_workbook(io.BytesIO(rep.files["10/Haifa/sea_level_data_Haifa_2026-10-31.xlsx"])).active
    assert ws.title == "Historical Data"
    assert [c.value for c in ws[1]] == ["Tab_DateTime", "Station", "Sea_Level", "Temp"]
    assert ws.cell(2, 1).value == "2026-10-07T00:00:00"   # local time, no "Z" and ws.cell(2, 2).value == "Haifa"
    assert ws.max_row - 1 == 3 * 24 + 1                     # hourly means, 7 Oct 00:00 → 10 Oct 00:00
    assert rep.files["10/Haifa/sea_level_graph_Haifa_2026-10-31.png"][:4] == b"\x89PNG"
    z = zipfile.ZipFile(io.BytesIO(rep.zip_bytes()))
    assert sorted(z.namelist()) == names


def test_yearly_report_layout_and_values(engine):
    from shared import reports
    rep = reports.yearly_report(engine, 2026, history={2024: 0.18, 2025: 0.15})
    root = "שנתי"
    for st in reports.STATIONS:
        assert f"{root}/{st}26.xlsx" in rep.files
    combined = rep.files[f"{root}/Daily Avg All Stations Combined 26.csv"].decode().splitlines()
    assert combined[0] == '"Date","Acre","Haifa","Yafo","Ashkelon","Ashdod","Eilat"'
    assert combined[1].startswith('"2026-10-07",') and combined[1].endswith(",NULL")   # Eilat missing → NULL
    monthly = rep.files[f"{root}/Monthly Avg 26.csv"].decode().splitlines()
    assert monthly[0] == '"Station","Year","Month","Monthly_Avg_SeaLevel"'
    assert '"Acre","2026","1",NaN' in monthly
    daily = rep.files[f"{root}/Daily Avg 26.csv"].decode().splitlines()
    assert daily[0] == '"Station","ObservationDate","Daily_Avg_SeaLevel","Min_Level","Max_Level"'
    assert any(n.endswith(".png") for n in rep.files)        # long-term chart from the history
    assert any("not computed" in n for n in rep.notes)       # only a few days of 2026 in the test data


def test_annual_mean_needs_11_valid_months():
    from shared.reports import annual_mean
    full = {m: {"Ashdod": {"mean": 0.1 + m / 1000, "days": 28}} for m in range(1, 13)}
    assert annual_mean(full, "Ashdod") == pytest.approx(sum(0.1 + m / 1000 for m in range(1, 13)) / 12)
    sparse = {m: ({"Ashdod": {"mean": 0.1, "days": 10}} if m < 3 else {"Ashdod": {"mean": 0.1, "days": 20}})
              for m in range(1, 13)}
    assert annual_mean(sparse, "Ashdod") is None           # only 10 months with ≥ 15 days


def test_report_store_roundtrip(engine, tmp_path, monkeypatch):
    from shared import report_store, reports
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path))
    monkeypatch.delenv("REPORTS_BUCKET", raising=False)
    meta = report_store.save(reports.monthly_report(engine, 2026, 10))
    assert meta["name"] == "sea_level_monthly_2026-10.zip" and meta["size"] > 0
    assert [r["name"] for r in report_store.list_reports()] == ["sea_level_monthly_2026-10.zip"]
    url, body = report_store.download("sea_level_monthly_2026-10.zip")
    assert url is None and body[:2] == b"PK"
    for bad in ("../etc/passwd", "sea_level_monthly_2026-10.zip/../x", "x.zip"):
        with pytest.raises(KeyError):
            report_store.download(bad)


def test_tides_from_validated_series():
    """Synthetic semidiurnal tide (12.42 h) + noise: every high and low is found, ~6.2 h apart."""
    import numpy as np
    import pandas as pd
    from shared.tides import find_tides
    t = pd.date_range("2026-10-01", "2026-10-04", freq="10min")
    sec = (t - t[0]).total_seconds().to_numpy()
    rng = np.random.default_rng(1)
    lvl = 0.1 + 0.15 * np.sin(2 * np.pi * sec / 44712) + rng.normal(0, 0.005, len(t))
    ev = find_tides(pd.Series(t), lvl, np.full(len(t), 20.0))
    highs = [e for e in ev if e["Type"] == "High"]
    lows = [e for e in ev if e["Type"] == "Low"]
    assert 5 <= len(highs) <= 6 and 5 <= len(lows) <= 6
    gaps = np.diff(pd.to_datetime([e["Tab_DateTime"] for e in ev]).values).astype("timedelta64[m]").astype(int)
    assert all(330 <= g <= 420 for g in gaps)               # ~6 h 13 min between high and low
    assert all(abs(e["Tab_Value_mDepthC1"] - 0.25) < 0.02 for e in highs)


def test_admin_group_does_not_grant_admin_by_default(monkeypatch):
    from shared.auth import Identity
    monkeypatch.delenv("ADMIN_GROUP", raising=False)
    assert Identity("s", "someone@mapi.gov.il", True, ["admin"]).is_admin is False
    assert Identity("s", "benp@mapi.gov.il", True, []).is_admin is True
    monkeypatch.setenv("ADMIN_GROUP", "admin")
    assert Identity("s", "someone@mapi.gov.il", True, ["admin"]).is_admin is True


def test_mediterranean_mean_uses_months_with_any_station():
    """Eilat excluded; a station missing some months does not drop the year."""
    from shared.reports import MEDITERRANEAN, network_annual_mean
    assert "Eilat" not in MEDITERRANEAN
    monthly = {m: {"Ashdod": {"mean": 0.10, "days": 30}, "Haifa": {"mean": 0.20, "days": 30 if m <= 9 else 5},
                   "Eilat": {"mean": 0.40, "days": 30}} for m in range(1, 13)}
    # Jan–Sep: (0.10+0.20)/2 = 0.15 ; Oct–Dec: Haifa invalid → 0.10 ; year = (9*0.15 + 3*0.10)/12
    assert network_annual_mean(monthly, MEDITERRANEAN) == pytest.approx((9 * 0.15 + 3 * 0.10) / 12)


def test_history_file_values_win_and_chart_is_made(engine):
    from shared import reports
    hist = reports.read_history()
    assert hist[1958] == pytest.approx(0.055) and hist[2025] == pytest.approx(0.150) and len(hist) == 68
    rep = reports.yearly_report(engine, 2026, history=hist)
    assert "שנתי/מפלס הים התיכון בישראל 1958-2026.png" in rep.files


def test_station_check_reproduces_2025_decision():
    """Monthly means from Ben's 'sealevel2025(12)': Haifa and Acre are left out, the year is ~0.149 m (official 0.150)."""
    from shared.reports import MEDITERRANEAN, check_stations, network_annual_mean
    sheet = {  # month: (Acre, Haifa, Yafo, Ashdod, Ashkelon) monthly means, None = no value
        1: (0.103, 0.111, 0.012, 0.013, 0.010), 2: (0.044, 0.082, -0.020, -0.026, -0.017),
        3: (0.133, 0.090, 0.060, 0.051, 0.070), 4: (0.149, 0.109, 0.073, 0.073, 0.074),
        5: (0.176, 0.149, 0.100, 0.100, 0.099), 6: (0.259, 0.220, 0.175, 0.174, 0.176),
        7: (0.329, 0.292, 0.256, 0.254, 0.258), 8: (0.384, 0.306, 0.315, 0.306, 0.303),
        9: (0.315, 0.305, 0.255, 0.243, 0.231), 10: (0.237, None, 0.182, 0.185, 0.180),
        11: (0.273, None, 0.213, 0.212, None), 12: (0.250, None, None, 0.190, None)}
    names = ["Acre", "Haifa", "Yafo", "Ashdod", "Ashkelon"]
    monthly = {m: {st: {"mean": v, "days": 30} for st, v in zip(names, vals) if v is not None}
               for m, vals in sheet.items()}
    included, notes = check_stations(monthly, MEDITERRANEAN)
    assert included == ["Yafo", "Ashdod", "Ashkelon"]
    assert any(n.startswith("Acre vs Yafo") and "left out" in n for n in notes)
    assert any(n.startswith("Haifa vs Yafo") and "left out" in n for n in notes)
    assert network_annual_mean(monthly, included) == pytest.approx(0.149, abs=0.0015)
