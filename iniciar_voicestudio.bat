@echo off
title Lanzador de VoiceStudio
echo ===================================================
echo        Iniciando VoiceStudio (Local TTS)
echo ===================================================
echo.

set "VS_EXE=%LOCALAPPDATA%\Programs\VoiceStudio\VoiceStudio.exe"
set "INSTALLER=%USERPROFILE%\Downloads\VoiceStudio-Electron-0.5.6-win-x64.exe"

if exist "%VS_EXE%" (
    echo [OK] VoiceStudio encontrado en el sistema.
    echo Iniciando aplicacion...
    start "" "%VS_EXE%"
) else if exist "%INSTALLER%" (
    echo [INFO] VoiceStudio no esta instalado aun, pero el instalador ya fue descargado en:
    echo        "%INSTALLER%"
    echo.
    echo Ejecutando instalador para completar la instalacion inicial...
    start "" "%INSTALLER%"
) else (
    echo [ADVERTENCIA] No se encontro ni la aplicacion instalada ni el instalador en Downloads.
    echo Podes descargarlo desde: https://github.com/debpalash/VoiceStudio/releases
)

echo.
echo Presiona cualquier tecla para cerrar esta ventana...
pause >nul
