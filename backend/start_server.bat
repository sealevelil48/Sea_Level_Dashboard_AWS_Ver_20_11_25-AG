@echo off
:: Ensure we are in the backend directory
cd /d "%~dp0"

:: Activate virtual environment and run the server
if exist "venv\Scripts\python.exe" (venv\Scripts\python.exe local_server_optimized.py) else (python local_server_optimized.py)