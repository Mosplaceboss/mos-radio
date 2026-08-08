@echo off
setlocal
if exist "%~dp0engine.local.cmd" (
  call "%~dp0engine.local.cmd"
  exit /b %ERRORLEVEL%
)
echo %DATE% %TIME% start blocked: engine.local.cmd not configured >> "%~dp0requests.log"
echo Configure engine.local.cmd to start MoRequestsWatcher before Requests can run. >> "%~dp0requests.log"
if exist "%~dp0.running" del "%~dp0.running"
if exist "%~dp0running.lock" del "%~dp0running.lock"
exit /b 1
