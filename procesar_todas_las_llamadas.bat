@echo off
title AI Pipeline Batch Processor
echo ============================================================
echo  PROCESANDO TODAS LAS LLAMADAS PENDIENTES EN LOTE
echo ============================================================
cd services\ai-pipeline
python main.py process --session all --profile --delete-audio
pause
