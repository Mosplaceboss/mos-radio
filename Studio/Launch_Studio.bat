@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements.txt -q
start "" pythonw app\main.py
