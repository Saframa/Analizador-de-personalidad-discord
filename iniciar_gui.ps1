# Iniciar aplicacion de escritorio
$ErrorActionPreference = "Stop"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  DISCORD TWIN PROFILER - INICIANDO APLICACION DE ESCRITORIO" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$scriptDir\services\desktop-gui"

if (-not (Test-Path "node_modules")) {
    Write-Host "[INFO] Instalando dependencias de Node.js..." -ForegroundColor Yellow
    npm install
}

Write-Host "[INFO] Iniciando backend IA y Frontend Electron..." -ForegroundColor Green
npm run dev
