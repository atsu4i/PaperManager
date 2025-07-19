#!/usr/bin/env python3
"""
Paper Manager GUI 起動スクリプト
Streamlit Webアプリケーションを起動します
"""

import sys
import subprocess
from pathlib import Path

def main():
    """GUI起動メイン関数"""
    print("🚀 Paper Manager GUI を起動しています...")
    print("📱 ブラウザでWebアプリが自動的に開きます")
    print("🛑 終了する場合は Ctrl+C を押してください")
    print("-" * 50)
    
    # GUI アプリケーションのパス
    gui_app_path = Path(__file__).parent / "gui" / "app.py"
    
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
        print("💡 'pip install streamlit' でStreamlitをインストールしてください")
    
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")

if __name__ == "__main__":
    main()