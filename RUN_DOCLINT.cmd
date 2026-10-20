@echo off
setlocal
cd /d "%~dp0"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 py -3 -m venv .venv
    if errorlevel 1 goto error
)
".venv\Scripts\python.exe" -m pip --version >nul 2>&1
if errorlevel 1 (
    ".venv\Scripts\python.exe" -m ensurepip --upgrade
    if errorlevel 1 goto error
)
".venv\Scripts\python.exe" -m pip install -r "DocLint\requirements.txt"
if errorlevel 1 goto error
".venv\Scripts\python.exe" "DocLint\launch.py"
if errorlevel 1 goto error
exit /b 0
:error
echo.
echo Chua khoi dong duoc. Giu nguyen thong bao loi o tren de kiem tra.
pause
exit /b 1
