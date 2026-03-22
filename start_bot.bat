@echo off
title 🎯 DealScope
color 0A

echo.
echo  ================================================
echo   🎯  DealScope
echo   📊  Dashboard: http://localhost:8000
echo  ================================================
echo.

echo  ⏳ Stopping old instances...
taskkill /F /IM python.exe /T 2>nul
timeout /t 2 /nobreak >nul

echo  🚀 Starting bot + dashboard...
echo.

cd /d "%~dp0dealscope"
"..\\.venv\\Scripts\\python.exe" main.py

echo.
echo  ❌ Bot stopped.
pause
