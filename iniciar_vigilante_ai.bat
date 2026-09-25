@echo off
title AI Pipeline Watcher & Auto-Cleaner
echo ============================================================
echo  INICIANDO VIGILANTE AUTONOMO DE IA (PROCESADO + PURGA)
echo ============================================================
cd services\ai-pipeline
python main.py watch
pause
