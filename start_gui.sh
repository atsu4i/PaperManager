#!/bin/bash
# Paper Manager GUI 起動スクリプト (macOS/Linux用)

echo "========================================"
echo "   Paper Manager GUI 起動中..."
echo "========================================"
echo ""

# 仮想環境がある場合は有効化
if [ -f "paper_manager_env/bin/activate" ]; then
    echo "仮想環境を有効化しています..."
    source paper_manager_env/bin/activate
fi

# GUI起動
echo "Streamlit GUIを起動しています..."
echo "ブラウザが自動的に開きます。"
echo "終了する場合はCtrl+Cを押してください。"
echo ""

python start_gui.py