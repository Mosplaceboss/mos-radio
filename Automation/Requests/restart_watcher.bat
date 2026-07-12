@echo off
REM Launcher stub — replace with your existing Request Watcher restart script.
echo %DATE% %TIME% restart >> "%~dp0requests.log"
echo. > "%~dp0.running"
exit /b 0
