@echo off
title Trading Bot — Full Stack

echo ========================================
echo   Trading Bot — Full Stack Launcher
echo   Backend : http://localhost:8000
echo   Frontend: http://localhost:5173
echo ========================================
echo.

REM Jalankan FastAPI backend di background
echo [1/2] Menjalankan Python API server...
start "Trading Bot API" cmd /k "cd /d C:\TradingBot && venv\Scripts\activate && uvicorn api_server:app --reload --port 8000"

REM Tunggu 3 detik sampai backend ready
timeout /t 3 /nobreak >nul

REM Jalankan React frontend
echo [2/2] Menjalankan React frontend...
start "Trading Bot Frontend" cmd /k "cd /d C:\TradingBot\frontend && npm run dev"

timeout /t 2 /nobreak >nul

REM Tanya apakah mau jalankan auto-alert scanner
echo.
echo [3/3] Auto-Alert Scanner (opsional)
echo       Scan otomatis setiap 4 jam + Discord notif saat ada sinyal.
echo.
set /p RUN_ALERT=Jalankan Auto-Alert Scanner? (y/n):
if /i "%RUN_ALERT%"=="y" (
    start "Auto Alert Scanner" cmd /k "cd /d C:\TradingBot && venv\Scripts\activate && python scheduler_alert.py"
    echo ✅ Auto-Alert Scanner aktif!
)

echo.
echo ✅ Semua sudah berjalan!
echo    Backend API   : http://localhost:8000
echo    Frontend      : http://localhost:5173
echo    API Docs      : http://localhost:8000/docs
echo.
echo Tekan tombol apapun untuk menutup launcher ini...
pause >nul
