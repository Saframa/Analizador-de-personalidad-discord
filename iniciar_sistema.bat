@echo off
title Lanzador de Discord AI Profiler
echo ===================================================
echo   Iniciando Discord AI Profiler ^& Digital Twin 
echo ===================================================
echo.

cd /d "%~dp0"

echo [1/2] Iniciando Bot Grabador de Discord (Node.js)...
start "Discord Voice Recorder" cmd /k "cd /d ""%~dp0services\voice-recorder"" && npm start"

echo [2/2] Iniciando Vigilante de IA 24/7 (Python / CUDA RTX 4070)...
start "AI Pipeline Watcher" cmd /k "cd /d ""%~dp0services\ai-pipeline"" && python main.py watch"

echo.
echo ===================================================
echo  Ambos servicios estan corriendo en sus ventanas!
echo  Podes minimizarlas y usar tu PC con normalidad.
echo ===================================================
timeout /t 4
