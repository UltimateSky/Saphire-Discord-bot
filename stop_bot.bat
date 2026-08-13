@echo off
cd /d "%~dp0"
echo ===================================================
echo   Sapphire Discord Bot - Stop Service
echo ===================================================
echo.
echo Menghentikan bot di background...
taskkill /F /IM pythonw.exe 2>nul
echo.
echo [OK] Bot dan Web Dashboard berhasil dimatikan.
echo.
pause
