@echo off
REM Launcher stub — replace with your existing News task start script.
echo %DATE% %TIME% start >> "%~dp0news.log"
echo. > "%~dp0.running"
exit /b 0
