@echo off
rem M.U.S.E. Observatory TUI launcher
chcp 65001 >nul
title M.U.S.E. Observatory TUI
cd /d C:\Users\Echer\M.U.S.E\ui-tui
set HERMES_PYTHON=C:\Users\Echer\M.U.S.E\.venv\Scripts\python.exe
set FORCE_COLOR=3
set COLORTERM=truecolor
"C:\Users\Echer\AppData\Local\Programs\kimi-desktop\resources\resources\runtime\node.exe" node_modules\tsx\dist\cli.mjs src\entry.tsx
echo.
echo TUI exited. Press any key to close.
pause >nul
