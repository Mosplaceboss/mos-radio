@echo off
REM Start Piper TTS HTTP server on 127.0.0.1:5000 (Office PC).
REM Leave this window open while the station needs request intros / Kathy voice.
setlocal EnableExtensions
cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=5000"
set "VOICE=en_US-lessac-medium"

echo.
echo === Mo's Place Radio — Start Piper TTS ===
echo Target: http://%HOST%:%PORT%
echo Voice:  %VOICE%
echo.

where py >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python launcher "py" was not found.
  echo Install Python 3.11 or 3.12 from python.org, then run this again.
  pause
  exit /b 1
)

echo Checking for Piper...
py -m piper --help >nul 2>&1
if errorlevel 1 (
  echo Piper not installed. Installing piper-tts[http]...
  py -m pip install "piper-tts[http]"
  if errorlevel 1 (
    echo.
    echo Install failed on this Python. Listing available Pythons:
    py -0p
    echo.
    echo Try:  py -3.12 -m pip install "piper-tts[http]"
    echo Then run this bat again.
    pause
    exit /b 1
  )
)

echo Ensuring voice model is downloaded...
py -m piper.download_voices %VOICE%
if errorlevel 1 (
  echo Voice download failed. Check internet, then try again.
  pause
  exit /b 1
)

echo.
echo Starting Piper. Leave this window OPEN.
echo Browser check: http://%HOST%:%PORT%
echo Press Ctrl+C only when you want to stop Piper.
echo.
py -m piper.http_server -m %VOICE% --host %HOST% --port %PORT%
set "RC=%ERRORLEVEL%"
echo.
echo Piper exited with code %RC%.
pause
exit /b %RC%
