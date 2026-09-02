@echo off
echo ===================================================
echo   Starting Minimal Candlestick Pattern Alerts App
echo   Confidence Filter: >75%% Only
echo ===================================================
echo Opening http://127.0.0.1:8000 in your browser...
start http://127.0.0.1:8000
python app.py
pause
