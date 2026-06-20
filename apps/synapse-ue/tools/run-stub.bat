@echo off
rem ===========================================================================
rem  Start the offline stub gateway and pair the UE client for a PIE smoke.
rem  Writes the bearer token to <project>\Saved\muse_token.txt and launches
rem  tools\stub_gateway.py (default 127.0.0.1:8787). Ctrl+C to stop.
rem  Override the token with:  set "STUB_TOKEN=my-token" & call run-stub.bat
rem  Requires Python 3 on PATH.
rem ===========================================================================
setlocal EnableExtensions

pushd "%~dp0.."
set "PROJ_DIR=%CD%"
popd
if not defined STUB_TOKEN set "STUB_TOKEN=synapse-dev-token"

if not exist "%PROJ_DIR%\Saved" mkdir "%PROJ_DIR%\Saved" >nul 2>&1
rem Write the token with no trailing newline (the gateway client trims, but
rem keep it clean).
<nul set /p="%STUB_TOKEN%" > "%PROJ_DIR%\Saved\muse_token.txt"
echo Wrote bearer token to %PROJ_DIR%\Saved\muse_token.txt
echo Point Project Settings -> MUSE Gateway -> GatewayBaseUrl at http://127.0.0.1:8787
echo.
echo Starting stub gateway (Ctrl+C to stop) ...
python "%~dp0stub_gateway.py" %*

endlocal
