@echo off
title Push Retro Topup to GitHub
color 0b
echo ========================================================
echo        PUSHING RETRO TOPUP TO GITHUB
echo ========================================================
echo.
git init
git config user.name "shafinalhasan7"
git config user.email "shafinalhasan7@users.noreply.github.com"
git branch -M main
git remote remove origin >nul 2>&1
git remote add origin https://github.com/shafinalhasan7/retro-topup.git
git add .
git commit -m "Deploy Retro Topup platform"
echo.
echo [INFO] Pushing to GitHub...
git push -u origin main
echo.
echo ========================================================
echo [SUCCESS] Code pushed to GitHub!
echo Now go to https://dashboard.render.com and deploy for free!
echo ========================================================
pause
