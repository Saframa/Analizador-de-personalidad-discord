@echo off
setlocal
cd /d "%~dp0services\desktop-gui"

echo =================================================================
echo   DISCORD TWIN PROFILER - INICIANDO APLICACION DE ESCRITORIO
echo =================================================================
echo.

if not exist "node_modules" (
    echo [INFO] Instalando dependencias de Node.js...
    call npm install
    if errorlevel 1 (
        echo [ERROR] Fallo npm install.
        pause
        exit /b 1
    )
)

echo [INFO] Iniciando aplicacion de escritorio (Electron + React + FastAPI)...
call npm run dev

if errorlevel 1 (
    echo.
    echo [ERROR] La aplicacion se cerro con errores.
    pause
)
