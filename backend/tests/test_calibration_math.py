"""Phase 3 math: alignment, gap suggestion, drift episodes (synthetic, no database)."""
import numpy as np
import pandas as pd
import pytest

from shared.calibration_math import DriftParams, align_reference, coverage, detect_drift, suggest_gap


def tide(times, amp=0.15, base=0.10):
    t = pd.Series(pd.to_datetime(times)).sub(pd.Timestamp("2026-01-01")).dt.total_seconds().to_numpy() / 3600
    return base + amp * np.sin(2 * np.pi * t / 12.42)


# --- alignment ----------------------------------------------------------------

def test_exact_timestamps_match_exactly():
    t = pd.Series(pd.date_range("2026-11-01", periods=60, freq="1min"))
    v = pd.Series(tide(t))
    out = align_reference(t, t, v)
    assert coverage(out) == 1.0
    assert np.allclose(out.to_numpy(), v.to_numpy())


def test_offset_sampling_is_interpolated():
    """Target at :00, reference at :30 — the exact-join version matched nothing."""
    tt = pd.Series(pd.date_range("2026-11-01", periods=600, freq="1min"))
    rt = pd.Series(tt + pd.Timedelta(seconds=30))
    out = align_reference(tt, rt, pd.Series(tide(rt)))
    assert coverage(out) >= 0.99
    # Interior samples (reference on both sides) are linearly interpolated: < 0.1 mm error on a smooth tide.
    # The first sample has no earlier reference and falls back to the nearest one (30 s later).
    assert np.nanmax(np.abs(out.to_numpy()[1:] - tide(tt)[1:])) < 1e-4
    assert abs(out.iloc[0] - tide(rt)[0]) < 1e-12


def test_gaps_beyond_tolerance_are_unmatched():
    tt = pd.Series(pd.date_range("2026-11-01", periods=120, freq="1min"))
    rt = tt[(tt < "2026-11-01 00:30") | (tt >= "2026-11-01 01:00")]  # 30-min hole
    out = align_reference(tt, rt, pd.Series(tide(rt)), tolerance_s=120)
    assert 0.70 < coverage(out) < 0.80
    assert out[(tt >= "2026-11-01 00:33") & (tt <= "2026-11-01 00:57")].isna().all()


def test_alignment_keeps_target_order():
    tt = pd.Series(pd.to_datetime(["2026-11-01 00:02", "2026-11-01 00:00", "2026-11-01 00:01"]))
    rt = pd.Series(pd.date_range("2026-11-01", periods=3, freq="1min"))
    out = align_reference(tt, rt, pd.Series([0.0, 1.0, 2.0]))
    assert out.tolist() == [2.0, 0.0, 1.0]


# --- expected gap -------------------------------------------------------------

def test_suggest_gap_recovers_known_baseline_despite_outliers():
    rng = np.random.default_rng(1)
    d = pd.Series(0.034 + rng.normal(0, 0.004, 5000))
    d.iloc[::97] = 0.5  # spikes
    g = suggest_gap(d)
    assert g["gap"] == pytest.approx(0.034, abs=0.001)
    assert g["confidence"] == "high"


def test_suggest_gap_needs_enough_samples():
    assert suggest_gap(pd.Series([0.1] * 10)) is None


# --- drift detection ------------------------------------------------------------

def series(days=10, freq="1min"):
    return pd.Series(pd.date_range("2026-11-01", periods=int(days * 1440), freq=freq))


def test_two_separate_faults_are_two_episodes():
    t = series(days=6)
    d = np.zeros(len(t))
    d[(t >= "2026-11-02 10:00") & (t < "2026-11-02 14:00")] = 0.12   # Tuesday-like fault
    d[(t >= "2026-11-05 08:00") & (t < "2026-11-05 09:30")] = -0.09  # Friday-like fault
    r = detect_drift(t, d)
    assert len(r["episodes"]) == 2
    a, b = r["episodes"]
    # Edges snap to the exact first/last faulty samples (not the smoothed estimate)
    assert (a["start"], a["end"]) == ("2026-11-02T10:00:00", "2026-11-02T13:59:00")
    assert (b["start"], b["end"]) == ("2026-11-05T08:00:00", "2026-11-05T09:29:00")
    assert a["type"] == "plateau" and a["suggested_offset"] == pytest.approx(-0.12, abs=0.005)


def test_short_spike_is_ignored():
    t = series(days=2)
    d = np.zeros(len(t))
    d[(t >= "2026-11-01 12:00") & (t < "2026-11-01 12:10")] = 0.5    # 10-minute spike
    assert detect_drift(t, d)["episodes"] == []


def test_noise_only_has_no_false_positives():
    rng = np.random.default_rng(7)
    t = series(days=10)
    d = rng.normal(0, 0.012, len(t))
    r = detect_drift(t, d)
    assert r["episodes"] == [] and r["slow_drift"] is None


def test_step_that_persists_is_classified_step():
    t = series(days=2)
    d = np.where(t >= "2026-11-01 18:00", 0.08, 0.0)
    ep = detect_drift(t, d)["episodes"]
    assert len(ep) == 1 and ep[0]["type"] == "step"
    assert ep[0]["start"] == "2026-11-01T18:00:00"   # snapped to the exact first faulty sample


def test_slow_creep_is_reported_as_slow_drift():
    rng = np.random.default_rng(3)
    t = series(days=30, freq="5min")
    days = (t - t.iloc[0]).dt.total_seconds() / 86400
    d = 0.001 * days.to_numpy() + rng.normal(0, 0.008, len(t))       # 1 mm/day... too small to cross 5 cm in 30 d? (3 cm)
    r = detect_drift(t, d)
    assert r["slow_drift"] is not None
    assert r["slow_drift"]["mm_per_day"] == pytest.approx(1.0, abs=0.2)


def test_one_cm_per_day_creep_within_one_mm():
    t = series(days=30, freq="5min")
    days = (t - t.iloc[0]).dt.total_seconds() / 86400
    d = 0.01 * days.to_numpy()
    r = detect_drift(t, d)
    # The tail crosses the 5 cm threshold → it is also an episode, and the trend excludes it.
    assert r["slow_drift"] is not None
    assert r["slow_drift"]["mm_per_day"] == pytest.approx(10.0, abs=1.0)


def test_params_are_validated():
    with pytest.raises(ValueError):
        DriftParams(threshold_m=0).validate()
    with pytest.raises(ValueError):
        DriftParams(smooth_minutes=0).validate()
