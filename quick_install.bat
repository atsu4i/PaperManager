@echo off
:: Paper Manager Quick Install Script (Windows)
title Paper Manager - Quick Install

echo ========================================
echo    Paper Manager Quick Install
echo ========================================
echo.

:: Check and activate virtual environment
if exist "paper_manager_env\Scripts\activate.bat" (
    echo Activating virtual environment...
    call paper_manager_env\Scripts\activate.bat
) else (
    echo Creating virtual environment...
    python -m venv paper_manager_env
    call paper_manager_env\Scripts\activate.bat
)

echo.
echo Installing all dependencies...

:: Install everything from requirements.txt
pip install -r requirements.txt

if errorlevel 1 (
    echo Error: Installation failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo    Installation Complete!
echo ========================================
echo.
echo You can now:
echo   1. Run GUI: start_gui.bat
echo   2. Run CLI: python cli.py config
echo.

pause