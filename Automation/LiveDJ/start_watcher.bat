@echo off
setlocal
if exist "%~dp0engine.local.cmd" (
  call "%~dp0engine.local.cmd"
  exit /b %ERRORLEVEL%
)
echo LiveDJ watcher start requested by Mo's Place Studio > "%~dp0livedj.log"
echo %DATE% %TIME% start >> "%~dp0livedj.log"
echo Configure engine.local.cmd to call your live LiveDJ watcher. >> "%~dp0livedj.log"
echo. > "%~dp0.running"
exit /b 0
