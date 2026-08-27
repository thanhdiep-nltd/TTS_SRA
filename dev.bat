@echo off
set "ROOT_DIR=%~dp0"

echo =========================================
echo   Starting TTS_SRA Backend ^& Frontend
echo =========================================

echo [0/2] Cleaning up any old processes on ports 8000 and 3000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)

echo [1/2] Launching FastAPI Backend (port 8000)...
start "Backend FastAPI" cmd /k "cd /d "%ROOT_DIR%" && "%ROOT_DIR%.venv\Scripts\python.exe" -m uvicorn src.main:app --reload --port 8000"

echo [2/2] Launching Next.js Frontend (port 3000)...
start "Frontend Next.js" cmd /k "cd /d "%ROOT_DIR%frontend" && npm run dev"

echo.
echo Done! Old servers stopped and both services are starting cleanly in separate windows.
