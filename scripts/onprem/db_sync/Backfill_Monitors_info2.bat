@echo off
REM Weekly safety net: re-read the last BACKFILL_DAYS days from SSMS and add any rows that are missing.
REM (The continuous sync already re-checks 14 days every 6 h; a full re-read from 2024 every week is not needed.)
REM One-time full refill:  Backfill_Monitors_info2.bat 2024-01-01
REM Task Scheduler: "Database Sync" (weekly, Sunday 02:00) - see docs\guides\ONPREM_UPGRADE.md, part B.
setlocal
set "BACKFILL_DAYS=60"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "LOGDIR=%ROOT%\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOGFILE=%LOGDIR%\backfill_run.log"

powershell -NoProfile -Command "Get-ChildItem -Path '%LOGDIR%' -Filter '*.log*' | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) -or $_.Length -gt 5MB } | Remove-Item -Force -ErrorAction SilentlyContinue"

set "FROM=%~1"
if "%FROM%"=="" for /f %%d in ('powershell -NoProfile -Command "(Get-Date).AddDays(-%BACKFILL_DAYS%).ToString('yyyy-MM-dd')"') do set "FROM=%%d"

echo === BACKFILL FROM %FROM%: %date% %time% === >> "%LOGFILE%"
cd /d "%ROOT%"
REM Same script as the continuous sync (the old "No_Eilat" copy is no longer needed). Full log: sql_to_pg_backfill.log
python "Raw_Monitors_info2_BackupScript_Automation1.py" --backfill-from %FROM% >> "%LOGFILE%" 2>&1
set "RC=%ERRORLEVEL%"
echo === BACKFILL DONE (exit %RC%): %date% %time% === >> "%LOGFILE%"
exit /b %RC%
