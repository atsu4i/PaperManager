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

:: Try different installation methods
echo Step 1: Installing from requirements.txt...
pip install -r requirements.txt

if errorlevel 1 (
    echo Warning: requirements.txt failed due to encoding issue
    echo Step 2: Installing from requirements-simple.txt...
    pip install -r requirements-simple.txt
    
    if errorlevel 1 (
        echo Warning: Trying essential packages only...
        pip install streamlit plotly PyYAML python-dotenv pydantic requests
        echo Essential packages installed with possible warnings
    )
)

REM Create necessary directories
echo Creating necessary directories...
if not exist "pdfs" mkdir pdfs
if not exist "processed_pdfs" mkdir processed_pdfs
if not exist "logs" mkdir logs
if not exist "credentials" mkdir credentials

echo.
echo ========================================
echo    Installation Complete!
echo ========================================
echo.
echo You can now:
echo   1. Run GUI: start_gui.bat
echo   2. Run CLI: python cli.py config
echo.
echo First run will show setup wizard for API configuration
echo.

pause