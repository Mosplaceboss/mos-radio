@echo off
REM Emergency repair: rewrite requests.json to Piper-only and remove Voicebox fields.
REM Run on the Office PC inside Automation\Requests, then restart MoRequestsWatcher.
setlocal
set "CFG=%~dp0requests.json"
set "PY=%~dp0repair_tts_to_piper.py"
if not exist "%CFG%" (
  echo requests.json not found next to this script.
  exit /b 1
)
where py >nul 2>&1 && (
  py -3 "%PY%" "%CFG%"
  exit /b %ERRORLEVEL%
)
where python >nul 2>&1 && (
  python "%PY%" "%CFG%"
  exit /b %ERRORLEVEL%
)
echo Python not found. Open Studio → Requests → Fix TTS → Piper Only instead.
exit /b 1
