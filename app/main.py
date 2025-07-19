"""
メインアプリケーション
論文管理の自動化システム
"""

import asyncio
import signal
import time
from pathlib import Path
from typing import Optional, Dict
from concurrent.futures import ThreadPoolExecutor

from .config import config
from .models.paper import PaperMetadata, ProcessingResult
from .services.pdf_processor import pdf_processor
from .services.gemini_service import gemini_service
from .services.pubmed_service import pubmed_service
from .services.notion_service import notion_service
from .services.slack_service import slack_service
from .services.file_watcher import FileWatcher
from .utils.logger import get_logger

logger = get_logger(__name__)


class PaperManager:
    """論文管理システムメインクラス"""
    
    def __init__(self):
        self.file_watcher: Optional[FileWatcher] = None
        self.processing_queue = asyncio.Queue(maxsize=config.file_processing.max_concurrent_files * 2)
        self.is_running = False
        self.executor = ThreadPoolExecutor(max_workers=config.file_processing.max_concurrent_files)
        
    async def start(self):
        """システム開始"""
        try:
            logger.info("論文管理システムを開始します...")
            
            # 接続テスト
            await self._check_connections()
            
            # ファイル監視の開始
            self.file_watcher = FileWatcher(
                watch_folder=config.watch_folder,
                callback=self._on_new_file
            )
            self.file_watcher.start()
            
            # 処理タスクの開始
            self.is_running = True
            
            # 並行タスクを開始
            tasks = [
                asyncio.create_task(self._file_processor_worker()),
                asyncio.create_task(self._periodic_tasks()),
            ]
            
            # 複数のワーカーを起動
            for i in range(config.file_processing.max_concurrent_files):
                tasks.append(asyncio.create_task(self._file_processor_worker(worker_id=i)))
            
            logger.info("システムが正常に開始されました")
            
            # シグナルハンドラーを設定
            loop = asyncio.get_event_loop()
            for sig in [signal.SIGTERM, signal.SIGINT]:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
            
            # すべてのタスクが完了するまで待機
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"システム開始エラー: {e}")
            await self.stop()
            raise
    
    async def stop(self):
        """システム停止"""
        try:
            logger.info("システムを停止します...")
            
            self.is_running = False
            
            # ファイル監視停止
            if self.file_watcher:
                self.file_watcher.stop()
            
            # エグゼキューターの停止
            self.executor.shutdown(wait=True)
            
            logger.info("システムが正常に停止されました")
            
        except Exception as e:
            logger.error(f"システム停止エラー: {e}")
    
    async def _check_connections(self):
        """外部サービス接続チェック"""
        logger.info("外部サービス接続をチェック中...")
        
        # Notion接続チェック
        if not await notion_service.check_database_connection():
            raise ConnectionError("Notionデータベースに接続できません")
        
        # Slack接続チェック（有効な場合のみ）
        if slack_service.enabled:
            if not await slack_service.test_connection():
                logger.warning("Slack接続に問題がありますが、処理を続行します")
        
        logger.info("すべての外部サービスに正常に接続しました")
    
    def _on_new_file(self, file_path: str):
        """新しいファイル検出時のコールバック"""
        try:
            # キューに追加（ノンブロッキング）
            try:
                self.processing_queue.put_nowait(file_path)
                logger.info(f"処理キューに追加: {Path(file_path).name}")
            except asyncio.QueueFull:
                logger.warning(f"処理キューが満杯です。ファイルをスキップ: {Path(file_path).name}")
                
        except Exception as e:
            logger.error(f"ファイル追加エラー: {e}")
    
    async def _file_processor_worker(self, worker_id: int = 0):
        """ファイル処理ワーカー"""
        logger.info(f"ファイル処理ワーカー {worker_id} を開始")
        
        while self.is_running:
            try:
                # キューからファイルを取得（タイムアウト付き）
                try:
                    file_path = await asyncio.wait_for(
                        self.processing_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # ファイル処理実行
                await self._process_file(file_path, worker_id)
                
                # 処理間隔
                await asyncio.sleep(config.file_processing.processing_interval)
                
            except Exception as e:
                logger.error(f"ワーカー {worker_id} エラー: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"ファイル処理ワーカー {worker_id} を停止")
    
    async def _process_file(self, file_path: str, worker_id: int = 0) -> ProcessingResult:
        """単一ファイルの処理"""
        start_time = time.time()
        file_name = Path(file_path).name
        
        logger.info(f"[Worker {worker_id}] ファイル処理開始: {file_name}")
        
        try:
            # ファイル情報の取得
            file_stat = Path(file_path).stat()
            
            # 1. PDFからテキスト抽出
            logger.info(f"[Worker {worker_id}] PDF処理中: {file_name}")
            pdf_text = await pdf_processor.extract_text_from_pdf(file_path)
            
            if not pdf_text or len(pdf_text.strip()) < 100:
                raise ValueError("PDFから十分なテキストを抽出できませんでした")
            
            # 2. Geminiで論文解析
            logger.info(f"[Worker {worker_id}] 論文解析中: {file_name}")
            paper_metadata = await gemini_service.analyze_paper(pdf_text, file_name)
            
            # ファイル情報を設定
            paper_metadata.file_path = file_path
            paper_metadata.file_size = file_stat.st_size
            
            # 3. PubMed検索
            logger.info(f"[Worker {worker_id}] PubMed検索中: {file_name}")
            pmid = await pubmed_service.search_pmid(paper_metadata)
            if pmid:
                paper_metadata.pmid = pmid
                paper_metadata.pubmed_url = pubmed_service.create_pubmed_url(pmid)
                
                # 4. PMIDが取得できた場合、PubMedから正確なメタデータを取得
                logger.info(f"[Worker {worker_id}] PubMedメタデータ取得中: {file_name}")
                pubmed_metadata = await pubmed_service.fetch_metadata_from_pubmed(pmid)
                
                if pubmed_metadata:
                    # PubMedメタデータでGeminiの結果を更新（より信頼性が高い）
                    paper_metadata = await self._merge_metadata(paper_metadata, pubmed_metadata)
                    logger.info(f"[Worker {worker_id}] PubMedメタデータで更新完了: {file_name}")
                else:
                    logger.warning(f"[Worker {worker_id}] PubMedメタデータ取得に失敗: {file_name}")
            
            # 5. 重複チェック
            existing_page_id = await notion_service.search_existing_paper(
                paper_metadata.title,
                paper_metadata.doi
            )
            
            if existing_page_id:
                logger.warning(f"[Worker {worker_id}] 既存ページが見つかりました: {file_name}")
                
                # Slack重複通知
                if slack_service.enabled:
                    await slack_service.send_duplicate_notification(paper_metadata, existing_page_id)
                
                # 処理済みとしてマーク
                if self.file_watcher:
                    self.file_watcher.mark_file_processed(file_path, True, existing_page_id)
                
                return ProcessingResult(
                    success=True,
                    paper_metadata=paper_metadata,
                    notion_page_id=existing_page_id,
                    processing_time=time.time() - start_time
                )
            
            # 6. Notionに投稿（PDF付き）
            logger.info(f"[Worker {worker_id}] Notion投稿中 (PDF付き): {file_name}")
            notion_page_id = await notion_service.create_paper_page_with_pdf(paper_metadata)
            
            if not notion_page_id:
                raise Exception("Notion投稿に失敗しました")
            
            # 成功として処理済みマーク
            if self.file_watcher:
                self.file_watcher.mark_file_processed(file_path, True, notion_page_id)
            
            processing_time = time.time() - start_time
            logger.info(f"[Worker {worker_id}] 処理完了: {file_name} ({processing_time:.1f}秒)")
            
            # Slack成功通知
            if slack_service.enabled:
                await slack_service.send_success_notification(paper_metadata, notion_page_id, processing_time)
            
            return ProcessingResult(
                success=True,
                paper_metadata=paper_metadata,
                notion_page_id=notion_page_id,
                processing_time=processing_time
            )
            
        except Exception as e:
            error_msg = f"ファイル処理エラー: {e}"
            logger.error(f"[Worker {worker_id}] {error_msg}")
            
            processing_time = time.time() - start_time
            
            # Slack失敗通知
            if slack_service.enabled:
                await slack_service.send_failure_notification(file_name, error_msg, processing_time)
            
            # 失敗として処理済みマーク
            if self.file_watcher:
                self.file_watcher.mark_file_processed(file_path, False)
            
            return ProcessingResult(
                success=False,
                error_message=error_msg,
                processing_time=processing_time
            )
    
    async def _merge_metadata(self, gemini_metadata: PaperMetadata, pubmed_metadata: Dict) -> PaperMetadata:
        """GeminiとPubMedのメタデータをマージ（PubMedを優先）"""
        try:
            # PubMedメタデータを優先して更新
            if pubmed_metadata.get("title"):
                gemini_metadata.title = pubmed_metadata["title"]
            
            if pubmed_metadata.get("authors"):
                gemini_metadata.authors = pubmed_metadata["authors"]
            
            if pubmed_metadata.get("journal"):
                gemini_metadata.journal = pubmed_metadata["journal"]
            
            if pubmed_metadata.get("publication_year"):
                gemini_metadata.publication_year = pubmed_metadata["publication_year"]
            
            if pubmed_metadata.get("doi"):
                gemini_metadata.doi = pubmed_metadata["doi"]
            
            if pubmed_metadata.get("keywords"):
                gemini_metadata.keywords = pubmed_metadata["keywords"]
            
            # PubMedの抄録がある場合は追加情報として保存
            if pubmed_metadata.get("abstract"):
                # 抄録をadditional_infoに追加
                if not gemini_metadata.additional_info:
                    gemini_metadata.additional_info = {}
                gemini_metadata.additional_info["pubmed_abstract"] = pubmed_metadata["abstract"]
            
            logger.info(f"メタデータマージ完了: PubMed優先で更新")
            return gemini_metadata
            
        except Exception as e:
            logger.error(f"メタデータマージエラー: {e}")
            return gemini_metadata
    
    async def _periodic_tasks(self):
        """定期実行タスク"""
        while self.is_running:
            try:
                # ファイル監視の定期タスク
                if self.file_watcher:
                    await self.file_watcher.run_periodic_tasks()
                
            except Exception as e:
                logger.error(f"定期タスクエラー: {e}")
                await asyncio.sleep(5)
    
    async def process_single_file(self, file_path: str) -> ProcessingResult:
        """単一ファイルの手動処理（CLI用）"""
        if not Path(file_path).exists():
            return ProcessingResult(
                success=False,
                error_message=f"ファイルが存在しません: {file_path}"
            )
        
        return await self._process_file(file_path)


# メインアプリケーションインスタンス
app = PaperManager()


async def main():
    """メイン関数"""
    try:
        await app.start()
    except KeyboardInterrupt:
        logger.info("ユーザーによる中断")
    except Exception as e:
        logger.error(f"アプリケーションエラー: {e}")
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())