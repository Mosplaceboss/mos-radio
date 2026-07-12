@echo off
REM Launcher stub — points Studio to your existing LiveDJ watcher. Replace the line below with your live script path.
echo LiveDJ watcher start requested by Mo's Place Studio > "%~dp0livedj.log"
echo %DATE% %TIME% start >> "%~dp0livedj.log"
echo. > "%~dp0.running"
exit /b 0
