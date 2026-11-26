# On-prem server: upgrade the dashboard and harden the DB sync

Server: `FUJITSU`, user `slg`, Windows Task Scheduler. Until AWS is live, this server runs both:

| Piece | Folder (today) | Started by |
|---|---|---|
| **DB sync** SSMS → PostgreSQL `Monitors_info2` (every 60 s) | `C:\Users\slg\Desktop\Automation SSMS - Postgres22` | task *Database Sync - SSMS to Postgres* (at startup) |
| **Weekly backfill** | same folder | task *Database Sync* (Sunday 02:00) |
| **Dashboard** API :30886 + site :30887 | `C:\Users\slg\Desktop\Ben\Sea_Level_Dashboard\Sea_Level_Dashboard_AWS_Ver_20_11_25-AG-feature-calibration-correction` | tasks *Sea Level Da…* (at startup → `backend\start_server.bat`) and *Sea Level Da…* (watchdog, every minute) |
| DB backup | — | task *RunPgBackup* (daily 00:00) |

The new version reads the same database. The DB change (migration 003) only **adds** tables and a view, so the old
folder keeps working for rollback.

---

## Part A — review of the current setup (26/11/2026)

### DB sync (`sql_to_pg_sync.log`, 22/09 → 26/11)

- Healthy overall: 334k lines, 15 errors, all on 22–24/09 (config/ODBC driver set-up and the `"NAN"` text value,
  fixed by the table rules — 60,083 NULL/NaN rows and 152 duplicates moved to `Monitors_info2_rejected`).
  Yafo, Ashdod, Ashkelon, Eilat: 1,440 rows/day.
- **Acre has had no new rows since 25/11 22:39** (1,400 on 24/11, 1,361 on 25/11, 0 on 26/11). The sync asks
  SSMS every minute and gets nothing, so the gap is at the station/logger or the contractor's SQL Server, not in
  the sync. Once data arrives in SSMS, the sync fills the gap by itself (3 h look-back each minute, 14 days every 6 h).
- The log file **never rotates** (22.7 MB in 2 months) and every line is written **twice** — also to
  `logs\continuous_sync_run.log`, which the 7-day clean-up never deletes because it is written every minute.
- At boot, if PostgreSQL starts after the task, the script stops (`Failed to create PostgreSQL pool` → exit) and
  nothing restarts it until the next reboot. The `.bat` always ends with `exit /b 0`, so Task Scheduler never sees
  a failure.
- Weekly *Database Sync* re-reads **everything since 2024-01-01** every Sunday — ~1M rows per station through the
  contractor's server — although the continuous sync already re-checks 14 days every 6 hours.
- `Script_Backfill_No_Eilat_…py` is an identical copy of the main script (Eilat is active in it too); two copies
  will drift apart.
- `config.ini` holds the PostgreSQL **superuser** password and the SQL Server password in plain text, readable by
  anyone who can open the Desktop. Restrict it now (step B6) and move to a dedicated DB user later.

### Task Scheduler

- *Database Sync - SSMS to Postgres*: the action has a stray argument
  (`SSMS - Postgres22\SSMS_2_Postgresql_Automation_.bat` after the program). Harmless today, but clean it.
  No restart if it stops (see above).
- Two tasks start the dashboard, both pointing at the **old feature-branch folder**:
  `start_server.bat` (API only, needs `backend\venv`) and the watchdog → `start_servers_noninteractive.bat`.
- `start_app.bat` killed **every** `python.exe` — including the DB sync. Fixed in this version: it now stops only
  what listens on 30886/30887.

