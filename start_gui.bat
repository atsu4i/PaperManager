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
    echo 仮想環境が有効化されました: %VIRTUAL_ENV%
) else (
    echo 仮想環境が見つかりません。システムのPythonを使用します。
)

:: GUI起動
echo Streamlit GUIを起動しています...
echo ブラウザが自動的に開きます。
echo 終了する場合はこのウィンドウでCtrl+Cを押してください。
echo.

:: Streamlitがインストールされているか確認
python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo ❌ Streamlitがインストールされていません。
    echo 💡 次のコマンドでインストールしてください:
    echo    pip install streamlit plotly
    echo.
    pause
    exit /b 1
)

python start_gui.py

pause