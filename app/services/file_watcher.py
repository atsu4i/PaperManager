"""
ファイル監視サービス
指定フォルダ内のPDFファイルの追加を監視
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Set, Callable, Dict, Any, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from ..config import config
from ..utils.logger import get_logger
from ..utils.file_manager import file_manager

logger = get_logger(__name__)


class ProcessedFileManager:
    """処理済みファイル管理クラス"""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._processed_files: Dict[str, Dict[str, Any]] = {}
        self._load_processed_files()
    
    def _load_processed_files(self):
        """処理済みファイルデータベースを読み込み"""
        try:
            if self.db_path.exists():
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    self._processed_files = json.load(f)
                logger.info(f"処理済みファイルDB読み込み: {len(self._processed_files)}件")
            else:
                self._processed_files = {}
                logger.info("処理済みファイルDBを新規作成")
        except Exception as e:
            logger.error(f"処理済みファイルDB読み込みエラー: {e}")
            self._processed_files = {}
    
    def _save_processed_files(self):
        """処理済みファイルデータベースを保存"""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(self._processed_files, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"処理済みファイルDB保存エラー: {e}")
    
    def is_processed(self, file_path: str) -> bool:
        """ファイルが処理済みかチェック"""
        path = str(Path(file_path).resolve())
        
        if path not in self._processed_files:
            return False
        
        # ファイルの変更時刻をチェック
        try:
            current_mtime = Path(file_path).stat().st_mtime
            stored_mtime = self._processed_files[path].get('mtime', 0)
            
            # 変更時刻が異なる場合は未処理扱い
            if abs(current_mtime - stored_mtime) > 1:  # 1秒の誤差を許容
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"ファイル情報取得エラー: {e}")
            return False
    
    def mark_processed(self, file_path: str, success: bool, notion_page_id: Optional[str] = None):
        """ファイルを処理済みとしてマーク"""
        path = str(Path(file_path).resolve())
        
        try:
            # ファイルが存在するかチェック
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.warning(f"処理済みマーク対象ファイルが見つかりません: {file_path}")
                # ファイルが存在しない場合でも処理情報は記録
                self._processed_files[path] = {
                    'processed_at': time.time(),
                    'mtime': 0,  # ファイルが存在しないため0
                    'size': 0,   # ファイルが存在しないため0
                    'success': success,
                    'notion_page_id': notion_page_id,
                    'moved_to': None,
                    'moved_success': False
                }
                self._save_processed_files()
                return
            
            # ファイル情報を事前に取得（移動前）
            file_stat = file_path_obj.stat()
            
            # ファイルを移動
            moved_success, moved_path = file_manager.move_processed_file(
                file_path, success, notion_page_id
            )
            
            # 処理情報を記録
            self._processed_files[path] = {
                'processed_at': time.time(),
                'mtime': file_stat.st_mtime,
                'size': file_stat.st_size,
                'success': success,
                'notion_page_id': notion_page_id,
                'moved_to': moved_path if moved_success else None,
                'moved_success': moved_success
            }
            self._save_processed_files()
            
            if moved_success:
                logger.info(f"処理済みマーク＆移動完了: {Path(file_path).name}")
            else:
                logger.warning(f"処理済みマーク完了（移動失敗）: {Path(file_path).name}")
            
        except Exception as e:
            logger.error(f"処理済みマークエラー: {e}")
            # エラーが発生した場合でも最低限の情報は記録
            try:
                self._processed_files[path] = {
                    'processed_at': time.time(),
                    'mtime': 0,
                    'size': 0,
                    'success': success,
                    'notion_page_id': notion_page_id,
                    'moved_to': None,
                    'moved_success': False,
                    'error': str(e)
                }
                self._save_processed_files()
            except Exception as save_error:
                logger.error(f"処理済み情報の保存にも失敗: {save_error}")
    
    def get_processed_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """処理済みファイルの情報を取得"""
        path = str(Path(file_path).resolve())
        return self._processed_files.get(path)


class PDFFileHandler(FileSystemEventHandler):
    """PDFファイル監視ハンドラー"""
    
    def __init__(self, callback: Callable[[str], None]):
        super().__init__()
        self.callback = callback
        self.pending_files: Dict[str, float] = {}  # ファイルパス: 追加時刻
        self.recently_processed: Dict[str, float] = {}  # 重複処理防止用
        
    def on_created(self, event: FileSystemEvent):
        """ファイル作成時の処理"""
        if not event.is_directory:
            self._handle_file_event(event.src_path, "created")
    
    def on_moved(self, event: FileSystemEvent):
        """ファイル移動時の処理"""
        if not event.is_directory:
            self._handle_file_event(event.dest_path, "moved")
    
    def on_modified(self, event: FileSystemEvent):
        """ファイル変更時の処理"""
        if not event.is_directory:
            self._handle_file_event(event.src_path, "modified")
    
    def _handle_file_event(self, file_path: str, event_type: str):
        """ファイルイベントの処理"""
        try:
            path = Path(file_path)
            file_path_normalized = str(path.resolve())
            
            # PDFファイルのみを対象
            if path.suffix.lower() not in config.file_processing.supported_extensions:
                return
            
            # ファイルが存在し、読み取り可能かチェック
            if not path.exists() or not path.is_file():
                return
            
            # 一時ファイルや隠しファイルを除外
            if path.name.startswith('.') or path.name.startswith('~'):
                return
            
            # 重複処理防止チェック（30秒以内の同じファイルは無視）
            current_time = time.time()
            if file_path_normalized in self.recently_processed:
                last_processed = self.recently_processed[file_path_normalized]
                if current_time - last_processed < 30:  # 30秒以内
                    logger.debug(f"重複処理をスキップ: {path.name} ({event_type})")
                    return
            
            # ファイルサイズのチェック
            try:
                size = path.stat().st_size
                if size == 0:
                    logger.debug(f"空ファイルをスキップ: {path.name}")
                    return
                
                max_size = config.file_processing.max_pdf_size * 1024 * 1024
                if size > max_size:
                    logger.warning(f"ファイルサイズ超過: {path.name} ({size / 1024 / 1024:.1f}MB)")
                    return
                    
            except Exception as e:
                logger.warning(f"ファイルサイズ取得エラー: {e}")
                return
            
            # ファイルのロック状態をチェック（他のプロセスが書き込み中の可能性）
            if not self._is_file_ready(file_path):
                # 少し待ってから再度チェック
                self.pending_files[file_path] = time.time()
                return
            
            # 待機中ファイルの場合は除去
            if file_path in self.pending_files:
                del self.pending_files[file_path]
            
            # 処理記録を追加
            self.recently_processed[file_path_normalized] = current_time
            
            # 古い処理記録をクリーンアップ（1時間以上古いものを削除）
            self._cleanup_recent_processed()
            
            logger.info(f"新しいPDFファイルを検出: {path.name} ({event_type})")
            
            # コールバック実行
            self.callback(file_path)
            
        except Exception as e:
            logger.error(f"ファイルイベント処理エラー: {e}")
    
    def _cleanup_recent_processed(self):
        """古い処理記録をクリーンアップ"""
        current_time = time.time()
        expired_files = []
        
        for file_path, processed_time in self.recently_processed.items():
            if current_time - processed_time > 3600:  # 1時間
                expired_files.append(file_path)
        
        for file_path in expired_files:
            del self.recently_processed[file_path]
    
    def _is_file_ready(self, file_path: str) -> bool:
        """ファイルが処理可能な状態かチェック"""
        try:
            # ファイルを排他モードで開いてみる
            with open(file_path, 'rb') as f:
                # 少しデータを読んでみる
                f.read(1024)
            return True
        except (IOError, OSError):
            return False
    
    def check_pending_files(self):
        """待機中ファイルの再チェック"""
        current_time = time.time()
        ready_files = []
        
        for file_path, added_time in list(self.pending_files.items()):
            # 5秒以上経過した場合
            if current_time - added_time > 5:
                if self._is_file_ready(file_path):
                    ready_files.append(file_path)
                    del self.pending_files[file_path]
                elif current_time - added_time > 30:  # 30秒でタイムアウト
                    logger.warning(f"ファイル準備タイムアウト: {Path(file_path).name}")
                    del self.pending_files[file_path]
        
        # 準備完了ファイルを処理
        for file_path in ready_files:
            logger.info(f"待機中ファイルが準備完了: {Path(file_path).name}")
            self.callback(file_path)


class FileWatcher:
    """ファイル監視サービス"""
    
    def __init__(self, watch_folder: str, callback: Callable[[str], None]):
        self.watch_folder = Path(watch_folder)
        self.callback = callback
        self.observer = None
        self.handler = None
        self.processed_file_manager = ProcessedFileManager(config.processed_files_db)
        self.is_running = False
        
        # 監視フォルダを作成
        self.watch_folder.mkdir(parents=True, exist_ok=True)
        
    def start(self):
        """ファイル監視を開始"""
        try:
            logger.info(f"ファイル監視開始: {self.watch_folder}")
            
            # ハンドラーとオブザーバーを作成
            self.handler = PDFFileHandler(self._on_file_detected)
            self.observer = Observer()
            self.observer.schedule(self.handler, str(self.watch_folder), recursive=True)
            
            # 監視開始
            self.observer.start()
            self.is_running = True
            
            # 既存ファイルの初回スキャン
            self._scan_existing_files()
            
            logger.info("ファイル監視が開始されました")
            
        except Exception as e:
            logger.error(f"ファイル監視開始エラー: {e}")
            raise
    
    def stop(self):
        """ファイル監視を停止"""
        try:
            if self.observer and self.observer.is_alive():
                self.observer.stop()
                self.observer.join()
                self.is_running = False
                logger.info("ファイル監視を停止しました")
        except Exception as e:
            logger.error(f"ファイル監視停止エラー: {e}")
    
    def _scan_existing_files(self):
        """既存ファイルのスキャン"""
        try:
            logger.info("既存ファイルをスキャン中...")
            
            pdf_files = list(self.watch_folder.rglob("*.pdf"))
            unprocessed_files = []
            
            for pdf_file in pdf_files:
                if not self.processed_file_manager.is_processed(str(pdf_file)):
                    unprocessed_files.append(pdf_file)
            
            logger.info(f"未処理ファイル発見: {len(unprocessed_files)}件")
            
            # 未処理ファイルを順次処理
            for pdf_file in unprocessed_files:
                self._on_file_detected(str(pdf_file))
                
        except Exception as e:
            logger.error(f"既存ファイルスキャンエラー: {e}")
    
    def _on_file_detected(self, file_path: str):
        """ファイル検出時の処理"""
        try:
            # 処理済みチェック
            if self.processed_file_manager.is_processed(file_path):
                logger.debug(f"処理済みファイルをスキップ: {Path(file_path).name}")
                return
            
            # コールバック実行
            logger.info(f"新規ファイルを処理キューに追加: {Path(file_path).name}")
            self.callback(file_path)
            
        except Exception as e:
            logger.error(f"ファイル検出処理エラー: {e}")
    
    def mark_file_processed(self, file_path: str, success: bool, notion_page_id: Optional[str] = None):
        """ファイルを処理済みとしてマーク"""
        self.processed_file_manager.mark_processed(file_path, success, notion_page_id)
    
    def is_file_processed(self, file_path: str) -> bool:
        """ファイルが処理済みかチェック"""
        return self.processed_file_manager.is_processed(file_path)
    
    async def run_periodic_tasks(self):
        """定期実行タスク"""
        while self.is_running:
            try:
                # 待機中ファイルのチェック
                if self.handler:
                    self.handler.check_pending_files()
                
                await asyncio.sleep(5)  # 5秒間隔
                
            except Exception as e:
                logger.error(f"定期タスクエラー: {e}")
                await asyncio.sleep(5)