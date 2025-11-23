@echo off
echo ========================================
echo   Sea Level Dashboard - Backend Only
echo ========================================
echo.
echo NOTE: This starts the backend server ONLY.
echo       Make sure you have built the frontend first!
echo       If you see "static directory not found", run:
echo         cd frontend ^&^& npm run build-govmap
echo.
echo       OR use start_dashboard.bat for full setup.
echo.
echo ========================================
echo.

REM Set default host if not defined
if not defined DASHBOARD_HOST (
    set DASHBOARD_HOST=5.102.231.16
)

REM Check and start Redis service
echo [1/2] Checking Redis service status...
sc query Redis >nul 2>&1
if %errorLevel% neq 0 (
    echo Redis service not installed. Installing Redis service...
    echo Please run as Administrator to install Redis service:
    echo sc create Redis binpath="C:\Users\slg\Downloads\Redis-x64-3.0.504\redis-server.exe --service-run" start=auto
    echo sc start Redis
    echo.
    echo For now, starting Redis manually...
    start "Redis Server" /D "C:\Users\slg\Downloads\Redis-x64-3.0.504" redis-server.exe --maxmemory 512mb --maxmemory-policy allkeys-lru
    timeout /t 3 >nul
) else (
    echo Redis service found. Starting Redis...
    sc start Redis >nul 2>&1
    echo ✅ Redis service started
)

REM Check domain configuration
findstr "sea-level-dash-local" C:\Windows\System32\drivers\etc\hosts >nul
if %errorLevel% neq 0 (
    echo ERROR: Domain not configured!
    echo Please run setup_govmap_domain.bat as Administrator first
    pause
    exit /b 1
)

echo [2/2] Starting optimized backend server on port 30886...
echo.
echo ========================================
echo   SERVER STARTING
echo ========================================
echo   Client URL: http://%DASHBOARD_HOST%:30886
echo   API Docs:   http://%DASHBOARD_HOST%:30886/docs
echo ========================================
echo.
cd backend
python local_server_optimized.py
pause