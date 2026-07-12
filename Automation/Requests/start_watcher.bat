@echo off
REM Launcher stub — replace with your existing Request Watcher start script.
echo %DATE% %TIME% start >> "%~dp0requests.log"
echo. > "%~dp0.running"
exit /b 0
