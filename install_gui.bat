@echo off
:: Paper Manager GUI Install Script (Windows)
title Paper Manager - GUI Dependencies Installation

echo ========================================
echo    Paper Manager GUI Setup
echo ========================================
echo.

:: Check and activate virtual environment
if exist "paper_manager_env\Scripts\activate.bat" (
    echo Activating virtual environment...
    call paper_manager_env\Scripts\activate.bat
    echo Virtual environment activated: %VIRTUAL_ENV%
) else (
    echo Warning: Virtual environment not found.
    echo Do you want to create a virtual environment? (y/n)
    set /p create_venv=">>> "
    if /i "%create_venv%"=="y" (
        echo Creating virtual environment...
        python -m venv paper_manager_env
        call paper_manager_env\Scripts\activate.bat
        echo Virtual environment created successfully
    ) else (
        echo Using system Python
    )
)

echo.
echo Installing GUI packages...

:: Install GUI packages
pip install streamlit>=1.28.0 plotly>=5.17.0

if errorlevel 1 (
    echo Error: Installation failed
    echo Please check your internet connection and try again
    pause
    exit /b 1
)

echo.
echo Installation completed successfully!
echo Run start_gui.bat to start the GUI

pause