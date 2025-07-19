@echo off
:: Paper Manager GUI インストールスクリプト (Windows用)
title Paper Manager - GUI依存関係インストール

echo ========================================
echo    Paper Manager GUI セットアップ
echo ========================================
echo.

:: 仮想環境がある場合は有効化
if exist "paper_manager_env\Scripts\activate.bat" (
    echo 仮想環境を有効化しています...
    call paper_manager_env\Scripts\activate.bat
    echo 仮想環境が有効化されました: %VIRTUAL_ENV%
) else (
    echo ⚠️ 仮想環境が見つかりません。
    echo 🔧 仮想環境を作成しますか？ (y/n)
    set /p create_venv=">>> "
    if /i "%create_venv%"=="y" (
        echo 仮想環境を作成中...
        python -m venv paper_manager_env
        call paper_manager_env\Scripts\activate.bat
        echo ✅ 仮想環境が作成されました
    ) else (
        echo システムのPythonを使用します
    )
)

echo.
echo 📦 GUI関連パッケージをインストール中...

:: GUI関連パッケージをインストール
pip install streamlit>=1.28.0 plotly>=5.17.0

if errorlevel 1 (
    echo ❌ インストールに失敗しました
    echo 💡 インターネット接続を確認し、再度実行してください
    pause
    exit /b 1
)

echo.
echo ✅ インストール完了！
echo 🚀 start_gui.bat を実行してGUIを起動してください

pause