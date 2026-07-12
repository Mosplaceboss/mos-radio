@echo off
REM Launcher stub — replace with your existing News task restart script.
echo %DATE% %TIME% restart >> "%~dp0news.log"
echo. > "%~dp0.running"
exit /b 0
