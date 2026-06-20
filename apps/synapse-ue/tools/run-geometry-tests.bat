@echo off
rem ===========================================================================
rem  Run the SYNAPSE automation suite headlessly (no compile, no GPU).
rem  Default filter is "Synapse.Geometry"; pass another to override, e.g.:
rem     run-geometry-tests.bat Synapse.
rem  Requires a prior successful build (see build-legion.bat).
rem ===========================================================================
setlocal EnableExtensions
call :main %*
set "RC=%ERRORLEVEL%"
echo %cmdcmdline% | find /i "%~nx0" >nul && pause
endlocal & exit /b %RC%

:main
if not defined UE_ROOT set "UE_ROOT=C:\Program Files\Epic Games\UE_5.6"
set "FILTER=%~1"
if "%FILTER%"=="" set "FILTER=Synapse.Geometry"

pushd "%~dp0.."
set "PROJ_DIR=%CD%"
popd
set "UPROJECT=%PROJ_DIR%\Synapse.uproject"
set "EDITOR_CMD=%UE_ROOT%\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"

if not exist "%UPROJECT%" (
	echo [ERROR] Synapse.uproject not found at "%UPROJECT%".
	exit /b 1
)
if not exist "%EDITOR_CMD%" (
	echo [ERROR] Unreal Engine 5.6 not found at "%UE_ROOT%".
	exit /b 1
)

echo Running automation: %FILTER%
if not exist "%PROJ_DIR%\Saved\Automation" mkdir "%PROJ_DIR%\Saved\Automation" >nul 2>&1
call "%EDITOR_CMD%" "%UPROJECT%" -ExecCmds="Automation RunTests %FILTER%; Quit" -TestExit="Automation Test Queue Empty" -unattended -nopause -nullrhi -nosplash -log -ReportOutputPath="%PROJ_DIR%\Saved\Automation"
echo.
echo Report: %PROJ_DIR%\Saved\Automation\index.html
exit /b 0
