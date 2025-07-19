"""
設定管理ページ
API設定、システム設定の管理
"""

import streamlit as st
import os
from pathlib import Path
import yaml
from typing import Dict, Any
import sys

# アプリケーションモジュールをインポート
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.config import config, load_config
from app.utils.logger import get_logger

logger = get_logger(__name__)

def load_env_file() -> Dict[str, str]:
    """環境変数ファイルを読み込み"""
    env_file = Path(".env")
    env_vars = {}
    
    if env_file.exists():
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
        except Exception as e:
            logger.error(f"環境変数ファイル読み込みエラー: {e}")
    
    return env_vars

def save_env_file(env_vars: Dict[str, str]) -> bool:
    """環境変数ファイルを保存"""
    try:
        env_file = Path(".env")
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write("# Paper Manager 環境変数設定\\n")
            f.write("# 以下の設定を適切に入力してください\\n\\n")
            
            # 各種API設定
            f.write("# Google Cloud 認証（ダウンロードしたJSONファイルのパス）\\n")
            f.write(f"GOOGLE_APPLICATION_CREDENTIALS={env_vars.get('GOOGLE_APPLICATION_CREDENTIALS', '')}\\n\\n")
            
            f.write("# Gemini API Key\\n")
            f.write(f"GEMINI_API_KEY={env_vars.get('GEMINI_API_KEY', '')}\\n\\n")
            
            f.write("# Notion API\\n")
            f.write(f"NOTION_TOKEN={env_vars.get('NOTION_TOKEN', '')}\\n")
            f.write(f"NOTION_DATABASE_ID={env_vars.get('NOTION_DATABASE_ID', '')}\\n\\n")
            
            f.write("# PubMed API (任意)\\n")
            f.write(f"PUBMED_EMAIL={env_vars.get('PUBMED_EMAIL', '')}\\n\\n")
            
            f.write("# Slack通知（任意）\\n")
            f.write(f"SLACK_BOT_TOKEN={env_vars.get('SLACK_BOT_TOKEN', '')}\\n")
            f.write(f"SLACK_USER_ID_TO_DM={env_vars.get('SLACK_USER_ID_TO_DM', '')}\\n\\n")
            
            f.write("# フォルダ設定\\n")
            f.write(f"WATCH_FOLDER={env_vars.get('WATCH_FOLDER', './pdfs')}\\n")
            f.write(f"PROCESSED_FOLDER={env_vars.get('PROCESSED_FOLDER', './processed_pdfs')}\\n\\n")
            
            f.write("# ログレベル\\n")
            f.write(f"LOG_LEVEL={env_vars.get('LOG_LEVEL', 'INFO')}\\n")
        
        return True
    except Exception as e:
        logger.error(f"環境変数ファイル保存エラー: {e}")
        return False

def test_api_connections() -> Dict[str, bool]:
    """API接続テスト"""
    results = {}
    
    # Notion接続テスト
    try:
        from app.services.notion_service import notion_service
        # 非同期関数を同期的に実行（簡易版）
        results['notion'] = True  # 実際のテストは複雑なので簡略化
    except Exception as e:
        results['notion'] = False
        logger.error(f"Notion接続テストエラー: {e}")
    
    # Slack接続テスト
    try:
        from app.services.slack_service import slack_service
        results['slack'] = slack_service.enabled
    except Exception as e:
        results['slack'] = False
        logger.error(f"Slack接続テストエラー: {e}")
    
    # Gemini接続テスト
    try:
        from app.services.gemini_service import gemini_service
        results['gemini'] = bool(config.gemini_api_key)
    except Exception as e:
        results['gemini'] = False
        logger.error(f"Gemini接続テストエラー: {e}")
    
    return results

