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
HEBREW_NAMES = {"Acre": "עכו", "Haifa": "חיפה", "Yafo": "יפו", "Ashdod": "אשדוד", "Ashkelon": "אשקלון", "Eilat": "אילת"}
HISTORY_CSV = Path(__file__).resolve().parents[1] / "reports" / "annual_mean_history.csv"

# Timestamps are Israel local time, so no "Z" (UTC) suffix (the old uploads had a misleading "Z").
TS_SUFFIX = os.getenv("REPORT_TS_SUFFIX", "")
MISSING_XLSX = os.getenv("REPORT_MISSING_XLSX", "NULL")      # as in <Station><YY>.xlsx today
MISSING_COMBINED = os.getenv("REPORT_MISSING_COMBINED", "NULL")
MISSING_MONTHLY = os.getenv("REPORT_MISSING_MONTHLY", "NaN")
# The long-term chart is the Mediterranean coast: every station except Eilat (Red Sea).
MEDITERRANEAN = ["Acre", "Haifa", "Yafo", "Ashdod", "Ashkelon"]
REFERENCE_STATIONS = [s.strip() for s in os.getenv("REPORT_REFERENCE_STATIONS", ",".join(MEDITERRANEAN)).split(",")
                      if s.strip()]
ASSETS = Path(__file__).resolve().parents[1] / "reports" / "assets"

# Station comparison (Ben, 25.11.2026): Yafo is the baseline. Expected level relative to Yafo, in mm:
# Ashdod and Ashkelon about −4 (typically −2), Haifa +4, Acre +8. A station whose year-level differs from
# this by more than OFFSET_TOLERANCE_MM (or that has too little data) is left out of the annual mean —
# as in 2025, when Haifa was out of service and Acre had too little reliable data.
BASELINE_STATION = os.getenv("REPORT_BASELINE_STATION", "Yafo")
EXPECTED_OFFSET_MM = {k.strip(): float(v) for k, v in (
    pair.split(":") for pair in os.getenv("REPORT_EXPECTED_OFFSETS_MM",
                                          "Yafo:0,Ashdod:-4,Ashkelon:-4,Haifa:4,Acre:8").split(",") if ":" in pair)}
OFFSET_TOLERANCE_MM = float(os.getenv("REPORT_OFFSET_TOLERANCE_MM", "20"))
# A station contributes to the months it has data, so it needs fewer months than a single-station annual mean;
# the network year itself still needs MIN_MONTHS_PER_YEAR months.
MIN_MONTHS_TO_PARTICIPATE = int(os.getenv("REPORT_MIN_STATION_MONTHS", "6"))
MIN_OVERLAP_MONTHS = 3
MIN_DAYS_PER_MONTH = 15   # PSMSL-style validity for a monthly mean used in the annual mean
MIN_MONTHS_PER_YEAR = 11

if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
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


