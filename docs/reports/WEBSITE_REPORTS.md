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
- Hourly, daily and monthly means are the mean of every sample in the hour, day or month. This matches today's
  Monthly Avg file whenever a month has no gaps.
- The **annual mean** on the long-term chart is the mean of the valid monthly means of the reference
  station (`REPORT_REFERENCE_STATIONS`, default **Ashdod**). A month counts as valid with at least 15 days
  of data, and the year needs at least 11 valid months. Ashdod is the default because its 2025 mean
  (0.145 m) matches the 2025 point on the current slide (about 0.147 m). **Ben: please confirm which
  station or method the slide uses.**
- The chart's earlier years come from `backend/reports/annual_mean_history.csv` (`Year,Mean_m`).
  **Fill it once** with 1958–2024 from the Excel behind the slide. Until then the chart shows only the
  years in that file plus the new year.

### Differences from the files uploaded today (deliberate, easy to change)

| Today | Now | Why |
|---|---|---|
| `Daily Avg 25.csv` contained **2024** data | the report's year | It looked like a copy mistake |
| File date in monthly names, e.g. `_2025-01-25` | last day of the month (`_2025-01-31`) | Same name every time a report is made |
| Long-term chart is a slide with the MAPI logos (JPG) | chart only (PNG), no logos | Add the logos when the chart goes into the slide |
| Timestamps end in `Z` although they are Israel local time | kept, for compatibility | Set `REPORT_TS_SUFFIX=` to drop the misleading `Z` |

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
