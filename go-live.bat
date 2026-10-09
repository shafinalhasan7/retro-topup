@echo off
title Retro Topup - Live Online Server
color 0a
echo ========================================================
echo        RETRO TOPUP - LIVE PUBLIC SERVER (TUNNEL)
echo ========================================================
echo.
echo [1] Initializing Database...
py database.py
echo.
echo [2] Starting Local Server in background...
start "" py -m uvicorn server:app --host 127.0.0.1 --port 8000
timeout /t 3 >nul
echo.
echo [3] Connecting to Cloudflare Global Network...
echo ========================================================
echo Your Public Website URL will appear below (.trycloudflare.com):
echo ========================================================
echo.
.\cloudflared.exe tunnel --url http://127.0.0.1:8000
pause
