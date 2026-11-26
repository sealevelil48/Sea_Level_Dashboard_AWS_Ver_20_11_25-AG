"""
High and low tides per station, computed from the validated sea-level series.

Why: the "SeaTides" table/materialized view on-prem is refreshed rarely (the refresh took hours), so
recent dates were missing and the dashboard's Tidal Data view showed nothing (HTTP 404). This module
finds each tide directly from the data the dashboard already shows, so it is always current and
uses calibrated values.

Method: 10-minute means → centred 60-minute running mean (removes waves/seiches) → turning points
with scipy.signal.find_peaks: at least 4 h apart (semidiurnal tides, ~6.2 h between high and low)
and a prominence of at least 1 cm. The level and time reported are those of the smoothed series
at the turning point; the temperature is the 10-minute mean at that time.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
import pandas as pd

BUCKET_MIN = 10
SMOOTH_MIN = 60
MIN_SEPARATION_H = 4
MIN_PROMINENCE_M = 0.01
MAX_DAYS = 92


def _series(engine, stations: List[str], start: datetime, end: datetime) -> pd.DataFrame:
    from sqlalchemy import text
    sql = text("""
        SELECT l."Station",
               date_trunc('hour', m."Tab_DateTime")
                 + INTERVAL '10 minutes' * FLOOR(EXTRACT(MINUTE FROM m."Tab_DateTime") / 10) AS t,
               AVG(CAST(m."Tab_Value_mDepthC1" AS DOUBLE PRECISION)) AS level,
               AVG(CAST(m."Tab_Value_monT2m" AS DOUBLE PRECISION)) AS temp
          FROM "Monitors_effective" m JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
         WHERE l."Station" = ANY(:stations) AND m."Tab_DateTime" >= :start AND m."Tab_DateTime" < :end
           AND m."Tab_Value_mDepthC1" IS NOT NULL
         GROUP BY 1, 2 ORDER BY 1, 2
    """)
    with engine.connect() as conn:
        res = conn.execute(sql, {"stations": stations, "start": start, "end": end})
        return pd.DataFrame(res.fetchall(), columns=["Station", "t", "level", "temp"])


def find_tides(times: pd.Series, levels: np.ndarray, temps: np.ndarray) -> List[Dict]:
    """Turning points of one station's 10-minute series (gaps > 1 h split the series)."""
    from scipy.signal import find_peaks
    out: List[Dict] = []
    t = pd.to_datetime(times).reset_index(drop=True)
    if len(t) < 6:
        return out
    # Regular 10-minute grid; short gaps (≤ 1 h) are interpolated, longer gaps stay empty
    s = pd.Series(levels, index=t).astype(float)
    tmp = pd.Series(temps, index=t).astype(float)
    grid = pd.date_range(t.iloc[0], t.iloc[-1], freq=f"{BUCKET_MIN}min")
    s = s.reindex(grid).interpolate(limit=60 // BUCKET_MIN, limit_area="inside")
    tmp = tmp.reindex(grid)
    smooth = s.rolling(SMOOTH_MIN // BUCKET_MIN + 1, center=True, min_periods=3).mean()
    distance = MIN_SEPARATION_H * 60 // BUCKET_MIN
    # Each run without gaps is searched separately (find_peaks cannot cross NaN)
    valid = smooth.notna().to_numpy()
    edges = np.flatnonzero(np.diff(np.r_[0, valid.astype(int), 0]))
    for a, b in zip(edges[::2], edges[1::2]):
        seg = smooth.iloc[a:b]
        if len(seg) < distance:
            continue
        v = seg.to_numpy()
        for kind, idx in (("High", find_peaks(v, distance=distance, prominence=MIN_PROMINENCE_M)[0]),
                          ("Low", find_peaks(-v, distance=distance, prominence=MIN_PROMINENCE_M)[0])):
            for i in idx:
                ts = seg.index[i]
                temp = tmp.get(ts)
                out.append({"Tab_DateTime": ts.strftime("%Y-%m-%dT%H:%M:%S"), "Type": kind,
                            "Tab_Value_mDepthC1": round(float(v[i]), 4),
                            "Tab_Value_monT2m": None if temp is None or pd.isna(temp) else round(float(temp), 2)})
    out.sort(key=lambda r: r["Tab_DateTime"])
    return out


def tides(engine, stations: List[str], start: datetime, end: datetime) -> Dict:
    """{events: [...], daily: [...]} — every high/low tide plus a per-day summary (highest high, lowest low)."""
    if end - start > timedelta(days=MAX_DAYS):
        raise ValueError(f"Tidal analysis is limited to {MAX_DAYS} days")
    df = _series(engine, stations, start - timedelta(hours=3), end + timedelta(hours=3))  # margins for smoothing
    events: List[Dict] = []
    for st, g in df.groupby("Station"):
        for e in find_tides(g["t"], g["level"].to_numpy(), g["temp"].to_numpy()):
            if start.isoformat() <= e["Tab_DateTime"] < end.isoformat():
                events.append({"Station": st, **e})
    events.sort(key=lambda r: (r["Tab_DateTime"], r["Station"]))
    daily: Dict[tuple, Dict] = {}
    for e in events:
        key = (e["Tab_DateTime"][:10], e["Station"])
        d = daily.setdefault(key, {"Date": key[0], "Station": key[1], "HighTide": None, "HighTideTime": None,
                                   "LowTide": None, "LowTideTime": None, "Tides": 0})
        d["Tides"] += 1
        lvl, hhmm = e["Tab_Value_mDepthC1"], e["Tab_DateTime"][11:16]
        if e["Type"] == "High" and (d["HighTide"] is None or lvl > d["HighTide"]):
            d["HighTide"], d["HighTideTime"] = lvl, hhmm
        if e["Type"] == "Low" and (d["LowTide"] is None or lvl < d["LowTide"]):
            d["LowTide"], d["LowTideTime"] = lvl, hhmm
    return {"events": events, "daily": sorted(daily.values(), key=lambda d: (d["Date"], d["Station"])),
            "method": f"{BUCKET_MIN}-min means, {SMOOTH_MIN}-min running mean, turning points ≥ "
                      f"{MIN_SEPARATION_H} h apart, prominence ≥ {MIN_PROMINENCE_M * 100:.0f} cm"}
