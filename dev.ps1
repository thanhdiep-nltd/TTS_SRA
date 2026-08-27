$rootDir = $PSScriptRoot
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Starting TTS_SRA Backend & Frontend" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

Write-Host "[1/2] Launching FastAPI Backend (port 8000)..." -ForegroundColor Yellow
Start-Process cmd.exe -ArgumentList "/k", "cd /d `"$rootDir`" && `"$rootDir\.venv\Scripts\python.exe`" -m uvicorn src.main:app --reload --port 8000"

Write-Host "[2/2] Launching Next.js Frontend (port 3000)..." -ForegroundColor Yellow
Start-Process cmd.exe -ArgumentList "/k", "cd /d `"$rootDir\frontend`" && npm run dev"

Write-Host ""
Write-Host "Done! Both services are starting in separate windows." -ForegroundColor Green