All fixes are in this branch: `scripts\onprem\db_sync\` (sync script + 2 bats + `config.ini.example`),
`scripts\onprem\watchdog.ps1`, `scripts\onprem\start_servers_noninteractive.bat`.

---

## Part B — step by step

Do it over RDP/VNC as `slg`, in an **Administrator** command prompt. About 45 minutes. Users see the old
dashboard until step B5.

### B0. Backup

```bat
"C:\Program Files\PostgreSQL\<version>\bin\pg_dump.exe" -U postgres -Fc -f C:\Backup\sealevel_before_v3.dump <dbname>
```
(or pgAdmin → right-click the database → *Backup…*). Check that last night's *RunPgBackup* file exists too.

### B1. Get the new code

GitHub → branch **`fix/review-hydras-editor-aws`** → *Code → Download ZIP*. Extract to a **new** folder:

```
C:\Users\slg\Desktop\Ben\Sea_Level_Dashboard\Sea_Level_Dashboard_v3
```
(below this is called `%APP%`). Do not touch the old folder.

### B2. Settings

```bat
cd /d C:\Users\slg\Desktop\Ben\Sea_Level_Dashboard\Sea_Level_Dashboard_v3\backend
copy .env.onprem.example .env
notepad .env
```
- `DB_URI` → copy the line from the **old** folder's `backend\.env`.
- `CORS_ORIGINS` → every address users type, with `:30887` (already lists 85.155.88.90, 5.102.231.16,
  sea-level-dash-local, localhost). Add any other.
- Optional: `REPORTS_DIR=C:\SeaLevel_reports` for the Reports tab output.

### B3. Python and Node packages

```bat
cd /d %APP%\backend
python -m venv venv
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt

cd /d %APP%\frontend
npm install
npm run build-govmap
```
The build takes a few minutes and creates `frontend\build`. It must finish with *Compiled successfully*.

### B4. Database migration (once; safe to repeat)

pgAdmin → your database → *Query Tool* → open `%APP%\backend\migrations\003_calibration_layer.sql` → **Run**
(or `psql -U postgres -d <dbname> -f migrations\003_calibration_layer.sql`).
It creates `Calibration_Offsets`, `Calibration_Audit`, `Calibration_Audit_Rows` and the view
`Monitors_effective`. `Monitors_info2` is not changed, and the sync keeps writing to it as before.

### B5. Switch the dashboard to the new folder

1. Task Scheduler → *Sea Level Da…* (**At system startup**, `backend\start_server.bat`) → right-click
   **Disable**. The watchdog alone is enough.
2. *Sea Level Da…* (**repeat every 00:01:00**, `watchdog.ps1`) → right-click **Disable** for now.
3. Stop the old dashboard (only ports 30886/30887 — the DB sync keeps running):
   ```bat
   powershell -Command "Get-NetTCPConnection -LocalPort 30886,30887 -State Listen | Select -Expand OwningProcess -Unique | %% { Stop-Process -Id $_ -Force }"
   ```
   (in PowerShell write `%` instead of `%%`).
4. Start the new one:
   ```bat
   %APP%\scripts\onprem\start_servers_noninteractive.bat
   ```
   Wait ~30 s. `%APP%\logs\backend.log` should end with `Uvicorn running on http://0.0.0.0:30886`.
