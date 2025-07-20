@echo off
:: Paper Manager GUI Launcher (Windows)
title Paper Manager GUI

echo ========================================
echo    Paper Manager GUI Starting...
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

:: Start GUI
echo Starting Streamlit GUI...
echo Browser will open automatically.
echo Press Ctrl+C in this window to exit.
echo.

:: Check if Streamlit is installed
python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo Error: Streamlit is not installed.
    echo Please run: pip install streamlit plotly
    echo Or use: install_gui.bat
    echo.
    pause
    exit /b 1
)

:: Check configuration status
echo Checking configuration...
python check_config.py
if errorlevel 1 (
    echo.
    echo ===============================================
    echo    Configuration Required - Starting Setup
    echo ===============================================
    echo.
    echo Your Paper Manager is not configured yet.
    echo Starting the configuration tool...
    echo.
    pause
    
    :: Start setup tool instead
    start "Paper Manager Setup" setup_config.bat
    exit /b 0
) else (
    echo Configuration OK - Starting main application...
)

python start_gui.py

pause