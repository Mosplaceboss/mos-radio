@echo off
setlocal
cd /d "%~dp0\..\Studio"
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
  python -m pip install pyinstaller
)
python -m PyInstaller ^
  --noconfirm --clean --windowed ^
  --name "MoPlaceStudio" ^
  --add-data "config;config" ^
  --add-data "assets;assets" ^
  app\main.py
echo.
echo EXE created in Studio\dist\MoPlaceStudio\
pause
