@echo off
echo =================================
echo   論文管理システム
echo =================================
echo.

REM 仮想環境の確認
if exist "venv\Scripts\activate.bat" (
    echo 仮想環境を有効化中...
    call venv\Scripts\activate.bat
) else (
    echo 仮想環境が見つかりません。手動でPython環境を確認してください。
    echo.
)

REM Python実行
echo システムを開始しています...
python cli.py start

echo.
echo システムが終了しました。
pause