"""
ファイル管理ユーティリティ
処理済みPDFファイルの移動や管理を行う
"""

import shutil
import time
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

from ..config import config
from .logger import get_logger

logger = get_logger(__name__)


class FileManager:
    """ファイル管理クラス"""
    
    def __init__(self):
        self.processed_folder = Path(config.processed_folder)
        self.processed_folder.mkdir(parents=True, exist_ok=True)
    
    def move_processed_file(self, source_path: str, success: bool, notion_page_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        処理済みファイルを適切なフォルダに移動
        
        Args:
            source_path: 元ファイルパス
            success: 処理が成功したかどうか
            notion_page_id: Notion ページID（成功時）
        
        Returns:
            Tuple[移動成功フラグ, 移動先パス]
        """
        try:
            source = Path(source_path)
            
            if not source.exists():
                logger.warning(f"移動対象ファイルが存在しません: {source_path}")
                return False, ""
            
            # 移動先のサブフォルダを決定
            if success:
                subfolder = "success"
                status_prefix = "✓"
            else:
                subfolder = "failed"
                status_prefix = "✗"
            
            # 移動先ディレクトリを作成
            dest_dir = self.processed_folder / subfolder
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            # 日付別のサブフォルダを作成（オプション）
            date_folder = dest_dir / datetime.now().strftime("%Y-%m")
            date_folder.mkdir(parents=True, exist_ok=True)
            
            # ファイル名に処理情報を追加
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            original_name = source.stem
            extension = source.suffix
            
            # 新しいファイル名を生成
            if success and notion_page_id:
                new_name = f"{status_prefix}_{timestamp}_{original_name}_{notion_page_id[:8]}{extension}"
            else:
                new_name = f"{status_prefix}_{timestamp}_{original_name}{extension}"
            
            dest_path = date_folder / new_name
            
            # ファイル名の重複を避ける
            counter = 1
            while dest_path.exists():
                if success and notion_page_id:
                    new_name = f"{status_prefix}_{timestamp}_{original_name}_{notion_page_id[:8]}_{counter}{extension}"
                else:
                    new_name = f"{status_prefix}_{timestamp}_{original_name}_{counter}{extension}"
                dest_path = date_folder / new_name
                counter += 1
            
            # ファイルを移動
            shutil.move(str(source), str(dest_path))
            
            logger.info(f"ファイル移動完了: {source.name} → {dest_path.relative_to(self.processed_folder)}")
            
            return True, str(dest_path)
            
        except Exception as e:
            logger.error(f"ファイル移動エラー: {e}")
            return False, ""
    
    def create_backup(self, source_path: str) -> Optional[str]:
        """
        処理前にファイルのバックアップを作成
        
        Args:
            source_path: バックアップ対象ファイル
        
        Returns:
            バックアップファイルのパス（失敗時はNone）
        """
        try:
            source = Path(source_path)
            
            if not source.exists():
                return None
            
            # バックアップディレクトリを作成
            backup_dir = self.processed_folder / "backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # バックアップファイル名を生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}_{source.name}"
            backup_path = backup_dir / backup_name
            
            # ファイルをコピー
            shutil.copy2(str(source), str(backup_path))
            
            logger.debug(f"バックアップ作成: {backup_path}")
            
            return str(backup_path)
            
        except Exception as e:
            logger.warning(f"バックアップ作成エラー: {e}")
            return None
    
    def cleanup_old_files(self, days: int = 30):
        """
        古いファイルのクリーンアップ
        
        Args:
            days: 保持日数
        """
        try:
            cutoff_time = time.time() - (days * 24 * 60 * 60)
            deleted_count = 0
            
            # バックアップフォルダのクリーンアップ
            backup_dir = self.processed_folder / "backup"
            if backup_dir.exists():
                for file_path in backup_dir.rglob("*"):
                    if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                        try:
                            file_path.unlink()
                            deleted_count += 1
                            logger.debug(f"古いバックアップファイルを削除: {file_path.name}")
                        except Exception as e:
                            logger.warning(f"ファイル削除エラー: {e}")
            
            if deleted_count > 0:
                logger.info(f"クリーンアップ完了: {deleted_count}個のファイルを削除")
            
        except Exception as e:
            logger.error(f"クリーンアップエラー: {e}")
    
    def get_storage_info(self) -> dict:
        """
        ストレージ使用量情報を取得
        
        Returns:
            ストレージ情報の辞書
        """
        try:
            info = {
                "processed_folder": str(self.processed_folder),
                "total_files": 0,
                "success_files": 0,
                "failed_files": 0,
                "backup_files": 0,
                "total_size_mb": 0
            }
            
            # 成功ファイル数をカウント
            success_dir = self.processed_folder / "success"
            if success_dir.exists():
                info["success_files"] = len(list(success_dir.rglob("*.pdf")))
            
            # 失敗ファイル数をカウント
            failed_dir = self.processed_folder / "failed"
            if failed_dir.exists():
                info["failed_files"] = len(list(failed_dir.rglob("*.pdf")))
            
            # バックアップファイル数をカウント
            backup_dir = self.processed_folder / "backup"
            if backup_dir.exists():
                info["backup_files"] = len(list(backup_dir.rglob("*.pdf")))
            
            # 総ファイル数
            info["total_files"] = info["success_files"] + info["failed_files"] + info["backup_files"]
            
            # 総使用量を計算
            total_size = 0
            for file_path in self.processed_folder.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            
            info["total_size_mb"] = round(total_size / (1024 * 1024), 2)
            
            return info
            
        except Exception as e:
            logger.error(f"ストレージ情報取得エラー: {e}")
            return {}
    
    def restore_file(self, processed_file_path: str, target_folder: Optional[str] = None) -> bool:
        """
        処理済みファイルを元のフォルダまたは指定フォルダに復元
        
        Args:
            processed_file_path: 処理済みファイルのパス
            target_folder: 復元先フォルダ（Noneの場合は監視フォルダ）
        
        Returns:
            復元成功フラグ
        """
        try:
            source = Path(processed_file_path)
            
            if not source.exists():
                logger.error(f"復元対象ファイルが存在しません: {processed_file_path}")
                return False
            
            # 復元先フォルダを決定
            if target_folder:
                dest_dir = Path(target_folder)
            else:
                dest_dir = Path(config.watch_folder)
            
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            # 元のファイル名を推定（プレフィックスやタイムスタンプを除去）
            original_name = source.name
            
            # プレフィックスパターンを除去
            import re
            # "✓_20241217_123456_filename_12345678.pdf" -> "filename.pdf"
            cleaned_name = re.sub(r'^[✓✗]_\d{8}_\d{6}_', '', original_name)
            cleaned_name = re.sub(r'_[a-f0-9]{8}(_\d+)?\.pdf$', '.pdf', cleaned_name)
            
            dest_path = dest_dir / cleaned_name
            
            # 重複回避
            counter = 1
            while dest_path.exists():
                stem = Path(cleaned_name).stem
                ext = Path(cleaned_name).suffix
                dest_path = dest_dir / f"{stem}_restored_{counter}{ext}"
                counter += 1
            
            # ファイルをコピー（移動ではなく）
            shutil.copy2(str(source), str(dest_path))
            
            logger.info(f"ファイル復元完了: {source.name} → {dest_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"ファイル復元エラー: {e}")
            return False


# シングルトンインスタンス
file_manager = FileManager()