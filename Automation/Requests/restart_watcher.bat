@echo off
setlocal
if exist "%~dp0engine.local.cmd" (
  call "%~dp0engine.local.cmd"
  exit /b %ERRORLEVEL%
)
echo %DATE% %TIME% restart >> "%~dp0requests.log"
echo. > "%~dp0.running"
exit /b 0
