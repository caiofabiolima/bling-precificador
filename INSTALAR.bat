@echo off
chcp 65001 >nul
title Instalador - Precificador Bling
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
echo.
pause
