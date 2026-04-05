@echo off
chcp 65001 >nul
echo 启动 STM32 上位机监视程序...
py -3.11 "%~dp0main.py"
pause
