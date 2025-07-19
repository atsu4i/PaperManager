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
echo Installing all required packages from requirements.txt...

:: Install all packages from requirements.txt
pip install -r requirements.txt

if errorlevel 1 (
    echo Warning: Full installation failed, trying GUI packages only...
    echo Installing essential GUI packages...
    pip install streamlit>=1.28.0 plotly>=5.17.0 PyYAML>=6.0.0 python-dotenv>=1.0.0 pydantic>=2.6.0
    
    if errorlevel 1 (
        echo Error: Installation failed
        echo Please check your internet connection and try again
        pause
        exit /b 1
    )
)

echo.
echo Installation completed successfully!
echo Run start_gui.bat to start the GUI

pause