def _smooth(xs, ys, per=12):
    """Catmull-Rom curve through the points — like Excel's "smoothed line"."""
    import numpy as np
    x, y = np.asarray(xs, float), np.asarray(ys, float)
    if len(x) < 3:
        return x, y
    px = np.r_[2 * x[0] - x[1], x, 2 * x[-1] - x[-2]]
    py = np.r_[2 * y[0] - y[1], y, 2 * y[-1] - y[-2]]
    t = np.linspace(0, 1, per, endpoint=False)
    ox, oy = [], []
    for i in range(1, len(px) - 2):
        for arr, out in ((px, ox), (py, oy)):
            p0, p1, p2, p3 = arr[i - 1], arr[i], arr[i + 1], arr[i + 2]
            out.extend(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    ox.append(x[-1])
    oy.append(y[-1])
    return np.array(ox), np.array(oy)


def _plot_long_term(series: Dict[int, float], title_years: str, reference: str) -> bytes:
    """
    The "מפלס הים התיכון בישראל" slide (1920×1080): annual means (smoothed line + points), linear trend with
    its equation, 6th-order polynomial trend and 19-year moving average (trailing, as Excel draws them),
    MAPI logos. Same construction as the existing slide.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker  # noqa: F401
    import numpy as np
    years = np.array(sorted(series), dtype=float)
    vals = np.array([series[int(y)] for y in years])

    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    fig.patches.extend([
        plt.Rectangle((0, 0), 0.5, 1, transform=fig.transFigure, color="#0095d9", zorder=-3),
        plt.Rectangle((0.5, 0), 0.5, 1, transform=fig.transFigure, color="#23b9d2", zorder=-3),
        plt.Rectangle((0.02, 0.03), 0.96, 0.94, transform=fig.transFigure, color="white", zorder=-2),
    ])
    ax = fig.add_axes((0.05, 0.065, 0.875, 0.805))
    first = int(years[0]) if len(years) else 1958
    last = int(years[-1]) if len(years) else first
    x0, x1 = (first // 5) * 5 - (5 if first % 5 == 0 else 0), last
    ax.set_xlim(x0, x1)
    lo = min(-0.05, np.floor(vals.min() / 0.05) * 0.05) if len(vals) else -0.05
    hi = max(0.2, np.ceil(vals.max() / 0.05) * 0.05) if len(vals) else 0.2
    ax.set_ylim(lo, hi)
    ax.set_xticks(range(x0, x1 + 1, 5))
    ax.set_xticks(range(x0, x1 + 1), minor=True)
    ax.set_yticks(np.arange(lo, hi + 1e-9, 0.05))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%.3f"))
    ax.yaxis.tick_right()
    ax.grid(True, which="both", axis="x", color="#c8c8c8", linewidth=0.8)
    ax.grid(True, which="major", axis="y", color="#c8c8c8", linewidth=0.8)
    ax.tick_params(axis="x", which="major", labelsize=11, length=0, pad=10)
    ax.tick_params(axis="x", which="minor", length=0)
    ax.tick_params(axis="y", labelsize=11, length=0)
    for side in ax.spines.values():
        side.set_color("#bdbdbd")
    ax.axhline(0, color="#c0581d", linewidth=2.5, zorder=1)

    if len(years) >= 2:
        sx, sy = _smooth(years, vals)
        ax.plot(sx, sy, color="#2e6da4", linewidth=2.6, zorder=4)
    ax.plot(years, vals, "o", color="#2e6da4", markersize=6, zorder=5)
    if len(years) >= 3:
        k, b = np.polyfit(years, vals, 1)
        ax.plot(years, k * years + b, ":", color="#1a8f3a", linewidth=2.2, zorder=3)
        ax.text(years.mean(), k * years.mean() + b + (hi - lo) * 0.008, f"y = {k:.4f}x {b:+.3f}".replace("+", "+ ").replace("-", "- "),
                fontsize=12, ha="center", va="bottom", color="#333333", zorder=6)
    if len(years) >= 8:
        c = years.mean()
        poly = np.polyfit(years - c, vals, 6)
        fine = np.linspace(years[0], years[-1], 400)
        ax.plot(fine, np.polyval(poly, fine - c), ":", color="#8c8c8c", linewidth=2, zorder=2)
    if len(years) >= 19:
        ma = np.convolve(vals, np.ones(19) / 19, mode="valid")     # trailing: plotted at the window's last year
        ax.plot(years[18:], ma, ":", color="#8c8c8c", linewidth=2, zorder=2)

    fig.text(0.5, 0.885, _rtl(f"מפלס הים התיכון בישראל {title_years}"), ha="center", va="center",
             fontsize=30, color="#2e6da4")
    fig.text(0.965, 0.47, _rtl("גובה מפלס הים במטרים"), rotation=90, ha="center", va="center",
             fontsize=13, color="#8b1a1a")
    ax.text(x1 - 0.6, 0, _rtl("שנים"), ha="right", va="bottom", fontsize=12, color="#8b1a1a")
    ax.text(x0 + 0.5, lo + (hi - lo) * 0.012, _rtl(f"ממוצע תחנות הים התיכון: {reference}"), ha="left",
            va="bottom", fontsize=10, color="#666666", zorder=6)
    for name, box in (("logo_survey_of_israel.png", (0.379, 0.905, 0.242, 0.052)),
                      ("logo_ministry.png", (0.023, 0.887, 0.074, 0.072))):
        path = ASSETS / name
        if path.exists():
            lax = fig.add_axes(box)
            lax.imshow(plt.imread(str(path)))
            lax.axis("off")
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
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
            out[int(row[0])] = float(row[1])   # Year, Mean_m (further columns are ignored)
        except (ValueError, IndexError):
            continue   # header or a malformed line
    return out


def _valid_month_mean(monthly: Dict[int, dict], month: int, station: str) -> Optional[float]:
    acc = monthly.get(month, {}).get(station)
    return acc["mean"] if acc and acc["days"] >= MIN_DAYS_PER_MONTH else None


def annual_mean(monthly: Dict[int, dict], station: str) -> Optional[float]:
    """One station: mean of valid monthly means (≥ 15 days of data) — None if fewer than 11 valid months."""
    valid = [v for v in (_valid_month_mean(monthly, m, station) for m in range(1, 13)) if v is not None]
    return sum(valid) / len(valid) if len(valid) >= MIN_MONTHS_PER_YEAR else None


def network_annual_mean(monthly: Dict[int, dict], stations: List[str]) -> Optional[float]:
    """
    Several stations (the Mediterranean coast): each month = mean of the stations with a valid monthly mean
    that month; the year = mean of those monthly values, if at least 11 months have one. A station out of
    service for some months therefore does not remove the whole year.
    """
    months = []
    for m in range(1, 13):
        vals = [v for v in (_valid_month_mean(monthly, m, st) for st in stations) if v is not None]
        if vals:
            months.append(sum(vals) / len(vals))
    return sum(months) / len(months) if len(months) >= MIN_MONTHS_PER_YEAR else None


def check_stations(monthly: Dict[int, dict], stations: List[str]):
    """
    Which Mediterranean stations go into the annual mean.

    1. Enough data: at least MIN_MONTHS_TO_PARTICIPATE (6) months with a valid monthly mean (≥ 15 days).
    2. Consistent with the baseline (Yafo): the median over shared valid months of
       (station − Yafo) must be within OFFSET_TOLERANCE_MM of the expected offset. If the station shares fewer
       than 3 months with Yafo, it is compared with another station that passed (expected offsets subtract).
    Returns (included stations, notes explaining every decision).
    """
    def months_of(st):
        return {m: v for m in range(1, 13) if (v := _valid_month_mean(monthly, m, st)) is not None}

    data = {st: months_of(st) for st in stations}
    enough = [st for st in stations if len(data[st]) >= MIN_MONTHS_TO_PARTICIPATE]
    notes = [f"{st}: left out — only {len(data[st])} months with ≥ {MIN_DAYS_PER_MONTH} days of data"
             for st in stations if st not in enough]

    def offset_mm(a, b):
        shared = sorted(set(data[a]) & set(data[b]))
        if len(shared) < MIN_OVERLAP_MONTHS:
            return None, len(shared)
        diffs = sorted((data[a][m] - data[b][m]) * 1000 for m in shared)
        mid = len(diffs) // 2
        return (diffs[mid] if len(diffs) % 2 else (diffs[mid - 1] + diffs[mid]) / 2), len(shared)

    included = []
    base = BASELINE_STATION if BASELINE_STATION in data and data[BASELINE_STATION] else None
    # The baseline itself, then the others; a station without enough overlap with the baseline is compared
    # with a station already accepted.
    order = sorted(enough, key=lambda st: (st != base,))
    for st in order:
        if base is None or st == base:
            included.append(st)
            continue
        refs = [base] + [r for r in included if r != base]
        for ref in refs:
            got, n = offset_mm(st, ref)
            if got is None:
                continue
            expected = EXPECTED_OFFSET_MM.get(st, 0.0) - EXPECTED_OFFSET_MM.get(ref, 0.0)
            ok = abs(got - expected) <= OFFSET_TOLERANCE_MM
            notes.append(f"{st} vs {ref}: {got:+.0f} mm (expected {expected:+.0f} mm, {n} shared months) — "
                         + ("included" if ok else f"left out (more than {OFFSET_TOLERANCE_MM:.0f} mm off)"))
            if ok:
                included.append(st)
            break
        else:
            notes.append(f"{st}: included without comparison (fewer than {MIN_OVERLAP_MONTHS} months shared "
                         f"with {BASELINE_STATION} or an accepted station)")
            included.append(st)
    if base is None:
        notes.append(f"{BASELINE_STATION} (baseline) has no valid months — stations not compared")
    return [st for st in stations if st in included], notes


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

    # Long-term chart: the history file (official values) + this year's Mediterranean mean if not in it yet
    reference = reference or REFERENCE_STATIONS
    series = {y: v for y, v in (history if history is not None else read_history()).items() if y <= year}
    included, checks = check_stations(monthly, reference)
    rep.notes.extend(checks)
    computed = network_annual_mean(monthly, included) if included else None
    label = ", ".join(included) or "no station passed the checks"
    if computed is None:
        rep.notes.append(f"Annual mean {year} not computed: fewer than {MIN_MONTHS_PER_YEAR} months with a valid "
                         f"monthly mean (≥ {MIN_DAYS_PER_MONTH} days) at {label}")
    elif year in series:
        rep.notes.append(f"Annual mean {year}: {series[year]:.3f} m from the history file (official); "
                         f"computed from the data: {computed:.3f} m ({label})")
    else:
        series[year] = round(computed, 3)
        rep.notes.append(f"Annual mean {year}: {series[year]:.3f} m computed ({label}) — add it to "
                         f"backend/reports/annual_mean_history.csv once it is final")
    if series:
        first = min(series)
        rep.files[f"{root}/מפלס הים התיכון בישראל {first}-{year}.png"] = _plot_long_term(
            series, f"{first}-{year}", ", ".join(HEBREW_NAMES.get(st, st) for st in (included or reference)))
        if len(series) == 1:
            rep.notes.append("Long-term chart has only this year — add past annual means to "
                             "backend/reports/annual_mean_history.csv")
    return rep


def previous_month(today: Optional[date] = None):
    today = today or date.today()
    first = today.replace(day=1) - timedelta(days=1)
    return first.year, first.month
