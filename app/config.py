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


class NotionConfig(BaseModel):
    max_retries: int = 3
    retry_delay: int = 2
    max_page_size: int = 100


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


class Config(BaseModel):
    file_processing: FileProcessingConfig = Field(default_factory=FileProcessingConfig)
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    pubmed: PubMedConfig = Field(default_factory=PubMedConfig)
    notion: NotionConfig = Field(default_factory=NotionConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    summary: SummaryConfig = Field(default_factory=SummaryConfig)
    
    # 環境変数から取得する設定
    google_credentials_path: Optional[str] = None
    gemini_api_key: Optional[str] = None
    notion_token: Optional[str] = None
    notion_database_id: str = "3567584d934242a2b85acd3751b3997b"
    pubmed_email: Optional[str] = None
    watch_folder: str = "./pdfs"
    processed_folder: str = "./processed_pdfs"
    processed_files_db: str = "./processed_files.json"


def load_config() -> Config:
    """設定ファイルと環境変数から設定を読み込む"""
    
    # .envファイルを読み込む
    load_dotenv()
    
    # YAMLファイルから設定を読み込む
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    config_data = {}
    
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f) or {}
    
    # 環境変数から設定を取得
    env_config = {
        "google_credentials_path": os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        "gemini_api_key": os.getenv("GEMINI_API_KEY"),
        "notion_token": os.getenv("NOTION_TOKEN"),
        "notion_database_id": os.getenv("NOTION_DATABASE_ID", "3567584d934242a2b85acd3751b3997b"),
        "pubmed_email": os.getenv("PUBMED_EMAIL"),
        "watch_folder": os.getenv("WATCH_FOLDER", "./pdfs"),
        "processed_folder": os.getenv("PROCESSED_FOLDER", "./processed_pdfs"),
        "processed_files_db": os.getenv("PROCESSED_FILES_DB", "./processed_files.json")
    }
    
    # 設定をマージ
    merged_config = {**config_data, **env_config}
    
    return Config(**merged_config)


# グローバル設定インスタンス
config = load_config()