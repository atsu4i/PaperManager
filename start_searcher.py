#!/usr/bin/env python3
"""
Paper Searcher 起動スクリプト
Streamlit検索アプリケーションを起動します
"""

import sys
import subprocess
from pathlib import Path

def check_streamlit():
    """Streamlitがインストールされているかチェック"""
    try:
        import streamlit
        return True
    except ImportError:
        return False

def main():
    """検索アプリ起動メイン関数"""
    print("🔍 Paper Searcher を起動しています...")

    # 仮想環境の確認
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✅ 仮想環境が有効化されています")
    else:
        print("⚠️  仮想環境が検出されませんでした")

    print(f"🐍 使用中のPython: {sys.executable}")

    # Streamlitのインストール確認
    if not check_streamlit():
        print("❌ Streamlitがインストールされていません")
        print("💡 次のコマンドでインストールしてください:")
        print("   pip install -r requirements.txt")
        print("   または")
        print("   pip install -r search_app/requirements.txt")
        return

    print("✅ Streamlitが利用可能です")
    print("🔎 検索アプリがブラウザで自動的に開きます")
    print("🛑 終了する場合は Ctrl+C を押してください")
    print("-" * 50)

    # 検索アプリケーションのパス
    search_app_path = Path(__file__).parent / "search_app" / "app.py"

    if not search_app_path.exists():
        print(f"❌ 検索アプリケーションが見つかりません: {search_app_path}")
        return

    try:
        # Streamlitアプリを起動（ポート8503）
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", str(search_app_path),
            "--server.address", "localhost",
            "--server.port", "8503",
            "--browser.serverAddress", "localhost",
            "--browser.serverPort", "8503",
            "--server.headless", "false"
        ], check=True)

    except KeyboardInterrupt:
        print("\n👋 Paper Searcher を終了しました")

    except subprocess.CalledProcessError as e:
        print(f"❌ 検索アプリ起動エラー: {e}")
        print("💡 トラブルシューティング:")
        print("   1. 仮想環境でStreamlitをインストール: pip install streamlit")
        print("   2. 仮想環境を有効化してから実行")
        print("   3. Pythonのバージョンを確認 (3.8以上が必要)")

    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")

if __name__ == "__main__":
    main()
