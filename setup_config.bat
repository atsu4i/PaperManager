@echo off
title Paper Manager - Setup Configuration

echo ========================================
echo    Paper Manager Configuration Setup
echo ========================================
echo.

REM Activate virtual environment
if exist "paper_manager_env\Scripts\activate.bat" (
    echo Activating virtual environment...
    call paper_manager_env\Scripts\activate.bat
) else (
    echo Error: Virtual environment not found
    echo Please run quick_install.bat first
    pause
    exit /b 1
)

echo.
echo Starting configuration tool...
echo Browser will open automatically
echo.

REM Start the setup-only Streamlit app
streamlit run setup_only.py --server.port 8502

pause