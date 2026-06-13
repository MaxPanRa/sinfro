@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
set "PYTHONW_EXE=%CD%\.venv\Scripts\pythonw.exe"

if not exist "%PYTHON_EXE%" (
    echo Creating virtual environment...
    py -3 -m venv .venv
    if errorlevel 1 (
        python -m venv .venv
    )
)

if not exist "%PYTHON_EXE%" (
    echo Could not create .venv. Please install Python 3.11 or newer.
    pause
    exit /b 1
)

"%PYTHON_EXE%" -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    "%PYTHON_EXE%" -m pip install --upgrade pip
    if errorlevel 1 goto error
    "%PYTHON_EXE%" -m pip install -r requirements.txt
    if errorlevel 1 goto error
)

echo Starting Job Radar...
if exist "%PYTHONW_EXE%" (
    start "" "%PYTHONW_EXE%" "%CD%\run_job_radar.py"
    exit /b 0
)

"%PYTHON_EXE%" run_job_radar.py
if errorlevel 1 goto error

exit /b 0

:error
echo.
echo Job Radar could not start. Review the message above.
pause
exit /b 1
