@echo off
setlocal
if exist "%~dp0engine.local.cmd" (
  call "%~dp0engine.local.cmd"
  exit /b %ERRORLEVEL%
)
echo LiveDJ watcher start blocked: engine.local.cmd not configured > "%~dp0livedj.log"
echo %DATE% %TIME% start blocked: engine.local.cmd not configured >> "%~dp0livedj.log"
echo Configure engine.local.cmd to start MosLiveDJ before LiveDJ can talk. >> "%~dp0livedj.log"
if exist "%~dp0.running" del "%~dp0.running"
if exist "%~dp0running.lock" del "%~dp0running.lock"
exit /b 1
