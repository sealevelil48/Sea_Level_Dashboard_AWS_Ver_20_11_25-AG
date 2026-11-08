"""
Hydrographic calibration math (Phase 3) — pure functions, no database access.

  align_reference   put a reference station onto the target's timestamps (nearest / linear, with tolerance)
  suggest_gap       robust typical gap target − reference over a calm baseline
  detect_drift      episodes where |(target − reference) − gap| exceeds a threshold, plus slow-drift trend

All series are pandas objects indexed or keyed by naive local timestamps (as stored in Monitors_info2).
Values are metres.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

DEFAULT_TOLERANCE_S = 120          # a reference sample counts if within ±2 min of the target sample
MAX_TOLERANCE_S = 600
MIN_COVERAGE_FOLLOW = 0.95         # "follow reference" needs the reference almost everywhere
MIN_COVERAGE_LEVEL = 0.50          # "level shift" is one robust number; half the window is enough


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------

def align_reference(target_times: pd.Series, ref_times: pd.Series, ref_values: pd.Series,
                    tolerance_s: int = DEFAULT_TOLERANCE_S) -> pd.Series:
    """
    Reference value at each target timestamp.

    - exact match → that value
    - reference samples on both sides, each within `tolerance_s` → linear interpolation
    - only one side within tolerance → that sample
    - otherwise NaN (no reference for this target sample)

    Returns a float Series aligned positionally with `target_times`.
    """
    tol = pd.Timedelta(seconds=int(tolerance_s))
    t = pd.DataFrame({"t": pd.to_datetime(target_times).values, "_pos": np.arange(len(target_times))})
    t = t.sort_values("t")
    r = (pd.DataFrame({"t": pd.to_datetime(ref_times).values, "v": pd.to_numeric(ref_values, errors="coerce").values})
         .dropna().sort_values("t").drop_duplicates("t"))
    if r.empty or t.empty:
        return pd.Series(np.nan, index=range(len(target_times)), dtype=float)

    prev = pd.merge_asof(t, r.rename(columns={"t": "t_prev", "v": "v_prev"}), left_on="t", right_on="t_prev",
                         direction="backward")
    nxt = pd.merge_asof(t, r.rename(columns={"t": "t_next", "v": "v_next"}), left_on="t", right_on="t_next",
                        direction="forward")
    m = prev.merge(nxt[["_pos", "t_next", "v_next"]], on="_pos")

    dp = (m["t"] - m["t_prev"])
    dn = (m["t_next"] - m["t"])
    ok_p = m["t_prev"].notna() & (dp <= tol)
    ok_n = m["t_next"].notna() & (dn <= tol)

    out = pd.Series(np.nan, index=m.index, dtype=float)
    both = ok_p & ok_n
    span = (m["t_next"] - m["t_prev"]).dt.total_seconds()
    frac = np.where(span > 0, dp.dt.total_seconds() / span.replace(0, np.nan), 0.0)
    interp = m["v_prev"] + (m["v_next"] - m["v_prev"]) * np.nan_to_num(frac)
    out[both] = interp[both]
    out[ok_p & ~ok_n] = m.loc[ok_p & ~ok_n, "v_prev"]
    out[~ok_p & ok_n] = m.loc[~ok_p & ok_n, "v_next"]

    result = pd.Series(np.nan, index=range(len(target_times)), dtype=float)
    result.iloc[m["_pos"].to_numpy()] = out.to_numpy()
    return result


def coverage(aligned: pd.Series) -> float:
    return float(aligned.notna().mean()) if len(aligned) else 0.0


# ---------------------------------------------------------------------------
# Expected gap
# ---------------------------------------------------------------------------

def suggest_gap(deltas: pd.Series) -> Optional[Dict[str, float]]:
    """
    Typical gap (target − reference) from baseline deltas, robust to outliers:
    drop points further than 3 × MAD from the median, then report median and IQR.
    """
    d = pd.to_numeric(deltas, errors="coerce").dropna()
    if len(d) < 30:
        return None
    med = d.median()
    mad = (d - med).abs().median() * 1.4826
    if mad > 0:
        d = d[(d - med).abs() <= 3 * mad]
    q1, q3 = d.quantile(0.25), d.quantile(0.75)
    iqr = float(q3 - q1)
    confidence = "high" if iqr < 0.02 else "medium" if iqr < 0.06 else "low"
    return {"gap": round(float(d.median()), 4), "iqr": round(iqr, 4), "samples": int(len(d)), "confidence": confidence}


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------

@dataclass
class DriftParams:
    threshold_m: float = 0.05
    smooth_minutes: int = 30          # rolling median: a short spike can't trigger an episode
    merge_minutes: int = 30           # flagged runs closer than this are one episode
    min_minutes: int = 20             # shorter episodes are ignored
    context_hours: int = 2            # before/after window used to classify an episode

    def validate(self):
        if not (0.005 <= self.threshold_m <= 2.0):
            raise ValueError("threshold must be between 0.005 and 2 m")
        for name, lo, hi in (("smooth_minutes", 1, 720), ("merge_minutes", 0, 1440), ("min_minutes", 1, 1440)):
            v = getattr(self, name)
            if not (lo <= v <= hi):
                raise ValueError(f"{name} must be between {lo} and {hi}")
        return self


def _runs(mask: pd.Series):
    """(start_ts, end_ts) of consecutive True runs in a time-indexed boolean Series."""
    runs, start, prev = [], None, None
    for ts, flag in mask.items():
        if flag and start is None:
            start = ts
        if not flag and start is not None:
            runs.append([start, prev])
            start = None
        prev = ts
    if start is not None:
        runs.append([start, prev])
    return runs


def detect_drift(times, deviation, params: Optional[DriftParams] = None) -> Dict:
    """
    deviation = (target − reference) − expected_gap, at aligned timestamps (NaN allowed).

    Returns {episodes: [...], slow_drift: {...} | None, series: [...downsampled...], params}.
    Episode types:
      step     — deviation persists after the episode (sensor jumped and stayed) → suggest an offset
      plateau  — deviation returns to ~0 after the episode (temporary fault) → bridge or level shift
    """
    p = (params or DriftParams()).validate()
    s = pd.Series(pd.to_numeric(pd.Series(deviation), errors="coerce").to_numpy(),
                  index=pd.to_datetime(pd.Series(times)).to_numpy()).sort_index().dropna()
    s = s[~s.index.duplicated()]
    if len(s) < 3:
        return {"episodes": [], "slow_drift": None, "series": [], "params": p.__dict__}

    smooth = s.rolling(f"{p.smooth_minutes}min", center=True, min_periods=1).median()
    flagged = smooth.abs() > p.threshold_m

    # Merge runs separated by short gaps; drop short runs.
    runs = _runs(flagged)
    merged = []
    for r in runs:
        if merged and (r[0] - merged[-1][1]) < pd.Timedelta(minutes=p.merge_minutes):
            merged[-1][1] = r[1]
        else:
            merged.append(list(r))
    ctx = pd.Timedelta(hours=p.context_hours)
    half = pd.Timedelta(minutes=p.smooth_minutes / 2)
    raw_flag = s.abs() > p.threshold_m
    episodes = []
    for start, end in merged:
        if (end - start) < pd.Timedelta(minutes=p.min_minutes):
            continue
        # Snap edges to the exact first/last raw sample beyond the threshold near the smoothed edges
        # (the rolling median can move an edge by up to half its window).
        near_start = raw_flag[start - half: start + half]
        near_end = raw_flag[end - half: end + half]
        if near_start.any():
            start = near_start[near_start].index[0]
        if near_end.any():
            end = near_end[near_end].index[-1]
        inside = s[start:end]
        after = smooth[end + pd.Timedelta(seconds=1): end + ctx]
        persists = len(after) == 0 or bool((after.abs() > p.threshold_m / 2).mean() > 0.5)
        episodes.append({
            "start": start.isoformat(),
            "end": end.isoformat(),
            "duration_minutes": round((end - start).total_seconds() / 60, 1),
            "samples": int(len(inside)),
            "max_deviation": round(float(inside.abs().max()), 4),
            "median_deviation": round(float(inside.median()), 4),
            "type": "step" if persists else "plateau",
            # Value that brings this episode back to the reference + gap:
            "suggested_offset": round(float(-inside.median()), 4),
        })

    # Slow drift: robust trend of the smoothed deviation (hourly), outside the episodes.
    slow = None
    hourly = smooth.resample("1h").median().dropna()
    for ep in episodes:
        hourly = hourly[(hourly.index < pd.Timestamp(ep["start"])) | (hourly.index > pd.Timestamp(ep["end"]))]
    if len(hourly) >= 24 and (hourly.index[-1] - hourly.index[0]) >= pd.Timedelta(days=2):
        from scipy.stats import theilslopes
        days = (hourly.index - hourly.index[0]).total_seconds() / 86400.0
        slope, _, lo, hi = theilslopes(hourly.to_numpy(), days)
        total = slope * days[-1]
        significant = (lo > 0 or hi < 0) and abs(total) >= max(0.01, p.threshold_m / 5)
        if significant:
            slow = {"mm_per_day": round(slope * 1000, 2), "ci_mm_per_day": [round(lo * 1000, 2), round(hi * 1000, 2)],
                    "since": hourly.index[0].isoformat(), "total_change_m": round(float(total), 4)}

    # Downsampled deviation for the UI strip (≤ 300 points)
    step = max(1, -(-len(smooth) // 300))  # ceil → never more than 300 points
    series = [{"t": ts.isoformat(), "d": round(float(v), 4)} for ts, v in smooth.iloc[::step].items()]
    return {"episodes": episodes, "slow_drift": slow, "series": series, "params": p.__dict__}
