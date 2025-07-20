"""
Paper Manager 起動診断ツール
初回起動時の問題を特定するためのデバッグスクリプト
"""

import sys
import traceback
from pathlib import Path

print("=== Paper Manager 起動診断 ===")
print(f"Python バージョン: {sys.version}")
print(f"作業ディレクトリ: {Path.cwd()}")

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
print(f"プロジェクトルート: {project_root}")

print("\n--- モジュールインポートテスト ---")

# 1. 基本モジュールのインポートテスト
try:
    import streamlit as st
    print("✅ Streamlit インポート成功")
except Exception as e:
    print(f"❌ Streamlit インポートエラー: {e}")

# 2. 設定モジュールのインポートテスト
try:
    from app.config import load_config
    print("✅ app.config インポート成功")
    
    # 設定読み込みテスト
    try:
        config = load_config()
        print("✅ 設定読み込み成功")
        print(f"   - .envファイル: {(project_root / '.env').exists()}")
        print(f"   - 設定完了状態: {config.is_setup_complete()}")
        print(f"   - 不足設定: {config.get_missing_configs()}")
    except Exception as config_error:
        print(f"⚠️  設定読み込みエラー: {config_error}")
        print("   これは正常（初回起動時）")
        
except Exception as e:
    print(f"❌ app.config インポートエラー: {e}")
    traceback.print_exc()

# 3. GUIコンポーネントのインポートテスト
try:
    from gui.components_internal.setup_wizard import render_setup_wizard
    print("✅ setup_wizard インポート成功")
except Exception as e:
    print(f"❌ setup_wizard インポートエラー: {e}")
    traceback.print_exc()

# 4. ファイル存在確認
print("\n--- ファイル存在確認 ---")
files_to_check = [
    ".env",
    ".env.example", 
    "app/config.py",
    "gui/app.py",
    "gui/components_internal/setup_wizard.py"
]

for file_path in files_to_check:
    full_path = project_root / file_path
    exists = full_path.exists()
    print(f"{'✅' if exists else '❌'} {file_path}: {'存在' if exists else '不存在'}")

# 5. 環境変数確認
print("\n--- 環境変数確認 ---")
import os
env_vars = [
    "GEMINI_API_KEY",
    "NOTION_TOKEN", 
    "GOOGLE_APPLICATION_CREDENTIALS",
    "NOTION_DATABASE_ID"
]

for var in env_vars:
    value = os.getenv(var)
    print(f"{'✅' if value else '❌'} {var}: {'設定済み' if value else '未設定'}")

print("\n--- 推奨解決策 ---")
print("1. 手動設定を試す:")
print("   copy .env.example .env")
print("   notepad .env")
print("   (各API設定を入力)")
print("")
print("2. 設定後にGUIを再起動:")
print("   start_gui.bat")
print("")
print("3. それでも問題が続く場合:")
print("   python debug_startup.py")
print("   (このスクリプトを再実行)")

print("\n=== 診断完了 ===")