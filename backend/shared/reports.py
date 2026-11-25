"""
Monthly and yearly reports for the MAPI website (admin only).

Formats follow the files Ben uploads today, so the website side does not change:

Monthly (one folder per month, one sub-folder per station):
    MM/<Station>/sea_level_data_<Station>_<YYYY-MM-DD>.xlsx   sheet "Historical Data":
        Tab_DateTime | Station | Sea_Level | Temp       — hourly means of the validated series
    MM/<Station>/sea_level_graph_<Station>_<YYYY-MM-DD>.png  1200×600 "Sea Level Over Time"

Yearly ("שנתי"):
    <Station><YY>.xlsx                              Sheet1: Date | <Station>  — daily means
    Daily Avg <YY>.csv                              Station, ObservationDate, Daily_Avg_SeaLevel, Min_Level, Max_Level
    Daily Avg All Stations Combined <YY>.csv        Date, Acre, Haifa, Yafo, Ashkelon, Ashdod, Eilat
    Monthly Avg <YY>.csv                            Station, Year, Month, Monthly_Avg_SeaLevel
    מפלס הים התיכון בישראל <first>-<YYYY>.png        long-term annual mean chart (history file + this year)

All values come from "Monitors_effective" — the validated series (calibration corrections applied,
deleted samples left out). Means are means of every sample in the hour / day / month.
Timestamps are the database's local (Israel) wall-clock time.
"""
from __future__ import annotations

import calendar
import csv
import io
import logging
import math
import os
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

# Column order of the website's combined CSV (north → south, Eilat last)
STATIONS = ["Acre", "Haifa", "Yafo", "Ashkelon", "Ashdod", "Eilat"]
HISTORY_CSV = Path(__file__).resolve().parents[1] / "reports" / "annual_mean_history.csv"

# Existing files label local time with a trailing "Z"; kept for compatibility (REPORT_TS_SUFFIX="" to drop it).
TS_SUFFIX = os.getenv("REPORT_TS_SUFFIX", "Z")
MISSING_XLSX = os.getenv("REPORT_MISSING_XLSX", "NULL")      # as in <Station><YY>.xlsx today
MISSING_COMBINED = os.getenv("REPORT_MISSING_COMBINED", "NULL")
MISSING_MONTHLY = os.getenv("REPORT_MISSING_MONTHLY", "NaN")
REFERENCE_STATIONS = [s.strip() for s in os.getenv("REPORT_REFERENCE_STATIONS", "Ashdod").split(",") if s.strip()]
MIN_DAYS_PER_MONTH = 15   # PSMSL-style validity for a monthly mean used in the annual mean
MIN_MONTHS_PER_YEAR = 11

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")   # Lambda: only /tmp is writable


@dataclass
class Report:
    kind: str                       # monthly | yearly
    period: str                     # 2025-01 | 2025
    files: Dict[str, bytes] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"sea_level_{self.kind}_{self.period}.zip"

    def zip_bytes(self) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for path, data in self.files.items():
                z.writestr(path, data)
        return buf.getvalue()

    def manifest(self) -> dict:
        return {"kind": self.kind, "period": self.period, "name": self.name,
                "files": sorted(self.files), "notes": self.notes}


# ---------------------------------------------------------------------------
# Queries (validated series)
# ---------------------------------------------------------------------------

def _rows(engine, sql: str, params: dict):
    from sqlalchemy import text
    with engine.connect() as conn:
        return conn.execute(text(sql), params).fetchall()


def _hourly(engine, stations: List[str], start: datetime, end: datetime):
    return _rows(engine, """
        SELECT l."Station", date_trunc('hour', m."Tab_DateTime") AS h,
               AVG(CAST(m."Tab_Value_mDepthC1" AS DOUBLE PRECISION)) AS level,
               AVG(CAST(m."Tab_Value_monT2m"  AS DOUBLE PRECISION)) AS temp
          FROM "Monitors_effective" m JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
         WHERE l."Station" = ANY(:stations) AND m."Tab_DateTime" >= :start AND m."Tab_DateTime" < :end
           AND m."Tab_Value_mDepthC1" IS NOT NULL
         GROUP BY 1, 2 ORDER BY 1, 2
    """, {"stations": stations, "start": start, "end": end})


