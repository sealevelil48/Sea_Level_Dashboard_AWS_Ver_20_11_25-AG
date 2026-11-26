@echo off
REM ============================================================================
REM  Sea Level Dashboard - website reports (on-prem server, Windows Task Scheduler)
REM
REM  website_reports.bat monthly      -> previous month   (run on the 1st of every month)
REM  website_reports.bat yearly       -> previous year    (run on 2 January)
REM
REM  Output: backend\..\reports_output\sea_level_<kind>_<period>.zip  (also listed in the
REM  dashboard's Reports tab) and, extracted in the website layout, under %REPORTS_WEBSITE_DIR%.
REM
REM  Register once (Administrator command prompt; adjust the path):
REM    schtasks /Create /TN "SeaLevel Monthly Reports" /SC MONTHLY /D 1 /ST 05:15 /RU slg /RP * ^
REM      /TR "\"C:\SeaLevel_v3\scripts\onprem\website_reports.bat\" monthly"
REM    schtasks /Create /TN "SeaLevel Yearly Reports" /SC MONTHLY /M JAN /D 2 /ST 05:30 /RU slg /RP * ^
REM      /TR "\"C:\SeaLevel_v3\scripts\onprem\website_reports.bat\" yearly"
REM ============================================================================
setlocal
set KIND=%~1
if "%KIND%"=="" set KIND=monthly
if "%REPORTS_WEBSITE_DIR%"=="" set REPORTS_WEBSITE_DIR=%~dp0..\..\reports_website
if not exist "%~dp0..\..\reports_output" mkdir "%~dp0..\..\reports_output"
cd /d "%~dp0..\..\backend"
set "PY=python"
if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
"%PY%" reports_cli.py %KIND% --out "%REPORTS_WEBSITE_DIR%" --unzip >> "%~dp0..\..\reports_output\reports.log" 2>&1
exit /b %ERRORLEVEL%
