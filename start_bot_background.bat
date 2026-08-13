@echo off
cd /d "%~dp0"
echo ===================================================
echo   Sapphire Discord Bot - Background Runner
echo ===================================================
echo.
echo Menjalankan bot di background (senyap)...
start "" "%~dp0venv\Scripts\pythonw.exe" bot.py
echo.
echo [OK] Bot berhasil dijalankan di background!
echo [OK] Web Dashboard siap diakses: http://127.0.0.1:5000
echo.
timeout /t 3 >nul
