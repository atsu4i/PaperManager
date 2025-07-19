@echo off
:: Paper Manager GUI 起動スクリプト (Windows用)
title Paper Manager GUI

echo ========================================
echo    Paper Manager GUI 起動中...
echo ========================================
echo.

:: 仮想環境がある場合は有効化
if exist "paper_manager_env\Scripts\activate.bat" (
    echo 仮想環境を有効化しています...
    call paper_manager_env\Scripts\activate.bat
)

:: GUI起動
echo Streamlit GUIを起動しています...
echo ブラウザが自動的に開きます。
echo 終了する場合はこのウィンドウでCtrl+Cを押してください。
echo.

python start_gui.py

pause