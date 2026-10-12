@echo off
echo ========================================
echo   Sea Level Dashboard - Unified Startup
echo ========================================
echo.

REM ────────────────────────────────────────────────
REM STEP 1: Admin Check
REM ────────────────────────────────────────────────
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo ERROR: This script must be run as Administrator!
    echo Right-click start_app.bat and select "Run as administrator"
    echo.
    pause
    exit /b 1
)
echo [OK] Running as Administrator

REM ────────────────────────────────────────────────
REM STEP 2: Domain Setup (sea-level-dash-local)
REM ────────────────────────────────────────────────
echo.
echo [2/6] Checking domain configuration...
findstr "sea-level-dash-local" C:\Windows\System32\drivers\etc\hosts >nul
if %errorLevel% neq 0 (
    echo Adding sea-level-dash-local to hosts file...
    copy C:\Windows\System32\drivers\etc\hosts C:\Windows\System32\drivers\etc\hosts.backup.%date:~-4,4%%date:~-10,2%%date:~-7,2% >nul
    echo 127.0.0.1    sea-level-dash-local >> C:\Windows\System32\drivers\etc\hosts
    echo [OK] Domain added to hosts file
) else (
    echo [OK] Domain already configured
)

REM ────────────────────────────────────────────────
REM STEP 3: Clean Slate - kill old node processes
REM ────────────────────────────────────────────────
echo.
echo [3/6] Stopping any existing node/frontend processes...
taskkill /f /im node.exe 2>nul
timeout /t 2 /nobreak >nul
echo [OK] Old node processes cleared

REM ────────────────────────────────────────────────
REM STEP 4: Build Frontend
REM ────────────────────────────────────────────────
echo.
echo [4/6] Building frontend production bundle (this may take 2-3 minutes)...
echo   - Disabling source maps for faster loading
echo   - Minifying JavaScript and CSS
echo   - Optimizing assets
echo.
cd /d "%~dp0frontend"
call npm run build-govmap

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Frontend build failed! Check the output above.
    echo.
    pause
    exit /b 1
)

cd /d "%~dp0"
echo.
echo [OK] Frontend built successfully!

REM ────────────────────────────────────────────────
REM STEP 5: Redis Check and Startup
REM ────────────────────────────────────────────────
echo.
echo [5/6] Checking Redis service status...
sc query Redis >nul 2>&1
if %errorLevel% neq 0 (
    echo Redis service not installed. Starting Redis manually...
    start "Redis Server" /D "C:\Users\slg\Downloads\Redis-x64-3.0.504" redis-server.exe --maxmemory 512mb --maxmemory-policy allkeys-lru
    timeout /t 3 >nul
    echo [OK] Redis started manually
) else (
    echo Redis service found. Starting Redis...
    sc start Redis >nul 2>&1
    echo [OK] Redis service started
)

REM ────────────────────────────────────────────────
REM STEP 6: Launch Backend and Frontend concurrently
REM ────────────────────────────────────────────────
echo.
echo [6/6] Launching backend and frontend servers...
echo.
echo ========================================
echo   LAUNCHING SERVERS
echo ========================================

REM Set default host if not defined
if not defined DASHBOARD_HOST (
    set DASHBOARD_HOST=5.102.231.16
)

echo   Backend URL:  http://%DASHBOARD_HOST%:30886
echo   API Docs:     http://%DASHBOARD_HOST%:30886/docs
echo   Frontend URL: http://localhost:30887
echo ========================================
echo.

start "Sea Level Backend" cmd /k "cd /d "%~dp0backend" && python local_server_optimized.py"
start "Sea Level Frontend" cmd /k "cd /d "%~dp0frontend" && npx serve -s build -l 30887"

echo.
echo [OK] Both servers are starting in separate windows.
echo Close this window or press any key to exit.
echo.
pause
