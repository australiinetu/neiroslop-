@echo off
chcp 65001 >nul
cd /d "%~dp0"
python survival.py
if errorlevel 1 pause