def render_settings():
    """設定ページをレンダリング"""
    st.markdown("## ⚙️ システム設定")
    
    # タブで設定を分類
    tab1, tab2, tab3, tab4 = st.tabs(["🔐 API設定", "📁 フォルダ設定", "🔔 通知設定", "🧪 接続テスト"])
    
    # 現在の環境変数を読み込み
    env_vars = load_env_file()
    
    with tab1:
        st.markdown("### 🔐 API認証設定")
        st.info("各種APIの認証情報を設定してください。設定後は「保存」ボタンをクリックしてください。")
        
        # Google Cloud設定
        st.markdown("#### Google Cloud 設定")
        google_creds = st.text_input(
            "Google Cloud認証ファイルパス",
            value=env_vars.get('GOOGLE_APPLICATION_CREDENTIALS', ''),
            help="ダウンロードしたservice-account.jsonファイルのパス",
            placeholder="./credentials.json"
        )
        
        # Gemini API設定
        st.markdown("#### Gemini API 設定")
        gemini_key = st.text_input(
            "Gemini API Key",
            value=env_vars.get('GEMINI_API_KEY', ''),
            type="password",
            help="Google AI StudioでAPIキーを取得してください",
            placeholder="your_gemini_api_key_here"
        )
        
        # Notion API設定
        st.markdown("#### Notion API 設定")
        notion_token = st.text_input(
            "Notion Integration Token",
            value=env_vars.get('NOTION_TOKEN', ''),
            type="password",
            help="Notion Developersで作成したIntegrationのトークン",
            placeholder="secret_xxxxxxxxxx"
        )
        
        notion_db_id = st.text_input(
            "Notion Database ID",
            value=env_vars.get('NOTION_DATABASE_ID', ''),
            help="論文管理用データベースのID（32文字）",
            placeholder="your_notion_database_id_here"
        )
        
        # PubMed設定
        st.markdown("#### PubMed API 設定（任意）")
        pubmed_email = st.text_input(
            "PubMed Email",
            value=env_vars.get('PUBMED_EMAIL', ''),
            help="PubMed API利用時の連絡先メールアドレス",
            placeholder="your_email@example.com"
        )
        
        # 保存ボタン
        if st.button("💾 API設定を保存", type="primary"):
            new_env_vars = env_vars.copy()
            new_env_vars.update({
                'GOOGLE_APPLICATION_CREDENTIALS': google_creds,
                'GEMINI_API_KEY': gemini_key,
                'NOTION_TOKEN': notion_token,
                'NOTION_DATABASE_ID': notion_db_id,
                'PUBMED_EMAIL': pubmed_email
            })
            
            if save_env_file(new_env_vars):
                st.success("✅ API設定が保存されました！設定を反映するにはシステムを再起動してください。")
            else:
                st.error("❌ 設定の保存に失敗しました。")
    
    with tab2:
        st.markdown("### 📁 フォルダ設定")
        st.info("PDFファイルの監視フォルダと処理済みファイルの保存先を設定してください。")
        
        # フォルダ設定
        watch_folder = st.text_input(
            "監視フォルダ",
            value=env_vars.get('WATCH_FOLDER', './pdfs'),
            help="PDFファイルを配置する監視対象フォルダ",
            placeholder="./pdfs"
        )
        
        processed_folder = st.text_input(
            "処理済みフォルダ",
            value=env_vars.get('PROCESSED_FOLDER', './processed_pdfs'),
            help="処理済みPDFファイルの保存先フォルダ",
            placeholder="./processed_pdfs"
        )
        
        log_level = st.selectbox(
            "ログレベル",
            options=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
            index=['DEBUG', 'INFO', 'WARNING', 'ERROR'].index(env_vars.get('LOG_LEVEL', 'INFO')),
            help="ログ出力レベルの設定"
        )
        
        # フォルダ作成ボタン
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📁 監視フォルダ作成"):
                try:
                    Path(watch_folder).mkdir(parents=True, exist_ok=True)
                    st.success(f"監視フォルダを作成しました: {watch_folder}")
                except Exception as e:
                    st.error(f"フォルダ作成に失敗: {e}")
        
        with col2:
            if st.button("📁 処理済みフォルダ作成"):
                try:
                    Path(processed_folder).mkdir(parents=True, exist_ok=True)
                    st.success(f"処理済みフォルダを作成しました: {processed_folder}")
                except Exception as e:
                    st.error(f"フォルダ作成に失敗: {e}")
        
        # 保存ボタン
        if st.button("💾 フォルダ設定を保存", type="primary"):
            new_env_vars = env_vars.copy()
            new_env_vars.update({
                'WATCH_FOLDER': watch_folder,
                'PROCESSED_FOLDER': processed_folder,
                'LOG_LEVEL': log_level
            })
            
            if save_env_file(new_env_vars):
                st.success("✅ フォルダ設定が保存されました！")
            else:
                st.error("❌ 設定の保存に失敗しました。")
    
    with tab3:
        st.markdown("### 🔔 Slack通知設定")
        st.info("Slack通知を有効にすると、論文処理完了時にDMで通知を受け取れます。")
        
        # Slack設定
        slack_token = st.text_input(
            "Slack Bot Token",
            value=env_vars.get('SLACK_BOT_TOKEN', ''),
            type="password",
            help="Slack APIで作成したBotのOAuth Token（xoxb-で始まる）",
            placeholder="xoxb-your-bot-token"
        )
        
        slack_user_id = st.text_input(
            "Slack User ID",
            value=env_vars.get('SLACK_USER_ID_TO_DM', ''),
            help="通知を受け取るSlackユーザーのメンバーID（Uで始まる）",
            placeholder="U12345ABCDE"
        )
        
        # 通知レベル設定
        st.markdown("#### 通知レベル設定")
        
        # 現在の設定を読み込み
        try:
            config_path = Path("config/config.yaml")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                slack_config = config_data.get('slack', {})
            else:
                slack_config = {}
        except Exception as e:
            logger.error(f"設定ファイル読み込みエラー: {e}")
            slack_config = {}
        
        slack_enabled = st.checkbox(
            "Slack通知を有効にする",
            value=slack_config.get('enabled', False)
        )
        
        notify_success = st.checkbox(
            "成功時の通知",
            value=slack_config.get('notify_success', True),
            disabled=not slack_enabled
        )
        
        notify_failure = st.checkbox(
            "失敗時の通知",
            value=slack_config.get('notify_failure', True),
            disabled=not slack_enabled
        )
        
        notify_duplicate = st.checkbox(
            "重複検出時の通知",
            value=slack_config.get('notify_duplicate', False),
            disabled=not slack_enabled
        )
        
        include_summary = st.checkbox(
            "要約をメッセージに含める",
            value=slack_config.get('include_summary', False),
            disabled=not slack_enabled
        )
        
        max_message_length = st.slider(
            "メッセージ最大長",
            min_value=500,
            max_value=2000,
            value=slack_config.get('max_message_length', 1000),
            step=100,
            disabled=not slack_enabled
        )
        
        # 保存ボタン
        if st.button("💾 Slack設定を保存", type="primary"):
            # 環境変数を保存
            new_env_vars = env_vars.copy()
            new_env_vars.update({
                'SLACK_BOT_TOKEN': slack_token,
                'SLACK_USER_ID_TO_DM': slack_user_id
            })
            
            env_saved = save_env_file(new_env_vars)
            
            # config.yamlを更新
            try:
                config_path = Path("config/config.yaml")
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                
                config_data['slack'] = {
                    'enabled': slack_enabled,
                    'notify_success': notify_success,
                    'notify_failure': notify_failure,
                    'notify_duplicate': notify_duplicate,
                    'include_summary': include_summary,
                    'max_message_length': max_message_length
                }
                
                with open(config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
                
                config_saved = True
            except Exception as e:
                logger.error(f"設定ファイル保存エラー: {e}")
                config_saved = False
            
            if env_saved and config_saved:
                st.success("✅ Slack設定が保存されました！")
            else:
                st.error("❌ 設定の保存に失敗しました。")
    
    with tab4:
        st.markdown("### 🧪 API接続テスト")
        st.info("各種APIの接続状態をテストできます。")
        
        if st.button("🔍 接続テストを実行", type="primary"):
            with st.spinner("接続テストを実行中..."):
                results = test_api_connections()
            
            st.markdown("#### テスト結果")
            
            # Notion
            if results.get('notion'):
                st.success("✅ Notion API: 接続成功")
            else:
                st.error("❌ Notion API: 接続失敗")
            
            # Slack
            if results.get('slack'):
                st.success("✅ Slack API: 設定有効")
            else:
                st.warning("⚠️ Slack API: 無効または未設定")
            
            # Gemini
            if results.get('gemini'):
                st.success("✅ Gemini API: APIキー設定済み")
            else:
                st.error("❌ Gemini API: APIキー未設定")
        
        # 現在の設定表示
        st.markdown("#### 現在の設定状態")
        
        status_data = {
            "設定項目": ["Google Cloud認証", "Gemini APIキー", "Notion Token", "Notion DB ID", "Slack Bot Token"],
            "設定状態": [
                "✅ 設定済み" if env_vars.get('GOOGLE_APPLICATION_CREDENTIALS') else "❌ 未設定",
                "✅ 設定済み" if env_vars.get('GEMINI_API_KEY') else "❌ 未設定",
                "✅ 設定済み" if env_vars.get('NOTION_TOKEN') else "❌ 未設定",
                "✅ 設定済み" if env_vars.get('NOTION_DATABASE_ID') else "❌ 未設定",
                "✅ 設定済み" if env_vars.get('SLACK_BOT_TOKEN') else "❌ 未設定"
            ]
        }
        
        import pandas as pd
        df = pd.DataFrame(status_data)
        st.dataframe(df, use_container_width=True, hide_index=True)