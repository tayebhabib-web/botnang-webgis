@echo off
title Botnang WebGIS + BotnangBot

echo ==========================================
echo Starting AI-Assisted Botnang WebGIS...
echo ==========================================
echo.

REM Move to the folder where this BAT file is located
cd /d "%~dp0"

REM Check if backend folder exists
if not exist "backend\server.py" (
    echo ERROR: backend\server.py was not found.
    echo.
    echo Please place this BAT file in the main WebGIS folder,
    echo the same folder where index.html and the backend folder exist.
    echo.
    pause
    exit /b
)

REM Open the WebGIS in browser after a short delay
start "" cmd /c "timeout /t 3 >nul && start http://127.0.0.1:5000/index.html"

REM Start Flask backend from backend folder
cd backend
python server.py

pause
