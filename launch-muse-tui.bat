@echo off
rem M.U.S.E. — launch the Observatory TUI in the current console
set HERMES_HOME=C:\Users\Echer\AppData\Local\hermes
cd /d C:\Users\Echer\M.U.S.E\ui-tui
set HERMES_PYTHON=C:\Users\Echer\M.U.S.E\.venv\Scripts\python.exe
set FORCE_COLOR=3
set COLORTERM=truecolor
node node_modules\tsx\dist\cli.mjs src\entry.tsx %*
