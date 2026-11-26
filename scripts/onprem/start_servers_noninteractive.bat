@echo off
REM Sea Level Dashboard - start whatever is not running, with no windows, no pause, no admin check.
REM Called by watchdog.ps1 (Task Scheduler, every minute). Safe to run by hand.
REM Unlike start_app.bat it NEVER kills python.exe / node.exe, so the SSMS->PostgreSQL sync keeps running.
REM Needs a built frontend (frontend\build) - build it once with:  cd frontend && npm install && npm run build-govmap
setlocal
set "APP=%~dp0..\.."
for %%i in ("%APP%") do set "APP=%%~fi"
set "LOGDIR=%APP%\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
REM A log over 20 MB is renamed to *.old when its server is (re)started
powershell -NoProfile -Command "foreach ($n in 'backend','frontend','starter') { $f='%LOGDIR%\'+$n+'.log'; if ((Test-Path $f) -and (Get-Item $f).Length -gt 20MB) { Move-Item $f ($f+'.old') -Force -ErrorAction SilentlyContinue } }"

REM Python: the backend venv if it exists, otherwise python on PATH
set "PY=python"
if exist "%APP%\backend\venv\Scripts\python.exe" set "PY=%APP%\backend\venv\Scripts\python.exe"

REM Redis (optional cache; the API works without it)
sc query Redis >nul 2>&1 && sc start Redis >nul 2>&1

REM API on 30886
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 30886 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    echo %date% %time% starting API with %PY% >> "%LOGDIR%\starter.log"
    start "Sea Level Backend" /MIN /D "%APP%\backend" cmd /c ""%PY%" local_server_optimized.py >> "%LOGDIR%\backend.log" 2>&1"
)

REM Site on 30887
if not exist "%APP%\frontend\build\index.html" (
    echo %date% %time% ERROR frontend\build missing - run npm run build-govmap in %APP%\frontend >> "%LOGDIR%\starter.log"
    exit /b 1
)
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 30887 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    echo %date% %time% starting site on 30887 >> "%LOGDIR%\starter.log"
    start "Sea Level Frontend" /MIN /D "%APP%\frontend" cmd /c "npx --yes serve -s build -l 30887 >> "%LOGDIR%\frontend.log" 2>&1"
)
exit /b 0
