"""
PDF処理サービス
Google Cloud Vision APIを使用してPDFからテキストを抽出
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional, Tuple
# import fitz  # PyMuPDF - オプション機能のため無効化
from google.cloud import vision
from google.cloud import storage
from google.api_core import retry
import io
import tempfile
import os

from ..config import config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PDFProcessor:
    """PDF処理クラス"""
    
    def __init__(self):
        self.vision_client = vision.ImageAnnotatorClient()
        self.storage_client = storage.Client()
        self.bucket_name = self._get_or_create_bucket()
        
    def _get_or_create_bucket(self) -> str:
        """GCSバケットを取得または作成"""
        bucket_name = f"paper-manager-temp-{int(time.time())}"
        try:
            bucket = self.storage_client.bucket(bucket_name)
            if not bucket.exists():
                bucket = self.storage_client.create_bucket(bucket_name, location="us-central1")
                logger.info(f"一時バケットを作成しました: {bucket_name}")
            return bucket_name
        except Exception as e:
            logger.error(f"バケット作成エラー: {e}")
            raise
    
    async def extract_text_from_pdf(self, pdf_path: str) -> str:
        """PDFからテキストを抽出"""
        try:
            logger.info(f"PDF処理開始: {pdf_path}")
            
            # PDFファイルの検証
            if not self._validate_pdf_file(pdf_path):
                raise ValueError(f"無効なPDFファイル: {pdf_path}")
            
            # PyMuPDFは無効化されているため、直接Vision APIを使用
            logger.info("Vision APIでOCR処理を実行")
            return await self._extract_text_with_vision_api(pdf_path)
            
        except Exception as e:
            logger.error(f"PDF処理エラー: {e}")
            raise
    
    def _validate_pdf_file(self, pdf_path: str) -> bool:
        """PDFファイルの検証"""
        path = Path(pdf_path)
        
        if not path.exists():
            logger.error(f"ファイルが存在しません: {pdf_path}")
            return False
        
        if path.stat().st_size == 0:
            logger.error(f"空のファイルです: {pdf_path}")
            return False
        
        if path.stat().st_size > config.file_processing.max_pdf_size * 1024 * 1024:
            logger.error(f"ファイルサイズが上限を超えています: {pdf_path}")
            return False
        
        # PDFヘッダーの確認
        try:
            with open(pdf_path, 'rb') as f:
                header = f.read(8)
                if not header.startswith(b'%PDF-'):
                    logger.error(f"PDFヘッダーが不正です: {pdf_path}")
                    return False
        except Exception as e:
            logger.error(f"ファイル読み込みエラー: {e}")
            return False
        
        return True
    
    def _extract_text_simple(self, pdf_path: str) -> str:
        """PyMuPDF機能は無効化済み - Vision APIを使用"""
        logger.info("PyMuPDF機能は無効化されています。Vision APIを使用します。")
        return ""
    
    async def _extract_text_with_vision_api(self, pdf_path: str) -> str:
        """Vision APIを使用したOCRテキスト抽出"""
        try:
            # PDFをGCSにアップロード
            gcs_uri = await self._upload_to_gcs(pdf_path)
            logger.info(f"GCSアップロード完了: {gcs_uri}")
            
            # Vision APIで処理
            text = await self._process_with_vision_api(gcs_uri)
            
            # 一時ファイルを削除
            await self._cleanup_gcs_file(gcs_uri)
            
            return text
            
        except Exception as e:
            logger.error(f"Vision API処理エラー: {e}")
            raise
    
    async def _upload_to_gcs(self, pdf_path: str) -> str:
        """PDFファイルをGCSにアップロード"""
        try:
            bucket = self.storage_client.bucket(self.bucket_name)
            file_name = f"temp_pdf_{int(time.time())}_{Path(pdf_path).name}"
            blob = bucket.blob(file_name)
            
            # ファイルをアップロード
            blob.upload_from_filename(pdf_path)
            
            gcs_uri = f"gs://{self.bucket_name}/{file_name}"
            logger.info(f"GCSアップロード成功: {gcs_uri}")
            return gcs_uri
            
        except Exception as e:
            logger.error(f"GCSアップロードエラー: {e}")
            raise
    
    async def _process_with_vision_api(self, gcs_uri: str) -> str:
        """Vision APIでPDFを処理"""
        try:
            # まず同期処理を試行（より確実）
            logger.info("Vision API同期処理を試行")
            try:
                text = await self._process_with_vision_api_simple(gcs_uri)
                if text and len(text.strip()) > 100:  # 十分なテキストが取得できた場合
                    return text
                else:
                    logger.warning("同期処理で十分なテキストが取得できませんでした。非同期処理にフォールバック")
            except Exception as sync_error:
                logger.warning(f"同期処理失敗: {sync_error}. 非同期処理にフォールバック")
            
            # 非同期処理にフォールバック
            logger.info("Vision API非同期処理を使用")
            
            # 非同期ドキュメント処理リクエストを作成
            feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
            gcs_source = vision.GcsSource(uri=gcs_uri)
            input_config = vision.InputConfig(gcs_source=gcs_source, mime_type='application/pdf')
            
            # 出力先の設定
            gcs_destination = vision.GcsDestination(uri=f"{gcs_uri}_output/")
            output_config = vision.OutputConfig(gcs_destination=gcs_destination, batch_size=100)
            
            # 非同期リクエストを開始
            async_request = vision.AsyncAnnotateFileRequest(
                features=[feature],
                input_config=input_config,
                output_config=output_config
            )
            
            operation = self.vision_client.async_batch_annotate_files(requests=[async_request])
            
            # Operationオブジェクトの属性を安全に取得
            operation_name = getattr(operation, 'name', getattr(operation, 'operation_id', 'unknown'))
            logger.info(f"Vision API非同期処理開始: {operation_name}")
            
            # 処理完了を待機（より長いタイムアウト）
            result = operation.result(timeout=600)  # 10分でタイムアウト
            
            # 結果を取得（リトライ機能付き）
            text = await self._get_vision_api_result_with_retry(f"{gcs_uri}_output/")
            logger.info(f"Vision APIで抽出されたテキスト: {len(text)}文字")
            
            return text
            
        except Exception as e:
            logger.error(f"Vision API処理エラー: {e}")
            raise
    
    async def _process_with_vision_api_simple(self, gcs_uri: str) -> str:
        """Vision APIでPDFを処理（同期版）"""
        try:
            # 同期的なドキュメント処理
            feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
            gcs_source = vision.GcsSource(uri=gcs_uri)
            input_config = vision.InputConfig(gcs_source=gcs_source, mime_type='application/pdf')
            
            # 同期リクエストを作成
            request = vision.AnnotateFileRequest(
                features=[feature],
                input_config=input_config,
                pages=[]  # 全ページを処理
            )
            
            logger.info("Vision API同期処理を開始")
            # 正しいメソッド名を使用
            response = self.vision_client.batch_annotate_files(requests=[request])
            
            # レスポンスからテキストを抽出
            text_parts = []
            for response_item in response.responses:
                if response_item.full_text_annotation:
                    text_parts.append(response_item.full_text_annotation.text)
            
            full_text = '\n'.join(text_parts)
            logger.info(f"Vision API同期処理で抽出されたテキスト: {len(full_text)}文字")
            
            return full_text
            
        except Exception as e:
            logger.warning(f"Vision API同期処理エラー: {e}")
            raise
    
    async def _get_vision_api_result(self, output_uri: str) -> str:
        """Vision APIの結果を取得"""
        try:
            bucket_name = output_uri.split('/')[2]
            prefix = '/'.join(output_uri.split('/')[3:])
            
            bucket = self.storage_client.bucket(bucket_name)
            blobs = bucket.list_blobs(prefix=prefix)
            
            text_parts = []
            for blob in blobs:
                if blob.name.endswith('.json'):
                    json_content = blob.download_as_text()
                    import json
                    data = json.loads(json_content)
                    
                    for response in data.get('responses', []):
                        if 'fullTextAnnotation' in response:
                            text_parts.append(response['fullTextAnnotation']['text'])
            
            return '\n'.join(text_parts)
            
        except Exception as e:
            logger.error(f"Vision API結果取得エラー: {e}")
            raise
    
    async def _get_vision_api_result_with_retry(self, output_uri: str, max_retries: int = 5) -> str:
        """Vision APIの結果を取得（リトライ機能付き）"""
        import asyncio
        
        for attempt in range(max_retries):
            try:
                # 最初の試行では少し待機
                if attempt > 0:
                    wait_time = min(2 ** attempt, 30)  # 指数バックオフ（最大30秒）
                    logger.info(f"Vision API結果取得リトライ {attempt + 1}/{max_retries}（{wait_time}秒後）")
                    await asyncio.sleep(wait_time)
                
                bucket_name = output_uri.split('/')[2]
                prefix = '/'.join(output_uri.split('/')[3:])
                
                bucket = self.storage_client.bucket(bucket_name)
                blobs = list(bucket.list_blobs(prefix=prefix))
                
                if not blobs:
                    logger.warning(f"Vision API結果ファイルが見つかりません（試行 {attempt + 1}）")
                    continue
                
                text_parts = []
                for blob in blobs:
                    if blob.name.endswith('.json'):
                        try:
                            json_content = blob.download_as_text()
                            import json
                            data = json.loads(json_content)
                            
                            for response in data.get('responses', []):
                                if 'fullTextAnnotation' in response:
                                    text_parts.append(response['fullTextAnnotation']['text'])
                        except Exception as blob_error:
                            logger.warning(f"ファイル読み込みエラー {blob.name}: {blob_error}")
                            continue
                
                if text_parts:
                    result_text = '\n'.join(text_parts)
                    logger.info(f"Vision API結果取得成功（試行 {attempt + 1}）: {len(result_text)}文字")
                    return result_text
                else:
                    logger.warning(f"テキストが抽出できませんでした（試行 {attempt + 1}）")
                
            except Exception as e:
                logger.warning(f"Vision API結果取得エラー（試行 {attempt + 1}）: {e}")
                if attempt == max_retries - 1:
                    raise
        
        raise Exception("Vision API結果取得に失敗しました（最大リトライ回数に到達）")
    
    async def _cleanup_gcs_file(self, gcs_uri: str):
        """GCSの一時ファイルを削除"""
        try:
            bucket_name = gcs_uri.split('/')[2]
            file_name = '/'.join(gcs_uri.split('/')[3:])
            
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(file_name)
            
            if blob.exists():
                blob.delete()
                logger.info(f"一時ファイル削除: {gcs_uri}")
            
            # 出力ディレクトリも削除
            output_prefix = f"{file_name}_output/"
            blobs = bucket.list_blobs(prefix=output_prefix)
            for blob in blobs:
                blob.delete()
                
        except Exception as e:
            logger.warning(f"一時ファイル削除エラー: {e}")


# シングルトンインスタンス
pdf_processor = PDFProcessor()