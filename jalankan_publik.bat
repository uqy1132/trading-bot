@echo off
title Trading Bot — Full Stack + Public Access
chcp 65001 >nul

echo ============================================================
echo   Trading Bot — Full Stack + Public Access
echo   Backend  : http://localhost:8000
echo   Frontend : http://localhost:5173
echo   Public   : via Cloudflare Tunnel (lihat terminal cloudflared)
echo ============================================================
echo.

REM 1. Backend FastAPI
echo [1/3] Menjalankan Python API server...
start "Trading Bot API" cmd /k "cd /d C:\TradingBot && venv\Scripts\activate && uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak >nul

REM 2. Frontend React
echo [2/3] Menjalankan React frontend...
start "Trading Bot Frontend" cmd /k "cd /d C:\TradingBot\frontend && npm run dev"

timeout /t 3 /nobreak >nul

REM 3. Cloudflare Tunnel untuk akses publik
echo [3/3] Membuka tunnel publik ke frontend (port 5173)...
echo.
echo Pilih metode tunnel:
echo   [1] Cloudflare Tunnel (cloudflared) — URL permanen lebih stabil
echo   [2] ngrok — URL acak tapi mudah
echo.
set /p PILIHAN=Pilih (1 atau 2):

if "%PILIHAN%"=="1" (
    echo Menjalankan cloudflared tunnel...
    start "Cloudflare Tunnel Frontend" cmd /k "cloudflared tunnel --url http://localhost:5173"
    timeout /t 2 /nobreak >nul
    start "Cloudflare Tunnel Backend" cmd /k "cloudflared tunnel --url http://localhost:8000"
    echo.
    echo URL publik akan muncul di window cloudflared ^(format: https://xxxx.trycloudflare.com^)
) else (
    echo Menjalankan ngrok...
    start "ngrok Frontend" cmd /k "ngrok http 5173"
    echo.
    echo URL publik akan muncul di window ngrok
    echo ^(atau buka http://127.0.0.1:4040 untuk dashboard ngrok^)
)

echo.
echo ============================================================
echo PENTING: Jika pakai tunnel, update VITE_API_URL di frontend
echo          agar frontend memanggil backend via URL publik juga!
echo ============================================================
echo.
echo Tekan tombol apapun untuk keluar launcher...
pause >nul
