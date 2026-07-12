@echo off
REM Launcher stub — replace with your existing LiveDJ restart script.
echo %DATE% %TIME% restart >> "%~dp0livedj.log"
echo. > "%~dp0.running"
exit /b 0
