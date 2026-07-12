@echo off
setlocal
cd /d "%~dp0\..\Inventory"
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
  python -m pip install pyinstaller
)
python -m PyInstaller ^
  --noconfirm --clean --windowed ^
  --name "MoPlaceInventory" ^
  app\main.py
echo.
echo EXE created in Inventory\dist\MoPlaceInventory\
pause
