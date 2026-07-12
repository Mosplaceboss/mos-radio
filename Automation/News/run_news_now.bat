@echo off
setlocal
if exist "%~dp0engine.local.cmd" (
  call "%~dp0engine.local.cmd"
  exit /b %ERRORLEVEL%
)
echo %DATE% %TIME% run now >> "%~dp0news.log"
exit /b 0
