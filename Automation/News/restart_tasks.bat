@echo off
setlocal
if exist "%~dp0.running" del "%~dp0.running"
if exist "%~dp0running.lock" del "%~dp0running.lock"
if exist "%~dp0engine.pid" del "%~dp0engine.pid"
if exist "%~dp0engine.local.cmd" (
  call "%~dp0engine.local.cmd"
  exit /b %ERRORLEVEL%
)
echo %DATE% %TIME% restart blocked: engine.local.cmd not configured >> "%~dp0news.log"
echo Configure engine.local.cmd to restart MosNews before News tasks can run. >> "%~dp0news.log"
exit /b 1
