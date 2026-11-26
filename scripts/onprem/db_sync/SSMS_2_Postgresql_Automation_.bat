@echo off
REM Continuous SSMS -> PostgreSQL sync (Monitors_info2), every 60 s.
REM Task Scheduler: "Database Sync - SSMS to Postgres" - see docs\guides\ONPREM_UPGRADE.md, part B.
REM Program/script: this file. Add arguments: (empty). Start in: this folder.
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "LOGDIR=%ROOT%\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOGFILE=%LOGDIR%\continuous_sync_run.log"

REM Old run logs (>7 days) and a run log that grew over 5 MB are removed.
powershell -NoProfile -Command "Get-ChildItem -Path '%LOGDIR%' -Filter '*.log*' | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) -or $_.Length -gt 5MB } | Remove-Item -Force -ErrorAction SilentlyContinue"

echo === CONTINUOUS SYNC STARTUP: %date% %time% === >> "%LOGFILE%"
cd /d "%ROOT%"
REM Only warnings, errors and Python crashes reach this file; the full log is sql_to_pg_sync.log (rotating).
python "Raw_Monitors_info2_BackupScript_Automation1.py" >> "%LOGFILE%" 2>&1
set "RC=%ERRORLEVEL%"
echo === CONTINUOUS SYNC STOPPED (exit %RC%): %date% %time% === >> "%LOGFILE%"
REM Return Python's exit code so Task Scheduler sees a crash and the 5-minute re-trigger starts it again.
exit /b %RC%
