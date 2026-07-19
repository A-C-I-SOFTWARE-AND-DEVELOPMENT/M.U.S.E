@echo off
"C:\Program Files\Epic Games\UE_5.7\Engine\Build\BatchFiles\Build.bat" SynapseEditor Win64 Development -Project="C:\Users\Echer\M.U.S.E\apps\synapse-ue\Synapse.uproject" -WaitMutex -FromMsBuild 2>&1
echo UE_BUILD_EXIT_CODE=%ERRORLEVEL%
