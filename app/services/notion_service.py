"""
Notion API連携サービス
論文データをNotionデータベースに投稿
"""

import asyncio
import json
import aiohttp
import aiofiles
from typing import Optional, Dict, Any
from pathlib import Path
from notion_client import Client
# Notion APIの例外処理を安全にインポート
NotionClientError = Exception  # デフォルトフォールバック

try:
    from notion_client.errors import APIResponseError as NotionClientError
except ImportError:
    try:
        from notion_client.errors import NotionClientError
    except ImportError:
        try:
            # 最新版での代替インポート
            from notion_client.errors import RequestTimeoutError, HTTPResponseError
            NotionClientError = (RequestTimeoutError, HTTPResponseError, Exception)
        except ImportError:
            # 最終フォールバック
            NotionClientError = Exception

from ..config import config
from ..models.paper import PaperMetadata, create_notion_page_data
from ..utils.logger import get_logger

logger = get_logger(__name__)


class NotionService:
    """Notion API連携クラス"""
    
    def __init__(self):
        if not config.notion_token:
            raise ValueError("Notion APIトークンが設定されていません")
        
        self.client = Client(auth=config.notion_token)
        self.database_id = config.notion_database_id
    
    async def create_paper_page(self, paper: PaperMetadata) -> Optional[str]:
        """論文ページをNotionデータベースに作成"""
        try:
            logger.info(f"Notion投稿開始: {paper.title[:50]}...")
            
            # Notion投稿用データを作成
            notion_data = create_notion_page_data(paper, self.database_id)
            
            # データベースにページを作成
            page_id = await self._create_page_with_retry(notion_data.dict())
            
            if page_id:
                logger.info(f"Notion投稿成功: {page_id}")
                return page_id
            else:
                logger.error("Notion投稿失敗: ページIDが取得できませんでした")
                return None
                
        except Exception as e:
            logger.error(f"Notion投稿エラー: {e}")
            return None
    
    async def _create_page_with_retry(self, page_data: Dict[str, Any]) -> Optional[str]:
        """リトライ機能付きでページを作成"""
        
        for attempt in range(config.notion.max_retries):
            try:
                # 非同期ラッパーでNotion APIを呼び出し
                response = await self._async_notion_call(
                    self.client.pages.create,
                    **page_data
                )
                
                return response.get('id')
                
            except NotionClientError as e:
                status = getattr(e, 'status', None) or getattr(e, 'code', None)
                if status == 400:
                    # 400エラーの場合は詳細を調査してデータを修正
                    logger.warning(f"Notion API 400エラー: {e}")
                    
                    # データサイズやフォーマットをチェック
                    fixed_data = self._fix_page_data(page_data)
                    if fixed_data != page_data:
                        logger.info("データを修正して再試行します")
                        page_data = fixed_data
                        continue
                
                logger.warning(f"Notion API呼び出し失敗 (試行 {attempt + 1}/{config.notion.max_retries}): {e}")
                
                if attempt < config.notion.max_retries - 1:
                    await asyncio.sleep(config.notion.retry_delay * (attempt + 1))
                else:
                    raise
                    
            except Exception as e:
                logger.warning(f"予期しないエラー (試行 {attempt + 1}/{config.notion.max_retries}): {e}")
                
                if attempt < config.notion.max_retries - 1:
                    await asyncio.sleep(config.notion.retry_delay * (attempt + 1))
                else:
                    raise
        
        return None
    
    async def _async_notion_call(self, func, **kwargs):
        """Notion API呼び出しを非同期ラッパーで実行"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(**kwargs))
    
    def _fix_page_data(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """ページデータの問題を修正"""
        fixed_data = page_data.copy()
        
        try:
            properties = fixed_data.get('properties', {})
            
            # タイトルの長さ制限
            if 'Title' in properties and 'title' in properties['Title']:
                title_content = properties['Title']['title'][0]['text']['content']
                if len(title_content) > 2000:  # Notionの制限
                    properties['Title']['title'][0]['text']['content'] = title_content[:1997] + "..."
                    logger.info("タイトルを切り詰めました")
            
            # 著者数の制限
            if 'Authors' in properties and 'multi_select' in properties['Authors']:
                authors = properties['Authors']['multi_select']
                if len(authors) > 100:  # Notionの制限
                    properties['Authors']['multi_select'] = authors[:100]
                    logger.info("著者数を制限しました")
                
                # 著者名のクリーニング（カンマ除去、長さ制限）
                cleaned_authors = []
                for author in properties['Authors']['multi_select']:
                    # カンマを除去してクリーニング
                    clean_name = author['name'].replace(',', ' ').strip()
                    # 複数のスペースを単一に
                    clean_name = ' '.join(clean_name.split())
                    # 長さ制限
                    if len(clean_name) > 100:
                        clean_name = clean_name[:97] + "..."
                    # 空文字列や無効な名前をスキップ
                    if clean_name and len(clean_name) > 1:
                        cleaned_authors.append({"name": clean_name})
                
                properties['Authors']['multi_select'] = cleaned_authors
                logger.info(f"著者名をクリーニングしました: {len(cleaned_authors)}名")
            
            # キーワード数の制限
            if 'Key Words' in properties and 'multi_select' in properties['Key Words']:
                keywords = properties['Key Words']['multi_select']
                if len(keywords) > 100:  # Notionの制限
                    properties['Key Words']['multi_select'] = keywords[:100]
                    logger.info("キーワード数を制限しました")
                
                # キーワードのクリーニング（カンマ除去、長さ制限）
                cleaned_keywords = []
                for keyword in properties['Key Words']['multi_select']:
                    # カンマを除去してクリーニング
                    clean_keyword = keyword['name'].replace(',', ' ').strip()
                    # 複数のスペースを単一に
                    clean_keyword = ' '.join(clean_keyword.split())
                    # 長さ制限
                    if len(clean_keyword) > 100:
                        clean_keyword = clean_keyword[:97] + "..."
                    # 空文字列や無効なキーワードをスキップ
                    if clean_keyword and len(clean_keyword) > 1:
                        cleaned_keywords.append({"name": clean_keyword})
                
                properties['Key Words']['multi_select'] = cleaned_keywords
                logger.info(f"キーワードをクリーニングしました: {len(cleaned_keywords)}個")
            
            # Rich textフィールドの長さ制限
            for field_name in ['Volume', 'Issue', 'Pages']:
                if field_name in properties and 'rich_text' in properties[field_name]:
                    rich_text = properties[field_name]['rich_text']
                    if rich_text and len(rich_text[0]['text']['content']) > 2000:
                        rich_text[0]['text']['content'] = rich_text[0]['text']['content'][:1997] + "..."
                        logger.info(f"{field_name}フィールドを切り詰めました")
            
            # 要約（children）の長さ制限
            if 'children' in fixed_data and fixed_data['children']:
                for child in fixed_data['children']:
                    if (child.get('type') == 'paragraph' and 
                        'paragraph' in child and 
                        'rich_text' in child['paragraph']):
                        
                        rich_text = child['paragraph']['rich_text']
                        if rich_text and rich_text[0] and 'text' in rich_text[0]:
                            content = rich_text[0]['text']['content']
                            if len(content) > 1900:
                                # 文の境界で切り詰め
                                truncated = self._truncate_at_sentence_boundary(content, 1900)
                                rich_text[0]['text']['content'] = truncated
                                logger.info(f"要約を切り詰めました: {len(content)} → {len(truncated)}文字")
            
            # Noneや空文字列の除去
            properties = {k: v for k, v in properties.items() 
                         if v is not None and v != "" and v != []}
            
            fixed_data['properties'] = properties
            
        except Exception as e:
            logger.warning(f"データ修正エラー: {e}")
            return page_data
        
        return fixed_data
    
    def _truncate_at_sentence_boundary(self, text: str, max_length: int) -> str:
        """文の境界で自然にテキストを切り詰める"""
        if not text or len(text) <= max_length:
            return text
        
        # 日本語の文区切り文字
        sentence_endings = ['。', '．', '！', '？', '!', '?']
        
        # 最大長以内の位置で最後の文区切りを見つける
        best_pos = -1
        
        # 後ろから検索して、適切な文区切りを見つける
        for i in range(min(max_length - 1, len(text) - 1), -1, -1):
            if text[i] in sentence_endings:
                best_pos = i + 1  # 文区切り文字の直後
                break
        
        # 文区切りが見つからない場合は、句読点での区切りを試す
        if best_pos == -1:
            punctuation_marks = ['、', '，', ',']
            for i in range(min(max_length - 1, len(text) - 1), -1, -1):
                if text[i] in punctuation_marks:
                    best_pos = i + 1
                    break
        
        # それでも見つからない場合は、強制的に切り詰め
        if best_pos == -1:
            best_pos = max_length
        
        # 最終的な位置で切り詰め
        truncated = text[:best_pos].rstrip()
        
        return truncated
    
    async def check_database_connection(self) -> bool:
        """データベース接続をテスト"""
        try:
            response = await self._async_notion_call(
                self.client.databases.query,
                database_id=self.database_id,
                page_size=1
            )
            logger.info("Notionデータベース接続成功")
            return True
            
        except Exception as e:
            logger.error(f"Notionデータベース接続エラー: {e}")
            return False
    
    async def search_existing_paper(self, title: str, doi: str = None) -> Optional[str]:
        """既存の論文ページを検索（正確性を重視）"""
        try:
            # DOIが利用可能な場合は優先的にDOIで検索（最も正確）
            if doi:
                doi_url = f"https://doi.org/{doi}" if not doi.startswith('http') else doi
                response = await self._async_notion_call(
                    self.client.databases.query,
                    database_id=self.database_id,
                    filter={
                        "property": "DOI",
                        "url": {
                            "equals": doi_url
                        }
                    }
                )
                
                if response.get('results'):
                    # DOIで見つかった場合、実際にページが存在するか確認
                    page_id = response['results'][0]['id']
                    if await self._verify_page_exists(page_id):
                        logger.info(f"DOIで既存ページを発見: {page_id}")
                        return page_id
                    else:
                        logger.debug(f"DOIで見つかったページが存在しません: {page_id}")
            
            # タイトルで検索（より厳密なマッチング）
            if title:
                # クリーンなタイトルで検索
                clean_title = self._clean_title_for_search(title)
                
                # 複数の検索戦略を試行
                search_queries = [
                    # 完全一致に近い検索
                    {"property": "Title", "title": {"equals": clean_title}},
                    # 部分一致（より短い文字列で）
                    {"property": "Title", "title": {"contains": clean_title[:30]}} if len(clean_title) > 30 else None
                ]
                
                for query in search_queries:
                    if not query:
                        continue
                        
                    response = await self._async_notion_call(
                        self.client.databases.query,
                        database_id=self.database_id,
                        filter=query
                    )
                    
                    if response.get('results'):
                        # 結果を詳細にチェック
                        for result in response['results']:
                            page_id = result['id']
                            # ページの存在確認
                            if await self._verify_page_exists(page_id):
                                # タイトルの類似性をチェック
                                result_title = self._extract_title_from_result(result)
                                if self._titles_are_similar(clean_title, result_title):
                                    logger.info(f"タイトルで既存ページを発見: {page_id}")
                                    return page_id
                                else:
                                    logger.debug(f"タイトルが類似していません: '{clean_title}' vs '{result_title}'")
                            else:
                                logger.debug(f"タイトル検索で見つかったページが存在しません: {page_id}")
            
            logger.debug("既存ページは見つかりませんでした")
            return None
            
        except Exception as e:
            logger.warning(f"既存ページ検索エラー: {e}")
            return None
    
    def _clean_title_for_search(self, title: str) -> str:
        """検索用にタイトルをクリーンアップ"""
        if not title:
            return ""
        
        # 基本的なクリーニング
        clean = title.strip()
        # 複数の空白を単一に
        clean = ' '.join(clean.split())
        # 特殊文字の正規化
        clean = clean.replace('：', ':').replace('－', '-').replace('—', '-')
        
        return clean
    
    def _extract_title_from_result(self, result: dict) -> str:
        """検索結果からタイトルを抽出"""
        try:
            title_property = result.get('properties', {}).get('Title', {})
            if 'title' in title_property and title_property['title']:
                return title_property['title'][0]['text']['content']
            return ""
        except Exception:
            return ""
    
    def _titles_are_similar(self, title1: str, title2: str, threshold: float = 0.8) -> bool:
        """タイトルの類似性をチェック"""
        if not title1 or not title2:
            return False
        
        # 簡単な類似性チェック（より高度なアルゴリズムも可能）
        title1_words = set(title1.lower().split())
        title2_words = set(title2.lower().split())
        
        if not title1_words or not title2_words:
            return False
        
        # Jaccard係数を使用
        intersection = len(title1_words & title2_words)
        union = len(title1_words | title2_words)
        
        similarity = intersection / union if union > 0 else 0
        return similarity >= threshold
    
    async def _verify_page_exists(self, page_id: str) -> bool:
        """ページが実際に存在するかを確認"""
        try:
            response = await self._async_notion_call(
                self.client.pages.retrieve,
                page_id=page_id
            )
            # ページが存在し、アーカイブされていない場合はTrue
            return response and not response.get('archived', False)
        except Exception as e:
            logger.debug(f"ページ存在確認エラー (ID: {page_id}): {e}")
            return False
    
    async def upload_pdf_to_notion(self, pdf_path: str, filename: str = None) -> Optional[str]:
        """PDFファイルをNotionにアップロード"""
        if not config.notion.enable_pdf_upload:
            logger.debug("PDFアップロードが無効化されています")
            return None
            
        try:
            pdf_file = Path(pdf_path)
            if not pdf_file.exists():
                logger.error(f"PDFファイルが存在しません: {pdf_path}")
                return None
            
            # ファイルサイズチェック
            file_size_mb = pdf_file.stat().st_size / (1024 * 1024)
            if file_size_mb > config.notion.max_pdf_size_mb:
                logger.warning(f"PDFファイルが大きすぎます: {file_size_mb:.1f}MB > {config.notion.max_pdf_size_mb}MB")
                return None
            
            if not filename:
                filename = pdf_file.name
            
            logger.info(f"PDFアップロード開始: {filename} ({file_size_mb:.1f}MB)")
            
            # Step 1: ファイルアップロードリクエストを作成
            upload_request = await self._create_file_upload_request(filename)
            if not upload_request:
                return None
            
            # Step 2: PDFファイルをアップロード
            upload_success = await self._upload_file_to_notion(
                pdf_path, 
                upload_request['upload_url'],
                filename
            )
            
            if not upload_success:
                logger.error(f"PDFファイルのアップロードに失敗: {filename}")
                return None
            
            logger.info(f"PDFアップロード成功: {filename}")
            return upload_request['id']
            
        except Exception as e:
            logger.error(f"PDFアップロードエラー: {e}")
            return None
    
    async def _create_file_upload_request(self, filename: str) -> Optional[Dict]:
        """Notion File Upload APIリクエストを作成"""
        try:
            url = "https://api.notion.com/v1/file_uploads"
            headers = {
                "Authorization": f"Bearer {config.notion_token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }
            
            payload = {
                "name": filename,
                "file": {
                    "type": "file"
                }
            }
            
            logger.debug(f"ファイルアップロードリクエスト開始: {filename}")
            logger.debug(f"URL: {url}")
            logger.debug(f"Headers: {headers}")
            logger.debug(f"Payload: {payload}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    response_text = await response.text()
                    logger.debug(f"Response Status: {response.status}")
                    logger.debug(f"Response Text: {response_text}")
                    
                    if response.status == 200:
                        result = await response.json()
                        logger.debug(f"ファイルアップロードリクエスト成功: {result.get('id')}")
                        return result
                    else:
                        logger.error(f"ファイルアップロードリクエスト失敗 ({response.status}): {response_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"ファイルアップロードリクエストエラー: {e}")
            return None
    
    async def _upload_file_to_notion(self, pdf_path: str, upload_url: str, filename: str = None) -> bool:
        """PDFファイルをNotionにアップロード"""
        try:
            async with aiofiles.open(pdf_path, 'rb') as file:
                file_content = await file.read()
            
            logger.debug(f"ファイルアップロード開始: {pdf_path}")
            logger.debug(f"Upload URL: {upload_url}")
            logger.debug(f"File size: {len(file_content)} bytes")
            
            # ファイル名の決定
            if not filename:
                filename = Path(pdf_path).name
            
            # multipart/form-data形式でアップロード
            data = aiohttp.FormData()
            data.add_field('file', file_content, filename=filename, content_type='application/pdf')
            
            headers = {
                'Authorization': f'Bearer {config.notion_token}',
                'Notion-Version': '2022-06-28'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(upload_url, data=data, headers=headers) as response:
                    response_text = await response.text()
                    logger.debug(f"Upload response status: {response.status}")
                    logger.debug(f"Upload response text: {response_text}")
                    
                    if response.status == 200:
                        logger.debug(f"ファイルアップロード成功: {pdf_path}")
                        return True
                    else:
                        logger.error(f"ファイルアップロード失敗 ({response.status}): {response_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"ファイルアップロードエラー: {e}")
            return False
    
    def _sanitize_filename(self, title: str) -> str:
        """ファイル名に使用できない文字を除去・置換（Notion 100文字制限対応）"""
        if not title:
            return "paper.pdf"
        
        # ファイル名に使用できない文字を置換
        invalid_chars = {
            '<': '＜',    # 全角小なり
            '>': '＞',    # 全角大なり
            ':': '：',    # 全角コロン
            '"': '"',   # 全角ダブルクォート
            '/': '／',    # 全角スラッシュ
            '\\': '＼',   # 全角バックスラッシュ
            '|': '｜',    # 全角パイプ
            '?': '？',    # 全角クエスチョン
            '*': '＊',    # 全角アスタリスク
        }
        
        # 無効な文字を置換
        sanitized = title
        for invalid_char, replacement in invalid_chars.items():
            sanitized = sanitized.replace(invalid_char, replacement)
        
        # 制御文字や特殊文字を除去
        sanitized = ''.join(char for char in sanitized if ord(char) >= 32)
        
        # Notion APIのファイル名制限（100文字）を考慮
        # PDF拡張子（.pdf = 4文字）を除いて96文字まで
        max_base_length = 96
        
        if len(sanitized) > max_base_length:
            # 単語境界で切り詰め
            words = sanitized.split()
            truncated = []
            char_count = 0
            
            for word in words:
                if char_count + len(word) + (1 if truncated else 0) <= max_base_length:
                    truncated.append(word)
                    char_count += len(word) + (1 if len(truncated) > 1 else 0)
                else:
                    break
            
            if truncated:
                sanitized = ' '.join(truncated)
            else:
                # 単語境界で切り詰められない場合は強制切り詰め
                sanitized = sanitized[:max_base_length]
        
        # 空文字列の場合はデフォルト名を使用
        if not sanitized.strip():
            sanitized = "paper"
        
        # PDF拡張子を追加
        final_filename = f"{sanitized.strip()}.pdf"
        
        # 最終チェック：100文字を超えている場合は強制的に切り詰め
        if len(final_filename) > 100:
            base_name = sanitized.strip()[:96]  # .pdf分を除いて96文字
            final_filename = f"{base_name}.pdf"
        
        logger.debug(f"ファイル名サニタイゼーション: '{title}' → '{final_filename}' (長さ: {len(final_filename)})")
        
        return final_filename
    
    async def create_paper_page_with_pdf(self, paper_metadata: PaperMetadata) -> Optional[str]:
        """PDFファイル付きで論文ページを作成"""
        try:
            # PDFアップロード
            pdf_upload_id = None
            if config.notion.enable_pdf_upload and paper_metadata.file_path:
                logger.info(f"PDFアップロード機能が有効です。ファイル: {paper_metadata.file_path}")
                
                # 論文タイトルからファイル名を作成
                paper_filename = self._sanitize_filename(paper_metadata.title)
                logger.info(f"PDFファイル名を論文タイトルに変更: {paper_filename}")
                
                pdf_upload_id = await self.upload_pdf_to_notion(
                    paper_metadata.file_path,
                    paper_filename
                )
                if pdf_upload_id:
                    logger.info(f"PDFアップロード成功: {pdf_upload_id}")
                else:
                    logger.warning("PDFアップロードに失敗しました。PDFなしでページを作成します。")
            else:
                logger.info("PDFアップロードはスキップされました。")
            
            # ページデータを作成
            page_data = create_notion_page_data(paper_metadata, self.database_id)
            
            # PDFファイルをページに追加
            if pdf_upload_id:
                # ファイル名を論文タイトルに変更
                paper_filename = self._sanitize_filename(paper_metadata.title)
                pdf_property = {
                    "files": [
                        {
                            "type": "file_upload",
                            "file_upload": {
                                "id": pdf_upload_id
                            },
                            "name": paper_filename
                        }
                    ]
                }
                page_data.properties[config.notion.pdf_property_name] = pdf_property
                logger.info(f"PDFファイルをページに追加: {config.notion.pdf_property_name}")
            
            # データの修正
            fixed_page_data = self._fix_page_data(page_data.dict())
            
            # ページを作成
            response = await self._async_notion_call(
                self.client.pages.create,
                **fixed_page_data
            )
            
            if response and response.get('id'):
                page_id = response['id']
                logger.info(f"Notionページ作成成功 (PDF付き): {page_id}")
                return page_id
            else:
                logger.error("Notionページ作成に失敗しました")
                return None
                
        except Exception as e:
            logger.error(f"PDF付きページ作成エラー: {e}")
            return None
    
    async def query_database_pages(self, filter_conditions: Optional[Dict] = None, 
                                  page_size: int = 100, start_cursor: Optional[str] = None) -> Optional[Dict]:
        """データベースページを公開メソッドでクエリ（移行スクリプト用）"""
        try:
            query_params = {
                "database_id": self.database_id,
                "page_size": page_size
            }
            
            if filter_conditions:
                query_params["filter"] = filter_conditions
                
            if start_cursor:
                query_params["start_cursor"] = start_cursor
            
            response = await self._async_notion_call(
                self.client.databases.query,
                **query_params
            )
            
            return response
            
        except Exception as e:
            logger.error(f"データベースクエリエラー: {e}")
            return None


# シングルトンインスタンス
notion_service = NotionService()