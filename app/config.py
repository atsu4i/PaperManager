"""
設定管理モジュール
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class FileProcessingConfig(BaseModel):
    max_pdf_size: int = 50
    max_concurrent_files: int = 3
    processing_interval: int = 2
    supported_extensions: List[str] = ['.pdf']


class GeminiConfig(BaseModel):
    model: str = "gemini-2.0-flash-exp"
    temperature: float = 0.1
    max_tokens: int = 8192
    max_retries: int = 3
    retry_delay: int = 2


class VisionConfig(BaseModel):
    language_hints: List[str] = ["ja", "en"]
    enable_text_detection_confidence: bool = True
    max_retries: int = 3
    retry_delay: int = 1


class PubMedConfig(BaseModel):
    timeout: int = 30
    max_retries: int = 3
    max_results: int = 10
    request_delay: float = 0.5
    ssl_verify: bool = True  # SSL証明書検証（企業ネットワークでは無効化が必要な場合あり）


class NotionConfig(BaseModel):
    max_retries: int = 3
    retry_delay: int = 2
    max_page_size: int = 100
    pdf_property_name: str = "PDF"
    enable_pdf_upload: bool = True
    max_pdf_size_mb: int = 50


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str = "logs/paper_manager.log"
    max_bytes: int = 10485760
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class SummaryConfig(BaseModel):
    target_length: int = 2500
    required_sections: List[str] = Field(default_factory=lambda: [
        "研究背景", "目的", "方法", "結果", "結論", "意義", "限界"
    ])


class SlackConfig(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    user_id_to_dm: str = ""
    notify_success: bool = True
    notify_failure: bool = True
    notify_duplicate: bool = False
    include_summary: bool = False
    max_message_length: int = 1000


class ObsidianConfig(BaseModel):
    enabled: bool = False
    vault_path: str = "./obsidian_vault"
    organize_by_year: bool = True
    include_pdf_attachments: bool = False  # デフォルト無効に変更
    tag_keywords: bool = True
    filename_format: str = "{first_author}_{year}_{title_short}"
    max_filename_length: int = 100
    link_to_notion: bool = True
    create_folders: bool = True


class Config(BaseModel):
    file_processing: FileProcessingConfig = Field(default_factory=FileProcessingConfig)
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    pubmed: PubMedConfig = Field(default_factory=PubMedConfig)
    notion: NotionConfig = Field(default_factory=NotionConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    summary: SummaryConfig = Field(default_factory=SummaryConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    obsidian: ObsidianConfig = Field(default_factory=ObsidianConfig)
    
    # 環境変数から取得する設定
    google_credentials_path: Optional[str] = None
    gemini_api_key: Optional[str] = None
    notion_token: Optional[str] = None
    notion_database_id: str = "your_notion_database_id_here"
    pubmed_email: Optional[str] = None
    slack_bot_token: Optional[str] = None
    slack_user_id_to_dm: Optional[str] = None
    watch_folder: str = "./pdfs"
    processed_folder: str = "./processed_pdfs"
    processed_files_db: str = "./processed_files.json"
    
    # ネットワーク設定
    ssl_verify_pubmed: bool = True  # PubMed SSL証明書検証
    
    def is_setup_complete(self) -> bool:
        """必須設定が完了しているかチェック"""
        required_fields = [
            self.gemini_api_key,
            self.notion_token,
            self.google_credentials_path
        ]
        
        return all(field is not None and field != "" and field != "your_notion_database_id_here" 
                  for field in required_fields[:2]) and \
               self.google_credentials_path is not None and \
               self.notion_database_id != "your_notion_database_id_here"
    
    def get_missing_configs(self) -> List[str]:
        """不足している設定項目のリストを取得"""
        missing = []
        
        if not self.gemini_api_key:
            missing.append("Gemini API Key")
        if not self.notion_token:
            missing.append("Notion Token")
        if not self.google_credentials_path:
            missing.append("Google Cloud認証ファイル")
        if self.notion_database_id == "your_notion_database_id_here":
            missing.append("Notion Database ID")
        
        return missing


def save_env_config(config_dict: Dict[str, str]) -> bool:
    """環境変数を.envファイルに保存"""
    try:
        env_path = Path(__file__).parent.parent / ".env"
        
        # 既存の.envファイルを読み込み
        existing_vars = {}
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        existing_vars[key] = value
        
        # 新しい値で更新
        existing_vars.update(config_dict)
        
        # .envファイルに書き込み
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write("# Paper Manager 設定ファイル\n")
            f.write("# 自動生成されたファイルです\n\n")
            
            # 必須設定
            f.write("# === 必須設定 ===\n")
            for key in ["GEMINI_API_KEY", "NOTION_TOKEN", "GOOGLE_APPLICATION_CREDENTIALS", "NOTION_DATABASE_ID"]:
                if key in existing_vars:
                    f.write(f"{key}={existing_vars[key]}\n")
                    
            # オプション設定
            f.write("\n# === オプション設定 ===\n")
            for key in ["PUBMED_EMAIL", "SLACK_BOT_TOKEN", "SLACK_USER_ID_TO_DM"]:
                if key in existing_vars:
                    f.write(f"{key}={existing_vars[key]}\n")
            
            # フォルダ設定
            f.write("\n# === フォルダ設定 ===\n")
            for key in ["WATCH_FOLDER", "PROCESSED_FOLDER", "PROCESSED_FILES_DB"]:
                if key in existing_vars:
                    f.write(f"{key}={existing_vars[key]}\n")
        
        return True
        
    except Exception as e:
        print(f"設定保存エラー: {e}")
        return False


def load_config() -> Config:
    """設定ファイルと環境変数から設定を読み込む"""
    
    # .envファイルを読み込む（存在しない場合はスキップ）
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    
    # YAMLファイルから設定を読み込む
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    config_data = {}
    
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f) or {}
    
    # 環境変数から設定を取得（デフォルト値を設定）
    env_config = {
        "google_credentials_path": os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        "gemini_api_key": os.getenv("GEMINI_API_KEY"),
        "notion_token": os.getenv("NOTION_TOKEN"),
        "notion_database_id": os.getenv("NOTION_DATABASE_ID", "your_notion_database_id_here"),
        "pubmed_email": os.getenv("PUBMED_EMAIL"),
        "slack_bot_token": os.getenv("SLACK_BOT_TOKEN"),
        "slack_user_id_to_dm": os.getenv("SLACK_USER_ID_TO_DM"),
        "watch_folder": os.getenv("WATCH_FOLDER", "./pdfs"),
        "processed_folder": os.getenv("PROCESSED_FOLDER", "./processed_pdfs"),
        "processed_files_db": os.getenv("PROCESSED_FILES_DB", "./processed_files.json"),
        "ssl_verify_pubmed": os.getenv("SSL_VERIFY_PUBMED", "true").lower() == "true",
        
        # Obsidian設定
        "obsidian": {
            "enabled": os.getenv("OBSIDIAN_ENABLED", "false").lower() == "true",
            "vault_path": os.getenv("OBSIDIAN_VAULT_PATH", "./obsidian_vault"),
            "organize_by_year": os.getenv("OBSIDIAN_ORGANIZE_BY_YEAR", "true").lower() == "true",
            "include_pdf_attachments": os.getenv("OBSIDIAN_INCLUDE_PDF", "true").lower() == "true",
            "tag_keywords": os.getenv("OBSIDIAN_TAG_KEYWORDS", "true").lower() == "true",
            "link_to_notion": os.getenv("OBSIDIAN_LINK_TO_NOTION", "true").lower() == "true"
        }
    }
    
    # 設定をマージ
    merged_config = {**config_data, **env_config}
    
    return Config(**merged_config)


# グローバル設定インスタンス
config = load_config()