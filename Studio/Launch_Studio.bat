@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements.txt -q
python app\main.py
if errorlevel 1 pause
