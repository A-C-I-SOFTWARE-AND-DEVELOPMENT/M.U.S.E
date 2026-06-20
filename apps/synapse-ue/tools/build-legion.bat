@echo off
rem ===========================================================================
rem  SYNAPSE - full build on the owner's Windows machine (e.g. the Legion).
rem
rem  One double-click: compiles SynapseEditor (Win64 Development,
rem  warnings-as-errors -> SynapseCore/MuseSacredGeometry, SynapseNet,
rem  SynapseObservatory, SynapseObservatoryRender) and then runs the headless
rem  Synapse.Geometry automation suite (no GPU needed).
rem
rem  Prereqs: Unreal Engine 5.6 + Visual Studio 2022 (Game Dev with C++).
rem  Override the engine path if it is not the default install location:
rem     set "UE_ROOT=D:\Epic\UE_5.6"  &  call build-legion.bat
rem
rem  Staged source - validated by review here (no UE in the authoring
rem  container); this is meant to RUN on the owner's machine.
rem ===========================================================================
setlocal EnableExtensions
call :main
set "RC=%ERRORLEVEL%"
rem Pause only when launched by double-click, so output stays readable.
echo %cmdcmdline% | find /i "%~nx0" >nul && pause
endlocal & exit /b %RC%

:main
if not defined UE_ROOT set "UE_ROOT=C:\Program Files\Epic Games\UE_5.6"
set "TARGET=SynapseEditor"
set "PLATFORM=Win64"
set "CONFIG=Development"

rem This script lives in <project>\tools\ ; resolve the project root.
pushd "%~dp0.."
set "PROJ_DIR=%CD%"
popd
set "UPROJECT=%PROJ_DIR%\Synapse.uproject"
set "BUILD_BAT=%UE_ROOT%\Engine\Build\BatchFiles\Build.bat"
set "EDITOR_CMD=%UE_ROOT%\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"

echo ===========================================================
echo  SYNAPSE full build
echo    UE_ROOT : %UE_ROOT%
echo    Project : %UPROJECT%
echo ===========================================================
echo.

if not exist "%UPROJECT%" (
	echo [ERROR] Synapse.uproject not found at "%UPROJECT%".
	echo         Run this script from inside the project's tools\ folder.
	exit /b 1
)
if not exist "%BUILD_BAT%" (
	echo [ERROR] Unreal Engine 5.6 not found at "%UE_ROOT%".
	echo         Install UE 5.6 or set UE_ROOT to your install dir, then re-run.
	exit /b 1
)

echo [1/2] Compiling %TARGET% %PLATFORM% %CONFIG% ...
call "%BUILD_BAT%" %TARGET% %PLATFORM% %CONFIG% -Project="%UPROJECT%" -WaitMutex
if errorlevel 1 (
	echo.
	echo [FAILED] Compile failed. Fix the errors above and re-run.
	exit /b 1
)
echo [OK] compile clean.
echo.

echo [2/2] Running Synapse.Geometry automation tests ^(headless, null RHI^) ...
if not exist "%PROJ_DIR%\Saved\Automation" mkdir "%PROJ_DIR%\Saved\Automation" >nul 2>&1
call "%EDITOR_CMD%" "%UPROJECT%" -ExecCmds="Automation RunTests Synapse.Geometry; Quit" -TestExit="Automation Test Queue Empty" -unattended -nopause -nullrhi -nosplash -log -ReportOutputPath="%PROJ_DIR%\Saved\Automation"

echo.
echo ===========================================================
echo  DONE.  Compile: OK
echo  Tests:  open  %PROJ_DIR%\Saved\Automation\index.html
echo  Next :  open Synapse.uproject in UE 5.6, drop an
echo          AObservatoryGalaxyActor, assign a sphere NodeMesh,
echo          console:  muse.Observatory.LayoutMode 4
echo ===========================================================
exit /b 0
