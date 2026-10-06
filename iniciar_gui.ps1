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

# Liberar puerto 8000 por si quedo algun proceso huerfano anterior
$conn = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($conn) {
    $pids = $conn | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($p in $pids) {
        if ($p -gt 0) {
            Write-Host "[INFO] Liberando puerto 8000 (PID $p)..." -ForegroundColor Yellow
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
        }
    }
}

# Auto-iniciar contenedor de VoiceStudio si existe
try {
    $vsRunning = docker ps --filter "name=voicestudio" --filter "status=running" --format "{{.Names}}" 2>$null
    if (-not $vsRunning) {
        $vsExists = docker ps -a --filter "name=voicestudio" --format "{{.Names}}" 2>$null
        if ($vsExists) {
            Write-Host "[INFO] Iniciando motor de voz VoiceStudio en Docker (segundo plano)..." -ForegroundColor Magenta
            docker start voicestudio 2>$null | Out-Null
        }
    }
} catch {}


Write-Host "[INFO] Iniciando backend IA y Frontend Electron..." -ForegroundColor Green
npm run dev
