"""
Notion API連携サービス
論文データをNotionデータベースに投稿
"""

import asyncio
import json
from typing import Optional, Dict, Any
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
                
                # キーワードの長さ制限
                for keyword in properties['Key Words']['multi_select']:
                    if len(keyword['name']) > 100:
                        keyword['name'] = keyword['name'][:97] + "..."
            
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
        """既存の論文ページを検索"""
        try:
            # タイトルで検索
            if title:
                response = await self._async_notion_call(
                    self.client.databases.query,
                    database_id=self.database_id,
                    filter={
                        "property": "Title",
                        "title": {
                            "contains": title[:50]  # 最初の50文字で検索
                        }
                    }
                )
                
                if response.get('results'):
                    page_id = response['results'][0]['id']
                    logger.info(f"既存ページを発見: {page_id}")
                    return page_id
            
            # DOIで検索
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
                    page_id = response['results'][0]['id']
                    logger.info(f"DOIで既存ページを発見: {page_id}")
                    return page_id
            
            return None
            
        except Exception as e:
            logger.warning(f"既存ページ検索エラー: {e}")
            return None


# シングルトンインスタンス
notion_service = NotionService()