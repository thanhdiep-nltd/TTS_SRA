@echo off
set "ROOT_DIR=%~dp0"

echo =========================================
echo   Starting TTS_SRA Backend ^& Frontend
echo =========================================

echo [1/2] Launching FastAPI Backend (port 8000)...
start "Backend FastAPI" cmd /k "cd /d "%ROOT_DIR%" && .venv\Scripts\activate && python -m uvicorn src.main:app --reload --port 8000"

echo [2/2] Launching Next.js Frontend (port 3000)...
start "Frontend Next.js" cmd /k "cd /d "%ROOT_DIR%frontend" && npm run dev"

echo.
echo Done! Both services are starting in separate windows.
