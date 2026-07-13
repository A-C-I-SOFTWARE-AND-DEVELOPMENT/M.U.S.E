@echo off
REM ─────────────────────────────────────────────────────────────
REM  M.U.S.E Voice - Launcher
REM  Starts the voice assistant server and opens in browser
REM ─────────────────────────────────────────────────────────────

title M.U.S.E Voice

REM Find the Hermes venv Python (has aiohttp)
set HERMES_PY=C:\Users\Echer\AppData\Local\hermes\M.U.S.E\venv\Scripts\python.exe
if not exist "%HERMES_PY%" set HERMES_PY=C:\Users\Echer\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe

echo.
echo   ================================================
echo     M.U.S.E Voice Assistant
echo   ================================================
echo.
echo   Starting server...
echo   URL: http://127.0.0.1:9120
echo.

"%HERMES_PY%" "%~dp0server.py"

pause
