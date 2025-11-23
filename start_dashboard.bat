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

REM Step 1: Build frontend
echo [1/3] Building frontend production bundle...
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

REM Step 2: Check and start Redis
cd /d "%~dp0"
echo [2/3] Checking Redis service...
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

REM Step 3: Start backend server
echo [3/3] Starting backend server...
echo.
echo ========================================
echo   DASHBOARD STARTING
echo ========================================
echo.
echo   URL for clients: http://5.102.231.16:30886
echo   API Documentation: http://5.102.231.16:30886/docs
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
