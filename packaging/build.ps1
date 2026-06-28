# Build the standalone NexShieldVeil.exe (onedir) with the MediaPipe model bundled.
#
# Usage (from the repo root):
#     .\packaging\build.ps1
#
# Requires the model at models/face_landmarker.task. Produces:
#     dist/NexShieldVeil/NexShieldVeil.exe
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

if (-not (Test-Path "models/face_landmarker.task")) {
    throw "Modele manquant : models/face_landmarker.task (voir README)."
}

Write-Host "==> Installation des dependances de build..." -ForegroundColor Cyan
pip install -e ".[vision,ui,packaging]" -q

Write-Host "==> Build PyInstaller (peut prendre quelques minutes)..." -ForegroundColor Cyan
pyinstaller --noconfirm --clean packaging/nexshieldveil.spec

Write-Host ""
Write-Host "OK -> dist/NexShieldVeil/NexShieldVeil.exe" -ForegroundColor Green
Write-Host "Pour un installeur : compiler packaging/installer.iss avec Inno Setup (iscc)." -ForegroundColor Green
