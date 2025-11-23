@echo off
echo Starting Sea Level Dashboard Backend with Redis Caching...
echo.

REM Check and start Redis service
echo Checking Redis service status...
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

echo Starting optimized backend server on port 30886...
echo This server also serves the frontend - no need to run start_production.bat
echo.
echo Access at: http://5.102.231.16:30886
echo API Docs:  http://5.102.231.16:30886/docs
echo.
cd backend
python local_server_optimized.py
pause