# Run the new version on the physical (on-prem) server — until AWS is live

You can install this branch on the current Windows server today. It reads the same PostgreSQL database.
The database change is **additive** (new tables and a view), so the old version keeps working if you need to
roll back.

## What you get on-prem now

| | Who |
|---|---|
| Dashboard, graph (tides, sunrise/sunset), table, maps, forecasts, CSV | everyone, **no sign-in** (view only) |
| Calibration editor + **Reports** tab | only a browser **on the server itself** (RDP → `http://localhost:30887`) |
| Google sign-in | comes with AWS (Cognito). It can be added on-prem later, but that needs HTTPS. |

The server decides who is admin, not the page: requests from other PCs get HTTP 403 on calibration and
reports, even if someone calls the API directly.

## Steps (≈ 30 min, Administrator command prompt on the server)

1. **Back up the database** (pgAdmin → Backup, or):
   `pg_dump -U <user> -Fc -f D:\backup\sealevel_before_upgrade.dump <dbname>`
2. **Get the code** — GitHub → branch `fix/review-hydras-editor-aws` → *Code → Download ZIP* (or
   `git fetch origin && git checkout fix/review-hydras-editor-aws`). Extract to a **new** folder, e.g.
   `C:\SeaLevel_v3`. Keep the old folder unchanged for rollback.
3. **Settings** — copy `backend\.env.onprem.example` to `backend\.env`, then put in the `DB_URI` from the old
   `backend\.env`. Check `CORS_ORIGINS` lists the addresses users type (port 30887).
4. **Python packages** (the same Python that `start_app.bat` uses):
   `cd C:\SeaLevel_v3\backend` → `python -m pip install -r requirements.txt`
5. **Database migration** (once; safe to repeat):
   `psql -U <user with CREATE rights> -d <dbname> -f migrations\003_calibration_layer.sql`
   This creates `Calibration_Offsets`, `Calibration_Audit*` and the view `Monitors_effective`. It also copies
   the old in-table `Calibration_Offset` values into the audited layer once. `Monitors_info2` is not changed.
6. **Stop the old version** (close its two windows), then run `C:\SeaLevel_v3\start_app.bat` **as Administrator**.
   It builds the frontend (`npm install` the first time; a few minutes) and starts the API (30886) and the site (30887).
7. **Check:**
   - From your PC: `http://85.155.88.90:30887` → data loads, **no** Calibration checkbox, **no** Reports tab.
   - On the server (RDP): `http://localhost:30887` → **Admin** badge, Calibration Correction, Reports tab.
   - Tidal Data → ▲/▼ tides; sun icons on the graph.
8. **Reports on a schedule** (optional) — register the two tasks in `scripts\onprem\website_reports.bat`
   (commands are at the top of the file).

## Rollback

Close the two windows and run the old folder's `start_app.bat`. The old version ignores the new tables and view.
Corrections made with the new editor live in `Calibration_Offsets`, so the old version won't show them.

## Notes

- `start_app.bat` still closes **every** `python.exe` and `node.exe` on the server before starting (old behaviour).
  If anything else runs Python on that machine, start the two windows by hand instead (last lines of the file).
- When AWS is live, the same code runs there with Google sign-in, and the on-prem server can be retired
  (see `docs/aws/DEPLOYMENT_PLAN.md`, phase 5).
