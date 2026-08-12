# ==========================================================================
# SKY.NET SAPPHIRE BOT (DISCORD PRO) RUNNER & DEPLOY SYSTEM
# ==========================================================================

Clear-Host
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       SAPPHIRE DISCORD BOT - DEPLOY & RUN SYSTEM           " -ForegroundColor Magenta
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Memeriksa dependensi Python & virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv\Scripts\python.exe") {
    $pythonCmd = ".\venv\Scripts\python.exe"
    Write-Host "[OK] Virtual environment terdeteksi." -ForegroundColor Green
} else {
    $pythonCmd = "python"
    Write-Host "[INFO] Menggunakan Python global system." -ForegroundColor Cyan
}

Write-Host ""
Write-Host "[2/3] Memeriksa konfigurasi token (.env)..." -ForegroundColor Yellow
if (Test-Path ".env") {
    $envContent = Get-Content ".env" -Raw
    if ($envContent -match "DISCORD_TOKEN=(.+)") {
        Write-Host "[OK] Konfigurasi token .env terdeteksi." -ForegroundColor Green
    } else {
        Write-Host "[WARNING] Token belum diisi lengkap di file .env." -ForegroundColor Yellow
    }
} else {
    Write-Host "[WARNING] File .env tidak ditemukan. Pastikan membuat .env terlebih dahulu." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[3/3] Memulai eksekusi Sapphire Discord Bot..." -ForegroundColor Yellow
Write-Host "Tekan CTRL + C di terminal ini kapan saja untuk menghentikan bot." -ForegroundColor Gray
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray

& $pythonCmd bot.py

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "[INFO] Sapphire Bot telah dinonaktifkan." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
