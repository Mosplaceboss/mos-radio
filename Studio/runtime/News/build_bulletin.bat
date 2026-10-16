@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1 && (
  py -3 "%~dp0build_bulletin.py" %*
  exit /b %ERRORLEVEL%
)
python "%~dp0build_bulletin.py" %*
exit /b %ERRORLEVEL%
