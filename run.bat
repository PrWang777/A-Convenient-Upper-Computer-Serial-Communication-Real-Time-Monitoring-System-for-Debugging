@echo off
chcp 65001 >nul 2>&1
title STM32 Monitor
cd /d "%~dp0"
py -3.11 -X utf8 main.py
pause
