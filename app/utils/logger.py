"""
ログ設定ユーティリティ
"""

import logging
import logging.handlers
import os
from pathlib import Path
import colorlog

from ..config import config


def setup_logging():
    """ログ設定をセットアップ"""
    
    # ログディレクトリを作成
    log_file = Path(config.logging.file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # ルートロガーの設定
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.logging.level.upper()))
    
    # 既存のハンドラーをクリア
    root_logger.handlers.clear()
    
    # フォーマッターの作成
    formatter = logging.Formatter(config.logging.format)
    
    # コンソールハンドラー（カラー対応）
    console_handler = colorlog.StreamHandler()
    console_handler.setLevel(getattr(logging, config.logging.level.upper()))
    
    color_formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    console_handler.setFormatter(color_formatter)
    root_logger.addHandler(console_handler)
    
    # ファイルハンドラー（ローテーション対応）
    file_handler = logging.handlers.RotatingFileHandler(
        config.logging.file,
        maxBytes=config.logging.max_bytes,
        backupCount=config.logging.backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, config.logging.level.upper()))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # 外部ライブラリのログレベルを調整
    logging.getLogger('google').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """名前付きロガーを取得"""
    return logging.getLogger(name)


# アプリケーション開始時にログ設定を初期化
setup_logging()