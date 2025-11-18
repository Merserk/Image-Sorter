@echo off
setlocal

REM Prevent Python from writing .pyc files or __pycache__ folders
set "PYTHONDONTWRITEBYTECODE=1"

REM Directory of this .bat file (Image Sorter root)
set "BASE_DIR=%~dp0"
REM Remove trailing backslash if present
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"

REM Paths to embedded Python and the script
set "PYTHON_EXE=%BASE_DIR%\bin\python-3.13.9-embed-amd64\python.exe"
set "SCRIPT=%BASE_DIR%\gui.py"

REM Check Python
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python executable not found:
    echo   "%PYTHON_EXE%"
    echo Make sure python-3.13.9-embed-amd64 is in the bin folder.
    pause
    exit /b 1
)

REM Check script
if not exist "%SCRIPT%" (
    echo [ERROR] Script file not found:
    echo   "%SCRIPT%"
    pause
    exit /b 1
)

REM Change to project root so imports work
cd /d "%BASE_DIR%"

echo Starting Image Sorter...
"%PYTHON_EXE%" "%SCRIPT%"

echo.
echo Image Sorter has exited.
pause
endlocal