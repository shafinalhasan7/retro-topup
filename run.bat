@echo off
title Retro Topup - Server
color 0b
echo ========================================================
echo               RETRO TOPUP - SERVER
echo   Bangladesh's Trusted Gaming Top-Up Platform
echo ========================================================
echo.
echo [1] Initializing Database...
py database.py
echo.
echo [2] Starting Retro Topup Web Server at http://127.0.0.1:8000 ...
echo [3] Press Ctrl+C in this window anytime to stop the server.
echo.
start http://127.0.0.1:8000
py -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
pause
