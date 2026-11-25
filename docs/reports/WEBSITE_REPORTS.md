# Website reports — monthly and yearly (admin only)

The files Ben uploads to the MAPI website each month and each year are now produced by the dashboard, in
the same layout and formats as today's uploads (checked against `01.zip` and `שנתי.zip`).

## What is produced

**Monthly** — `sea_level_monthly_<YYYY-MM>.zip`

```
MM/<Station>/sea_level_data_<Station>_<last day of month>.xlsx   sheet "Historical Data"
      Tab_DateTime | Station | Sea_Level | Temp      hourly means, formats 0.000 / 0.0
MM/<Station>/sea_level_graph_<Station>_<last day of month>.png  1200×600 "Sea Level Over Time"
```

A station with no data in the month is skipped and listed in the report's notes.

**Yearly** — `sea_level_yearly_<YYYY>.zip`

```
שנתי/<Station><YY>.xlsx                         Sheet1: Date | <Station>   daily means, one row per day
שנתי/Daily Avg <YY>.csv                         Station, ObservationDate, Daily_Avg_SeaLevel, Min_Level, Max_Level
שנתי/Daily Avg All Stations Combined <YY>.csv   Date, Acre, Haifa, Yafo, Ashkelon, Ashdod, Eilat
שנתי/Monthly Avg <YY>.csv                       Station, Year, Month, Monthly_Avg_SeaLevel
שנתי/מפלס הים התיכון בישראל <first>-<YYYY>.png    long-term annual mean chart
```

Missing values follow today's files: `NULL` in the per-station xlsx and the combined CSV, and `NaN` in Monthly
Avg. These can be changed with `REPORT_MISSING_*`.

### How the numbers are computed

- All values come from the **validated series** (`Monitors_effective`): calibration corrections are applied
  and deleted samples are left out.
- Hourly, daily and monthly means are the mean of every sample in the hour, day or month.
- **Long-term chart** (*מפלס הים התיכון בישראל*):
  - **History:** `backend/reports/annual_mean_history.csv` holds the official annual means for 1958–2025, taken
    from Ben's *מפלס ממוצע 1958-2024.xlsx*. When the history file has a value for a year, the chart uses that
    published value. The report's notes also show the value computed from the data, for comparison.
  - **New year (2026 onward):** the year's value is computed as the **average of the Mediterranean stations**
    (Acre, Haifa, Yafo, Ashdod, Ashkelon; **Eilat is excluded** because it is on the Red Sea). Each month is the
    mean of the stations that have a valid monthly mean (≥ 15 days of data), and the year is the mean of those
    months (at least 11 are needed). A station that is out of service for a few months therefore doesn't drop
    the year.
  - **Drawn like the slide:** smoothed line with points, linear trend with its equation, a 6th-order
    polynomial trend and a 19-year trailing moving average (the two grey dotted lines on the current slide;
    both were checked against it), the MAPI logos, and 1920×1080.
  - **Once a year is final,** add its official value to the history file.

> **Check (2025):** the official 2025 value is **0.150 m**. In *sealevel202512.xlsx*, the plain average of the
> five Mediterranean stations is **0.168 m** (average of the station means) or **0.174 m** (average of the monthly
> network means). Yafo + Ashdod + Ashkelon alone gives about **0.149 m**. If the official value excludes
> stations or applies a correction (for example Haifa's calibration issues noted in the sheet), set
> `REPORT_REFERENCE_STATIONS` accordingly before the 2026 report.

### Choices agreed with Ben (25.11.2026)

| Item | Now |
|---|---|
| Monthly file names | last day of the month, e.g. `sea_level_data_Haifa_2025-01-31.xlsx` |
| Timestamps in the monthly xlsx | Israel local time, **no `Z`**, e.g. `2025-01-01T00:00:00` |
| `Daily Avg <YY>.csv` | the report's year (the 2024 data in the old file was a mistake) |
| Long-term chart | the slide's layout and logos, PNG |

## How reports are made

| Where | How |
|---|---|
| **Dashboard** (admins) | **Reports** tab: choose monthly or yearly, then year (and month), then **Generate**. The list shows every report with notes about data gaps, and **Download** gives the zip. |
| **AWS** (automatic) | The reports Lambda runs on the 1st of every month at about 04:15 Israel time (previous month) and on 2 January (previous year). It saves to `s3://sealevel-reports-<env>-<account>/reports/` and e-mails a notice to the alarm address. |
| **On-prem server** (automatic) | `scripts/onprem/website_reports.bat monthly|yearly` runs from Windows Task Scheduler (registration commands are in the file). It writes to `reports_output\` (listed in the Reports tab) and extracts the files in the website layout to `%REPORTS_WEBSITE_DIR%`. |
| **Command line** | `python backend/reports_cli.py monthly --year 2025 --month 1 --out <folder> --unzip` |
| **Pull from AWS** to a PC | `python scripts/pull_reports.py --env prod --dest "<website folder>"` downloads and extracts only new reports. |

Uploading to the MAPI website itself is still manual, because the upload method isn't known yet (CMS form,
shared folder or SFTP). If the website has an upload folder or an API, the scheduled task can copy the files
there directly. That step needs only the target path or credentials.

## Access

Only `ADMIN_EMAILS` (benp@mapi.gov.il, with Google reporting the address as verified) can see the tab or call
`/api/reports*`. Everyone else gets HTTP 403 and never sees the tab.
