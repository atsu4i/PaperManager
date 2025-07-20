"""
Paper Manager - 初期設定ウィザード
初回起動時やAPI設定が不完全な場合の設定画面
"""

import streamlit as st
import os
from pathlib import Path
from typing import Dict, Any

# プロジェクトルートをパスに追加
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.config import save_env_config, load_config


def render_setup_wizard():
    """初期設定ウィザードを表示"""
    
    st.markdown("""
    <div style="text-align: center; padding: 2rem;">
        <h1>🚀 Paper Manager 初期設定</h1>
        <p style="font-size: 1.2em; color: #666;">
            論文管理システムを使用するために必要な設定を行います
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # ステップインジケーター
    _render_step_indicator()
    
    # 設定状態を管理
    if 'setup_step' not in st.session_state:
        st.session_state.setup_step = 1
    if 'setup_config' not in st.session_state:
        st.session_state.setup_config = {}
    
    # 現在のステップに応じて画面を表示
    if st.session_state.setup_step == 1:
        _render_step1_welcome()
    elif st.session_state.setup_step == 2:
        _render_step2_gemini()
    elif st.session_state.setup_step == 3:
        _render_step3_google_cloud()
    elif st.session_state.setup_step == 4:
        _render_step4_notion()
    elif st.session_state.setup_step == 5:
        _render_step5_optional()
    elif st.session_state.setup_step == 6:
        _render_step6_completion()


def _render_step_indicator():
    """ステップインジケーターを表示"""
    steps = [
        "ようこそ",
        "Gemini API",
        "Google Cloud",
        "Notion",
        "オプション",
        "完了"
    ]
    
    cols = st.columns(len(steps))
    current_step = st.session_state.get('setup_step', 1)
    
    for i, (col, step_name) in enumerate(zip(cols, steps), 1):
        with col:
            if i < current_step:
                st.markdown(f"<div style='text-align: center; color: #28a745;'>✅<br>{step_name}</div>", 
                          unsafe_allow_html=True)
            elif i == current_step:
                st.markdown(f"<div style='text-align: center; color: #007bff; font-weight: bold;'>🔵<br>{step_name}</div>", 
                          unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align: center; color: #ccc;'>⚪<br>{step_name}</div>", 
                          unsafe_allow_html=True)


def _render_step1_welcome():
    """ステップ1: ようこそ画面"""
    st.markdown("## 📝 事前準備について")
    
    st.markdown("""
    Paper Managerを使用するには、以下のサービスのアカウントが必要です：
    
    ### 🔑 必須アカウント
    
    1. **Google アカウント** 
       - Gemini API（AI解析用）
       - Google Cloud（PDF読み取り用）
       
    2. **Notion アカウント**
       - 論文データベース保存用
    
    ### ⚠️ 重要な注意事項
    
    - すべて無料プランから始められます
    - Google Cloud は課金設定が必要ですが、無料枠内で十分利用可能です
    - API キーは安全に管理されます（ローカルファイルのみ）
    """)
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 設定を開始する", type="primary", use_container_width=True):
            st.session_state.setup_step = 2
            st.rerun()


def _render_step2_gemini():
    """ステップ2: Gemini API設定"""
    st.markdown("## 🤖 Gemini API 設定")
    
    st.markdown("""
    ### 📋 Gemini API キーの取得方法
    
    1. [Google AI Studio](https://aistudio.google.com/) にアクセス
    2. 「Get API key」をクリック
    3. 「Create API key in new project」を選択
    4. 生成されたAPIキーをコピー
    """)
    
    st.info("💡 無料プランでも十分な機能を利用できます")
    
    # APIキー入力
    gemini_api_key = st.text_input(
        "Gemini API Key",
        type="password",
        placeholder="AIzaSy...",
        help="Google AI Studioで取得したAPIキーを入力してください",
        value=st.session_state.setup_config.get('GEMINI_API_KEY', '')
    )
    
    # APIキーテスト機能
    if gemini_api_key:
        if st.button("🧪 APIキーをテスト"):
            if _test_gemini_api(gemini_api_key):
                st.success("✅ APIキーが正常に動作しています！")
                st.session_state.setup_config['GEMINI_API_KEY'] = gemini_api_key
            else:
                st.error("❌ APIキーが無効です。確認してください。")
    
    # ナビゲーション
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("← 戻る"):
            st.session_state.setup_step = 1
            st.rerun()
    
    with col3:
        if gemini_api_key and st.button("次へ →", type="primary"):
            st.session_state.setup_config['GEMINI_API_KEY'] = gemini_api_key
            st.session_state.setup_step = 3
            st.rerun()


def _render_step3_google_cloud():
    """ステップ3: Google Cloud設定"""
    st.markdown("## ☁️ Google Cloud 設定")
    
    st.markdown("""
    ### 📋 Google Cloud 設定手順
    
    1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
    2. 新しいプロジェクトを作成（例: `paper-manager`）
    3. **Vision API** を有効化
       - 左メニュー「APIとサービス」→「ライブラリ」
       - 「Cloud Vision API」を検索して有効化
    4. **サービスアカウント** を作成
       - 「APIとサービス」→「認証情報」
       - 「認証情報を作成」→「サービスアカウント」
    5. **JSONキー** をダウンロード
       - 作成したサービスアカウントの「キー」タブ
       - 「新しいキーを作成」→「JSON」
    """)
    
    st.warning("⚠️ 課金設定が必要ですが、月額無料枠（1,000回のVision API呼び出し）内で利用可能です")
    
    # ファイルアップロード
    uploaded_file = st.file_uploader(
        "Google Cloud サービスアカウントキー（JSON）",
        type=['json'],
        help="Google Cloud ConsoleでダウンロードしたJSONファイルをアップロードしてください"
    )
    
    credentials_path = None
    if uploaded_file is not None:
        # ファイルを保存
        credentials_dir = project_root / "credentials"
        credentials_dir.mkdir(exist_ok=True)
        credentials_path = credentials_dir / "google_credentials.json"
        
        with open(credentials_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"✅ 認証ファイルを保存しました: {credentials_path}")
        st.session_state.setup_config['GOOGLE_APPLICATION_CREDENTIALS'] = str(credentials_path)
    
    # ナビゲーション
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("← 戻る"):
            st.session_state.setup_step = 2
            st.rerun()
    
    with col3:
        if credentials_path and st.button("次へ →", type="primary"):
            st.session_state.setup_step = 4
            st.rerun()


def _render_step4_notion():
    """ステップ4: Notion設定"""
    st.markdown("## 📚 Notion 設定")
    
    st.markdown("""
    ### 📋 Notion 設定手順
    
    #### 1. Integration の作成
    1. [Notion Developers](https://www.notion.so/my-integrations) にアクセス
    2. 「New integration」をクリック
    3. 名前を入力（例: `Paper Manager`）
    4. 「Internal Integration Token」をコピー
    
    #### 2. データベースの作成
    1. Notionで新しいページを作成
    2. `/database` と入力してデータベースを作成
    3. 以下のプロパティを追加：
    """)
    
    # データベース設計表
    st.markdown("""
    | プロパティ名 | タイプ | 説明 |
    |------------|--------|------|
    | Title | タイトル | 論文タイトル |
    | Authors | マルチセレクト | 著者リスト |
    | Journal | セレクト | 雑誌名 |
    | Year | 数値 | 出版年 |
    | DOI | URL | DOI |
    | PMID | 数値 | PubMed ID |
    | PubMed | URL | PubMedリンク |
    | Summary | テキスト | 日本語要約 |
    | pdf | ファイル | PDFファイル |
    """)
    
    # Notion Token入力
    notion_token = st.text_input(
        "Notion Integration Token",
        type="password",
        placeholder="secret_...",
        help="Notion Developersで取得したIntegration Tokenを入力してください",
        value=st.session_state.setup_config.get('NOTION_TOKEN', '')
    )
    
    # Database ID入力
    notion_database_id = st.text_input(
        "Notion Database ID",
        placeholder="3567584d934242a2b85acd3751b3997b",
        help="NotionデータベースURLの32文字のIDを入力してください",
        value=st.session_state.setup_config.get('NOTION_DATABASE_ID', '')
    )
    
    if notion_database_id:
        st.info(f"💡 データベース設定で作成したIntegrationを接続することを忘れずに！")
    
    # ナビゲーション
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("← 戻る"):
            st.session_state.setup_step = 3
            st.rerun()
    
    with col3:
        if notion_token and notion_database_id and st.button("次へ →", type="primary"):
            st.session_state.setup_config['NOTION_TOKEN'] = notion_token
            st.session_state.setup_config['NOTION_DATABASE_ID'] = notion_database_id
            st.session_state.setup_step = 5
            st.rerun()


def _render_step5_optional():
    """ステップ5: オプション設定"""
    st.markdown("## ⚙️ オプション設定")
    
    st.markdown("""
    以下の設定は後から変更可能です。今は空欄のままでも構いません。
    """)
    
    # PubMed設定
    st.markdown("### 🔬 PubMed設定")
    pubmed_email = st.text_input(
        "PubMedアクセス用メールアドレス（推奨）",
        placeholder="your-email@example.com",
        help="PubMed APIのアクセス制限を緩和するため",
        value=st.session_state.setup_config.get('PUBMED_EMAIL', '')
    )
    
    # Slack設定
    st.markdown("### 💬 Slack通知設定（オプション）")
    
    with st.expander("Slack通知を設定する場合はクリック"):
        slack_bot_token = st.text_input(
            "Slack Bot Token",
            type="password",
            placeholder="xoxb-...",
            value=st.session_state.setup_config.get('SLACK_BOT_TOKEN', '')
        )
        
        slack_user_id = st.text_input(
            "Slack User ID（通知先）",
            placeholder="U01ABCDEFGH",
            value=st.session_state.setup_config.get('SLACK_USER_ID_TO_DM', '')
        )
    
    # 設定を保存
    if pubmed_email:
        st.session_state.setup_config['PUBMED_EMAIL'] = pubmed_email
    if slack_bot_token:
        st.session_state.setup_config['SLACK_BOT_TOKEN'] = slack_bot_token
    if slack_user_id:
        st.session_state.setup_config['SLACK_USER_ID_TO_DM'] = slack_user_id
    
    # ナビゲーション
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("← 戻る"):
            st.session_state.setup_step = 4
            st.rerun()
    
    with col3:
        if st.button("設定を完了する →", type="primary"):
            st.session_state.setup_step = 6
            st.rerun()


def _render_step6_completion():
    """ステップ6: 設定完了"""
    st.markdown("## 🎉 設定完了")
    
    # 設定内容を確認
    st.markdown("### 📋 設定内容確認")
    
    config = st.session_state.setup_config
    
    st.markdown("**必須設定:**")
    st.write(f"✅ Gemini API Key: {'設定済み' if config.get('GEMINI_API_KEY') else '未設定'}")
    st.write(f"✅ Google Cloud: {'設定済み' if config.get('GOOGLE_APPLICATION_CREDENTIALS') else '未設定'}")
    st.write(f"✅ Notion Token: {'設定済み' if config.get('NOTION_TOKEN') else '未設定'}")
    st.write(f"✅ Notion Database ID: {'設定済み' if config.get('NOTION_DATABASE_ID') else '未設定'}")
    
    st.markdown("**オプション設定:**")
    st.write(f"📧 PubMed Email: {'設定済み' if config.get('PUBMED_EMAIL') else '未設定'}")
    st.write(f"💬 Slack通知: {'設定済み' if config.get('SLACK_BOT_TOKEN') else '未設定'}")
    
    # 設定保存ボタン
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 設定を保存してシステムを開始", type="primary", use_container_width=True):
            # .envファイルに保存
            if save_env_config(st.session_state.setup_config):
                st.success("✅ 設定が正常に保存されました！")
                
                # セッション状態をクリア
                st.session_state.setup_complete = True
                if 'setup_step' in st.session_state:
                    del st.session_state.setup_step
                if 'setup_config' in st.session_state:
                    del st.session_state.setup_config
                
                st.balloons()
                st.info("🔄 ページが自動的に再読み込みされます...")
                
                # 少し待ってからリロード
                import time
                time.sleep(2)
                st.rerun()
                
            else:
                st.error("❌ 設定の保存に失敗しました")


def _test_gemini_api(api_key: str) -> bool:
    """Gemini APIキーをテスト"""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content("Hello")
        
        return True
    except Exception:
        return False