"""
Paper Manager 設定状況チェックツール
start_manager.bat から呼び出されて設定完了状況を確認する
"""

import os
import sys
from pathlib import Path

def check_configuration():
    """設定が完了しているかチェック"""
    
    # .envファイルの存在確認
    env_path = Path(".env")
    if not env_path.exists():
        return False, "設定ファイル(.env)が見つかりません"
    
    # 環境変数を読み込み
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        return False, "python-dotenvライブラリが見つかりません"
    
    # 必須設定項目をチェック
    required_configs = {
        "GEMINI_API_KEY": "Gemini API Key",
        "NOTION_TOKEN": "Notion Token", 
        "NOTION_DATABASE_ID": "Notion Database ID",
        "GOOGLE_APPLICATION_CREDENTIALS": "Google Cloud認証ファイル"
    }
    
    missing_configs = []
    
    for key, name in required_configs.items():
        value = os.getenv(key)
        if not value or value in ["", "your_gemini_api_key_here", "your_notion_token_here", 
                                 "your_notion_database_id_here", "your_google_credentials_here"]:
            missing_configs.append(name)
    
    # Google Cloud認証ファイルの存在確認
    google_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if google_creds:
        creds_path = Path(google_creds)
        if not creds_path.exists():
            missing_configs.append("Google Cloud認証ファイル（ファイルが見つかりません）")
    
    if missing_configs:
        return False, f"未設定項目: {', '.join(missing_configs)}"
    
    return True, "すべての必須設定が完了しています"

def main():
    """メイン処理"""
    is_configured, message = check_configuration()
    
    if is_configured:
        print("CONFIG_OK")
        sys.exit(0)  # 設定完了
    else:
        print(f"CONFIG_MISSING: {message}")
        sys.exit(1)  # 設定不完全

if __name__ == "__main__":
    main()