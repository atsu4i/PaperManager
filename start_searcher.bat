@echo off
:: Paper Searcher Launcher (Windows)
title Paper Searcher

echo ========================================
echo    Paper Searcher Starting...
echo ========================================
echo.

:: Check and activate virtual environment
if exist "paper_manager_env\Scripts\activate.bat" (
    echo Activating virtual environment...
    call paper_manager_env\Scripts\activate.bat
    echo Virtual environment activated: %VIRTUAL_ENV%
) else (
    echo Virtual environment not found. Using system Python.
)

:: Check if Streamlit is installed
python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo Error: Streamlit is not installed.
    echo Please run: pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

:: Start Paper Searcher
echo Starting Paper Searcher...
echo Browser will open automatically at http://localhost:8503
echo Press Ctrl+C in this window to exit.
echo.

python start_searcher.py

pause
