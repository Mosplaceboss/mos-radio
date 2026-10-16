@echo off
setlocal
cd /d "%~dp0"
REM Write today's newscast first.
REM Morning: Mo, Johnny, Dave, Michael G, Mo.
REM Midday: Mo, Johnny, Bailey, Michael G, Mo.
REM bulletin.txt is D:\MosPlaceRadioPlatform\Automation\News\bulletin.txt on the Office PC.
call "%~dp0build_bulletin.bat" %*
if errorlevel 1 echo %DATE% %TIME% build_bulletin failed >> "%~dp0news.log"
REM Keep the station engine hook. It must speak bulletin.txt, not yesterday's script.
if exist "%~dp0engine.local.cmd" (
  call "%~dp0engine.local.cmd"
  exit /b %ERRORLEVEL%
)
echo %DATE% %TIME% wrote bulletin.txt; engine.local.cmd is not beside this bat >> "%~dp0news.log"
exit /b 0
