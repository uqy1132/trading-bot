@echo off
cd C:\TradingBot
call venv\Scripts\activate
echo.
echo ========================================
echo   Trading Bot Dashboard
echo   Buka browser: http://localhost:8501
echo   Tekan Ctrl+C untuk matikan
echo ========================================
echo.
streamlit run dashboard.py --server.port 8501
pause