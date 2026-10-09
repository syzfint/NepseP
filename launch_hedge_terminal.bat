@echo off
title APEX QUANTITATIVE TERMINAL - INSTITUTIONAL ASSET MANAGEMENT
color 0A
chcp 65001 >nul
cd /d "%~dp0"
python hedge_terminal.py
pause
