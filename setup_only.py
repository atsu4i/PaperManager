"""
Paper Manager 設定専用ツール
初期設定のみに特化したシンプルなStreamlitアプリ
"""

import streamlit as st
import os
from pathlib import Path

# ページ設定
st.set_page_config(
    page_title="Paper Manager 初期設定",
    page_icon="🚀",
    layout="centered"
)

def main():
    st.title("🚀 Paper Manager 初期設定")
    
    st.markdown("""
    **初期設定を行います。以下の方法から選択してください：**
    """)
    
    # タブで方法を分ける
    tab1, tab2 = st.tabs(["🖱️ GUI設定", "📝 手動設定"])
    
    with tab1:
        render_gui_setup()
    
    with tab2:
        render_manual_setup()

def render_gui_setup():
    """GUI設定"""
    st.markdown("### 🔧 API設定")
    
    # 設定項目
    st.markdown("#### 1. Gemini API Key")
    st.markdown("取得方法: [Google AI Studio](https://aistudio.google.com/) で「Get API key」")
    gemini_key = st.text_input("Gemini API Key", type="password", key="gemini")
    
    st.markdown("#### 2. Google Cloud認証ファイル")
    st.markdown("Google Cloud Consoleでサービスアカウントキー（JSON）をダウンロード")
    uploaded_file = st.file_uploader("JSONファイルをアップロード", type=['json'], key="google")
    
    st.markdown("#### 3. Notion設定")
    st.markdown("取得方法: [Notion Developers](https://www.notion.so/my-integrations)")
    notion_token = st.text_input("Notion Token", type="password", key="notion")
    notion_db_id = st.text_input("Notion Database ID", key="notion_db")
    
    st.markdown("#### 4. オプション設定")
    pubmed_email = st.text_input("PubMed Email (オプション)", key="pubmed")
    slack_token = st.text_input("Slack Bot Token (オプション)", type="password", key="slack")
    slack_user = st.text_input("Slack User ID (オプション)", key="slack_user")
    
    # 保存ボタン
    if st.button("💾 設定を保存", type="primary"):
        if save_config_gui(gemini_key, uploaded_file, notion_token, notion_db_id, 
                          pubmed_email, slack_token, slack_user):
            st.success("✅ 設定が保存されました！")
            st.info("🔄 通常のGUIを起動してください: start_gui.bat")
        else:
            st.error("❌ 設定の保存に失敗しました")

def render_manual_setup():
    """手動設定"""
    st.markdown("### 📝 手動で設定ファイルを作成")
    
    env_path = Path(".env")
    example_path = Path(".env.example")
    
    if not example_path.exists():
        st.warning("⚠️ .env.example ファイルが見つかりません")
        if st.button("📄 .env.example を作成"):
            create_env_example()
            st.success("✅ .env.example を作成しました")
            st.rerun()
    
    st.markdown("#### 手順:")
    st.code("""
# 1. テンプレートをコピー
copy .env.example .env

# 2. テキストエディタで開く  
notepad .env

# 3. 各API設定を入力して保存
""", language="bash")
    
    # 現在の状態表示
    if env_path.exists():
        st.success("✅ .env ファイルが存在します")
        
        # 設定内容をチェック
        config_status = check_env_file()
        st.markdown("**設定状況:**")
        for key, status in config_status.items():
            icon = "✅" if status else "❌"
            st.write(f"{icon} {key}")
        
        if all(config_status.values()):
            st.success("🎉 すべての必須設定が完了しています！")
            st.info("通常のGUIを起動してください: start_gui.bat")
    else:
        st.info("ℹ️ .env ファイルがまだ作成されていません")
    
    # リフレッシュボタン
    if st.button("🔄 設定状況を更新"):
        st.rerun()

def save_config_gui(gemini_key, uploaded_file, notion_token, notion_db_id, 
                   pubmed_email, slack_token, slack_user):
    """GUI設定を保存"""
    try:
        # .envファイルを作成
        env_content = f"""# Paper Manager 設定ファイル
# 自動生成されました

# === 必須設定 ===
GEMINI_API_KEY={gemini_key}
NOTION_TOKEN={notion_token}
NOTION_DATABASE_ID={notion_db_id}
"""

        # Google Cloud認証ファイル処理
        if uploaded_file:
            cred_dir = Path("credentials")
            cred_dir.mkdir(exist_ok=True)
            cred_path = cred_dir / "google_credentials.json"
            
            with open(cred_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            env_content += f"GOOGLE_APPLICATION_CREDENTIALS=./credentials/google_credentials.json\n"
        
        # オプション設定
        if pubmed_email:
            env_content += f"\n# === オプション設定 ===\nPUBMED_EMAIL={pubmed_email}\n"
        if slack_token:
            env_content += f"SLACK_BOT_TOKEN={slack_token}\n"
        if slack_user:
            env_content += f"SLACK_USER_ID_TO_DM={slack_user}\n"
        
        # .envファイルに書き込み
        with open(".env", "w", encoding="utf-8") as f:
            f.write(env_content)
        
        return True
        
    except Exception as e:
        st.error(f"エラー: {e}")
        return False

def check_env_file():
    """既存の.envファイルをチェック"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        required = {
            "GEMINI_API_KEY": bool(os.getenv("GEMINI_API_KEY")),
            "NOTION_TOKEN": bool(os.getenv("NOTION_TOKEN")),
            "NOTION_DATABASE_ID": bool(os.getenv("NOTION_DATABASE_ID")),
            "GOOGLE_APPLICATION_CREDENTIALS": bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
        }
        
        return required
        
    except Exception:
        return {
            "GEMINI_API_KEY": False,
            "NOTION_TOKEN": False, 
            "NOTION_DATABASE_ID": False,
            "GOOGLE_APPLICATION_CREDENTIALS": False
        }

def create_env_example():
    """env.exampleファイルを作成"""
    content = """# Paper Manager 設定ファイル
# このファイルを ".env" という名前でコピーして、各項目を設定してください

# === 必須設定 ===

# Gemini API Key
# 取得方法: https://aistudio.google.com/ で「Get API key」をクリック
GEMINI_API_KEY=your_gemini_api_key_here

# Google Cloud 認証ファイルのパス
# 取得方法: Google Cloud Console でサービスアカウントキー（JSON）をダウンロード
GOOGLE_APPLICATION_CREDENTIALS=./credentials/google_credentials.json

# Notion Integration Token
# 取得方法: https://www.notion.so/my-integrations で「New integration」を作成
NOTION_TOKEN=your_notion_token_here

# Notion Database ID
# 取得方法: NotionデータベースURLの32文字のID部分
NOTION_DATABASE_ID=your_notion_database_id_here

# === オプション設定 ===

# PubMed API用メールアドレス（推奨）
PUBMED_EMAIL=your_email@example.com

# Slack Bot Token（通知機能を使用する場合）
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token

# Slack User ID（通知先のユーザー）
SLACK_USER_ID_TO_DM=U01ABCDEFGH
"""
    
    with open(".env.example", "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    main()