5. Watchdog task → *Properties* → *Actions* → *Edit*:
   - Program/script: `powershell.exe`
   - Add arguments:
     `-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\Users\slg\Desktop\Ben\Sea_Level_Dashboard\Sea_Level_Dashboard_v3\scripts\onprem\watchdog.ps1"`
   - Start in: `C:\Users\slg\Desktop\Ben\Sea_Level_Dashboard\Sea_Level_Dashboard_v3\scripts\onprem`
   - *Settings* tab: **If the task is already running → Do not start a new instance**; untick *Stop the task if
     it runs longer than*.
   - OK (it asks for slg's password) → right-click **Enable**.
6. Test the watchdog: run step 3 again (stop the dashboard) → within 1–2 minutes both ports are back, and
   `%APP%\logs\watchdog.log` shows `Down (api=False, site=False) - running …`.

### B6. DB sync — install the hardened scripts

Same folder as today (`C:\Users\slg\Desktop\Automation SSMS - Postgres22`), same `config.ini`.

1. Task Scheduler → *Database Sync - SSMS to Postgres* → **End** (stops the sync; a few minutes of pause is fine,
   it catches up by itself).
2. In that folder, rename the old files to `*.old`, then copy in from `%APP%\scripts\onprem\db_sync\`:
   `Raw_Monitors_info2_BackupScript_Automation1.py`, `SSMS_2_Postgresql_Automation_.bat`,
   `Backfill_Monitors_info2.bat`. Keep `config.ini`. Move
   `Script_Backfill_No_Eilat_Raw_Monitors_info2_BackupScript_Automation1 - .py` to `*.old` (no longer used).
   - What changed in the `.py`: rotating log (10 MB × 5 files), console gets only warnings/errors, the backfill
     writes its own `sql_to_pg_backfill.log`, and at boot it waits up to 10 min for PostgreSQL instead of dying.
     The sync logic itself is unchanged.
3. Protect the passwords:
   ```bat
   icacls "C:\Users\slg\Desktop\Automation SSMS - Postgres22\config.ini" /inheritance:r /grant:r slg:F SYSTEM:F Administrators:F
   ```
4. *Database Sync - SSMS to Postgres* → *Properties*:
   - *Actions* → *Edit*: Program/script `"C:\Users\slg\Desktop\Automation SSMS - Postgres22\SSMS_2_Postgresql_Automation_.bat"`,
     **Add arguments: empty**, Start in: `C:\Users\slg\Desktop\Automation SSMS - Postgres22`.
   - *Triggers*: keep *At system startup*, add **New… → Daily, 00:00, Repeat task every 5 minutes, for a duration
     of Indefinitely**. With the setting below this restarts the sync within 5 minutes if it ever stops, and does
     nothing while it runs.
   - *Settings*: **If the task is already running → Do not start a new instance**; untick *Stop the task if it
     runs longer than 3 days*.
   - OK → right-click **Run**.
5. *Database Sync* (weekly) → *Actions* → *Edit*: same `Backfill_Monitors_info2.bat`, no arguments,
   same Start in. It now re-reads the **last 60 days** (edit `BACKFILL_DAYS` in the bat to change). For a
   one-time full refill run `Backfill_Monitors_info2.bat 2024-01-01` by hand.
6. Check after 2 minutes: `sql_to_pg_sync.log` shows a new `Starting SQL Server to PostgreSQL Sync Service`,
   then `Deep check (14 days) done`, then `Yafo: 1 new …` every minute. `logs\continuous_sync_run.log` stays
   almost empty.

### B7. Reports on a schedule (optional)

```bat
schtasks /Create /TN "SeaLevel Monthly Reports" /SC MONTHLY /D 1 /ST 05:15 /RU slg /RP * /TR "\"%APP%\scripts\onprem\website_reports.bat\" monthly"
schtasks /Create /TN "SeaLevel Yearly Reports" /SC MONTHLY /M JAN /D 2 /ST 05:30 /RU slg /RP * /TR "\"%APP%\scripts\onprem\website_reports.bat\" yearly"
```
(write the full path instead of `%APP%`). Test once by hand: `website_reports.bat monthly`.

### B8. Verify

| Where | Check |
|---|---|
| Your PC → `http://85.155.88.90:30887` | data loads; **no** Calibration checkbox, **no** Reports tab |
| Server → `http://localhost:30887` | **Admin** badge, Calibration Correction, Reports tab |
| Graph | Tidal Data shows ▲/▼; sun icons at sunrise/sunset |
| Reboot the server (when convenient) | within ~5 min: dashboard up (watchdog), sync running (`sql_to_pg_sync.log`) |

### Rollback

Disable the watchdog task, stop ports 30886/30887 (B5.3), point the watchdog back at the old folder's
`watchdog.ps1` and enable it. For the sync, rename the `*.old` files back. The old dashboard ignores the new
tables; corrections made in the new editor stay in `Calibration_Offsets` and are not shown by the old version.

### Later (not needed today)

- Dedicated PostgreSQL login for the sync instead of `postgres` (SQL in `config.ini.example`), and change the
  `postgres` password once nothing else uses it.
- When AWS is live, the dashboard tasks are retired; the DB sync stays (AWS copies from this PostgreSQL)
  (see `docs/aws/DEPLOYMENT_PLAN.md`).