def _daily(engine, stations: List[str], start: datetime, end: datetime):
    """Per station and day: mean, min, max, sum and number of samples (sum/count → exact monthly means)."""
    return _rows(engine, """
        SELECT l."Station", CAST(date_trunc('day', m."Tab_DateTime") AS DATE) AS d,
               AVG(v) AS mean, MIN(v) AS lo, MAX(v) AS hi, SUM(v) AS total, COUNT(*) AS n
          FROM (SELECT "Tab_TabularTag", "Tab_DateTime", CAST("Tab_Value_mDepthC1" AS DOUBLE PRECISION) AS v
                  FROM "Monitors_effective"
                 WHERE "Tab_DateTime" >= :start AND "Tab_DateTime" < :end AND "Tab_Value_mDepthC1" IS NOT NULL) m
          JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
         WHERE l."Station" = ANY(:stations)
         GROUP BY 1, 2 ORDER BY 2, 1
    """, {"stations": stations, "start": start, "end": end})


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def _xlsx(header: List[str], rows: Iterable[list], formats: Dict[int, str], widths: Dict[int, float],
          sheet: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(header)
    for r in rows:
        ws.append(r)
    for col, fmt in formats.items():
        for cell in ws.iter_rows(min_row=2, min_col=col, max_col=col):
            if not isinstance(cell[0].value, str):
                cell[0].number_format = fmt
    for col, w in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = w
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _csv(header: List[str], rows: Iterable[list], missing: str) -> bytes:
    """All values quoted, missing values unquoted (NULL / NaN) — the format of the existing files."""
    def cell(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return missing
        return '"' + str(v).replace('"', '""') + '"'
    lines = [",".join('"%s"' % h for h in header)] + [",".join(cell(v) for v in r) for r in rows]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _num(v):
    return None if v is None else float(v)


def _plot_month(station: str, times: List[datetime], values: List[float]) -> bytes:
    """1200×600 PNG in the dashboard's dark-blue style (like today's exported graphs)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    import matplotlib.ticker  # noqa: F401
    bg = "#13294b"
    fig, ax = plt.subplots(figsize=(12, 6), dpi=100)
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)
    ax.plot(times, values, color="#1f8fd1", linewidth=1.6, label=station)
    ax.axhline(0, color="white", linewidth=1)
    ax.set_title("Sea Level Over Time", color="white", fontsize=13)
    ax.grid(True, color="#2a4a7c", linewidth=0.8)
    for side in ax.spines.values():
        side.set_visible(False)
    ax.tick_params(colors="white", labelsize=9)
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.SU))
    # "%-d" is not portable (Windows on-prem server) — build "Jan 5" by hand
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
        lambda x, _pos: (lambda d: f"{d:%b} {d.day}")(mdates.num2date(x))))
    ax.set_ylabel("Sea level (m)", color="white", fontsize=9)
    leg = ax.legend(loc="upper left", facecolor=bg, edgecolor="#2a4a7c", labelcolor="white", fontsize=9)
    leg.get_frame().set_linewidth(0.8)
    if times:
        ax.set_xlim(times[0], times[-1])
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=bg)
    plt.close(fig)
    return buf.getvalue()


def _rtl(text: str) -> str:
    try:
        from bidi import get_display
        return get_display(text)
    except ImportError:  # pragma: no cover
        return text


def _plot_long_term(series: Dict[int, float], title_years: str, reference: str) -> bytes:
    """Annual mean sea level with a linear trend and a 19-year (tidal epoch) moving average."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    years = sorted(series)
    vals = [series[y] for y in years]
    fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=100)
    ax.plot(years, vals, "-o", color="#2f6aa8", linewidth=2.2, markersize=5, label=_rtl("ממוצע שנתי"))
    if len(years) >= 3:
        k, b = np.polyfit(years, vals, 1)
        ax.plot(years, [k * y + b for y in years], ":", color="#1a8f3a", linewidth=2,
                # No brackets or signs inside Hebrew labels: the bidi reordering would mirror them wrongly
                label=_rtl(f"מגמה ליניארית: {'עלייה' if k >= 0 else 'ירידה'} של {abs(k) * 1000:.2f} מ\"מ לשנה"))
    if len(years) >= 19:
        ma = np.convolve(vals, np.ones(19) / 19, mode="valid")
        ax.plot(years[9:-9], ma, ":", color="#888888", linewidth=2, label=_rtl("ממוצע נע 19 שנים"))
    ax.axhline(0, color="#c0581d", linewidth=2)
    ax.set_title(_rtl(f"מפלס הים התיכון בישראל {title_years}"), fontsize=26, color="#2f6aa8")
    ax.set_ylabel(_rtl("גובה מפלס הים במטרים"), fontsize=13, color="#8b1a1a")
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    ax.grid(True, axis="x", color="#cccccc")
    ax.grid(True, axis="y", color="#dddddd")
    if years:
        ax.set_xlim(years[0] - 3, years[-1] + 1)
    ax.legend(loc="upper left", fontsize=11)
    ax.text(0.995, 0.01, _rtl(f"תחנת ייחוס: {reference}"), transform=ax.transAxes, ha="right",
            fontsize=10, color="#555555")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def monthly_report(engine, year: int, month: int, stations: Optional[List[str]] = None,
                   stamp: Optional[date] = None) -> Report:
    stations = [s for s in (stations or STATIONS) if s in STATIONS]
    start = datetime(year, month, 1)
    end = datetime(year + (month == 12), month % 12 + 1, 1)
    stamp = stamp or date(year, month, calendar.monthrange(year, month)[1])
    rep = Report("monthly", f"{year}-{month:02d}")
    by_station: Dict[str, list] = {s: [] for s in stations}
    for st, h, level, temp in _hourly(engine, stations, start, end):
        by_station[st].append((h, _num(level), _num(temp)))
    hours_in_month = int((end - start).total_seconds() // 3600)
    for st in stations:
        rows = by_station[st]
        if not rows:
            rep.notes.append(f"{st}: no data in {year}-{month:02d} — skipped")
            continue
        if len(rows) < hours_in_month:
            rep.notes.append(f"{st}: {len(rows)} of {hours_in_month} hours have data")
        folder = f"{month:02d}/{st}"
        xlsx_rows = [[h.strftime("%Y-%m-%dT%H:%M:%S") + TS_SUFFIX, st, level, temp] for h, level, temp in rows]
        rep.files[f"{folder}/sea_level_data_{st}_{stamp.isoformat()}.xlsx"] = _xlsx(
            ["Tab_DateTime", "Station", "Sea_Level", "Temp"], xlsx_rows, {3: "0.000", 4: "0.0"},
            {1: 22, 2: 12, 3: 12, 4: 10}, "Historical Data")
        rep.files[f"{folder}/sea_level_graph_{st}_{stamp.isoformat()}.png"] = _plot_month(
            st, [r[0] for r in rows], [r[1] for r in rows])
    return rep


def read_history(path: Optional[Path] = None) -> Dict[int, float]:
    """Annual means from before the database (Year,Mean_m). Lines starting with # are ignored."""
    p = Path(os.getenv("REPORTS_HISTORY_CSV", "") or path or HISTORY_CSV)
    out: Dict[int, float] = {}
    if not p.exists():
        return out
    for row in csv.reader(line for line in p.read_text(encoding="utf-8-sig").splitlines()
                          if line.strip() and not line.startswith("#")):
        try:
            out[int(row[0])] = float(row[1])
        except (ValueError, IndexError):
            continue   # header or a malformed line
    return out


def annual_mean(monthly: Dict[int, dict], station: str) -> Optional[float]:
    """Mean of valid monthly means (≥ 15 days of data) — None if fewer than 11 valid months."""
    valid = []
    for mo in monthly.values():
        s = mo.get(station)
        if s and s["days"] >= MIN_DAYS_PER_MONTH:
            valid.append(s["mean"])
    return sum(valid) / len(valid) if len(valid) >= MIN_MONTHS_PER_YEAR else None


def yearly_report(engine, year: int, history: Optional[Dict[int, float]] = None,
                  reference: Optional[List[str]] = None) -> Report:
    yy = f"{year % 100:02d}"
    start, end = datetime(year, 1, 1), datetime(year + 1, 1, 1)
    rep = Report("yearly", str(year))
    root = "שנתי"
    daily = _daily(engine, STATIONS, start, end)

    per_day: Dict[date, Dict[str, tuple]] = {}
    monthly: Dict[int, Dict[str, dict]] = {m: {} for m in range(1, 13)}
    for st, d, mean, lo, hi, total, n in daily:
        per_day.setdefault(d, {})[st] = (float(mean), float(lo), float(hi))
        acc = monthly[d.month].setdefault(st, {"sum": 0.0, "n": 0, "days": 0})
        acc["sum"] += float(total)
        acc["n"] += int(n)
        acc["days"] += 1
    for mo in monthly.values():
        for acc in mo.values():
            acc["mean"] = acc["sum"] / acc["n"]
    days = sorted(per_day)

    # <Station><YY>.xlsx — one row per day on which any station reported
    for st in STATIONS:
        rows = [[datetime(d.year, d.month, d.day), per_day[d][st][0] if st in per_day[d] else MISSING_XLSX] for d in days]
        rep.files[f"{root}/{st}{yy}.xlsx"] = _xlsx(["Date", st], rows,
                                                   {1: "[$-1010409]d/m/yyyy\\ h:mm\\ AM/PM;@"}, {1: 18, 2: 14}, "Sheet1")
        missing = sum(1 for d in days if st not in per_day[d])
        if missing:
            rep.notes.append(f"{st}: no data on {missing} of {len(days)} days")

    rep.files[f"{root}/Daily Avg {yy}.csv"] = _csv(
        ["Station", "ObservationDate", "Daily_Avg_SeaLevel", "Min_Level", "Max_Level"],
        ([st, d.isoformat(), *per_day[d][st]] for d in days for st in sorted(per_day[d])), "NULL")
    rep.files[f"{root}/Daily Avg All Stations Combined {yy}.csv"] = _csv(
        ["Date", *STATIONS],
        ([d.isoformat(), *[per_day[d][st][0] if st in per_day[d] else None for st in STATIONS]] for d in days),
        MISSING_COMBINED)
    rep.files[f"{root}/Monthly Avg {yy}.csv"] = _csv(
        ["Station", "Year", "Month", "Monthly_Avg_SeaLevel"],
        ([st, year, m, monthly[m][st]["mean"] if st in monthly[m] else None]
         for st in sorted(STATIONS) for m in range(1, 13)), MISSING_MONTHLY)

    # Long-term chart: history file + this year's annual mean of the reference station(s)
    reference = reference or REFERENCE_STATIONS
    series = dict(history if history is not None else read_history())
    means = [v for v in (annual_mean(monthly, st) for st in reference) if v is not None]
    if means:
        series[year] = sum(means) / len(means)
        rep.notes.append(f"Annual mean {year} ({'+'.join(reference)}): {series[year]:.4f} m")
    else:
        rep.notes.append(f"Annual mean {year} not computed: fewer than {MIN_MONTHS_PER_YEAR} valid months "
                         f"(≥ {MIN_DAYS_PER_MONTH} days) for {'+'.join(reference)}")
    if series:
        first = min(series)
        rep.files[f"{root}/מפלס הים התיכון בישראל {first}-{year}.png"] = _plot_long_term(
            series, f"{first}-{year}", "+".join(reference))
        if len(series) == 1:
            rep.notes.append("Long-term chart has only this year — add past annual means to "
                             "backend/reports/annual_mean_history.csv")
    return rep


def previous_month(today: Optional[date] = None):
    today = today or date.today()
    first = today.replace(day=1) - timedelta(days=1)
    return first.year, first.month
