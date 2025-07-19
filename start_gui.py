#!/usr/bin/env python3
"""
Paper Manager GUI 起動スクリプト
Streamlit Webアプリケーションを起動します
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
    """GUI起動メイン関数"""
    print("🚀 Paper Manager GUI を起動しています...")
    
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
        print("   pip install streamlit plotly")
        return
    
    print("✅ Streamlitが利用可能です")
    print("📱 ブラウザでWebアプリが自動的に開きます")
    print("🛑 終了する場合は Ctrl+C を押してください")
    print("-" * 50)
    
    # GUI アプリケーションのパス
    gui_app_path = Path(__file__).parent / "gui" / "app.py"
    
    if not gui_app_path.exists():
        print(f"❌ GUIアプリケーションが見つかりません: {gui_app_path}")
        return
    
    try:
        # Streamlitアプリを起動
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", str(gui_app_path),
            "--server.address", "localhost",
            "--server.port", "8501",
            "--browser.serverAddress", "localhost",
            "--browser.serverPort", "8501",
            "--server.headless", "false"
        ], check=True)
    
    except KeyboardInterrupt:
        print("\n👋 Paper Manager GUI を終了しました")
    
    except subprocess.CalledProcessError as e:
        print(f"❌ GUI起動エラー: {e}")
        print("💡 トラブルシューティング:")
        print("   1. 仮想環境でStreamlitをインストール: pip install streamlit plotly")
        print("   2. 仮想環境を有効化してから実行")
        print("   3. Pythonのバージョンを確認 (3.8以上が必要)")
    
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")

if __name__ == "__main__":
    main()