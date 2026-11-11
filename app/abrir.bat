@echo off
title Precificador Bling (feche esta janela para encerrar)
cd /d "%~dp0"
python app.py || py app.py
if errorlevel 1 pause
