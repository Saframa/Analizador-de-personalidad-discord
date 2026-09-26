@echo off
chcp 65001 > nul
title Discord Twin Profiler - Desktop GUI

echo =================================================================
echo   DISCORD TWIN PROFILER - INICIANDO APLICACION DE ESCRITORIO
echo =================================================================
echo.

cd /d "%~dp0services\desktop-gui"

if not exist "node_modules" (
    echo [INFO] Instalando dependencias de Node.js...
    call npm install
    if errorlevel 1 (
        echo [ERROR] Falló npm install.
        pause
        exit /b 1
    )
)

echo [INFO] Iniciando backend IA y Frontend Electron...
call npm run dev

if errorlevel 1 (
    echo.
    echo [ERROR] La aplicación se cerró con errores.
    pause
)
