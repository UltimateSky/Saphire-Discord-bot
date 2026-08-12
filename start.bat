@echo off
title FruitBot - Discord Music Bot
echo ============================================
echo    FruitBot - Starting with Virtual Env
echo ============================================
echo.

cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found!
    echo Run: python -m venv venv
    pause
    exit /b 1
)

echo [OK] Virtual environment found.
echo [OK] Starting bot...
echo.

venv\Scripts\python.exe -u bot.py

echo.
echo [BOT STOPPED] Press any key to restart...
pause
goto :eof
