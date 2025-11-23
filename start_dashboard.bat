@echo off
echo ========================================
echo   Sea Level Dashboard - Full Startup
echo ========================================
echo.
echo This script will:
echo   1. Build the frontend (React app)
echo   2. Start Redis cache
echo   3. Start the backend server
echo   4. Serve everything on port 30886
echo.

REM Set default host if not defined
if not defined DASHBOARD_HOST (
    set DASHBOARD_HOST=5.102.231.16
)

REM Step 1: Build frontend
echo [1/4] Building frontend production bundle...
cd /d "%~dp0frontend"
call npm run build-govmap

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Frontend build failed!
    pause
    exit /b 1
)

echo.
echo [OK] Frontend built successfully!
echo.

REM Step 2: Check domain configuration
cd /d "%~dp0"
echo [2/4] Checking domain configuration...
findstr "sea-level-dash-local" C:\Windows\System32\drivers\etc\hosts >nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: Domain not configured!
    echo Please run setup_govmap_domain.bat as Administrator first
    pause
    exit /b 1
)
echo [OK] Domain configured

REM Step 3: Check and start Redis
echo [3/4] Checking Redis service...
sc query Redis >nul 2>&1
if %errorLevel% neq 0 (
    echo Redis service not found. Starting Redis manually...
    start "Redis Server" /D "C:\Users\slg\Downloads\Redis-x64-3.0.504" redis-server.exe --maxmemory 512mb --maxmemory-policy allkeys-lru
    timeout /t 3 >nul
) else (
    echo Redis service found. Starting...
    sc start Redis >nul 2>&1
    echo [OK] Redis started
)

echo.

REM Step 4: Start backend server
echo [4/4] Starting backend server...
echo.
echo ========================================
echo   DASHBOARD STARTING
echo ========================================
echo.
echo   URL for clients: http://%DASHBOARD_HOST%:30886
echo   API Documentation: http://%DASHBOARD_HOST%:30886/docs
echo.
echo   This server provides:
echo   - Frontend (React dashboard)
echo   - REST API (all /api/* endpoints)
echo   - Real-time data from Survey of Israel
echo   - Wave forecasts from IMS
echo.
echo ========================================
echo.

cd backend
python local_server_optimized.py
pause
