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
echo Installing required packages...

:: Try requirements.txt first
echo Step 1: Installing from requirements.txt...
pip install -r requirements.txt

if errorlevel 1 (
    echo Warning: requirements.txt failed, trying simplified version...
    echo Step 2: Installing from requirements-simple.txt...
    pip install -r requirements-simple.txt
    
    if errorlevel 1 (
        echo Warning: Simplified installation failed, trying essential packages...
        echo Step 3: Installing essential GUI packages individually...
        pip install streamlit>=1.28.0
        pip install plotly>=5.17.0
        pip install PyYAML>=6.0.0
        pip install python-dotenv>=1.0.0
        pip install pydantic>=2.6.0
        pip install requests>=2.31.0
        
        echo Essential packages installation completed with possible warnings
    )
)

echo.
echo Installation completed successfully!
echo Run start_gui.bat to start the GUI

pause