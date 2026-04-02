@echo off
REM ETF Trading Analysis System - Run Script (Windows)
REM This script runs the daily analysis

cd /d %~dp0

python main.py --once

exit /b %ERRORLEVEL%
