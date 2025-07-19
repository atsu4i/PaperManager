"""
Slack通知サービス
論文処理完了時にSlack DMで通知
"""

import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from ..config import config
from ..models.paper import PaperMetadata
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SlackService:
    """Slack通知クラス"""
    
    def __init__(self):
        self.enabled = config.slack.enabled if hasattr(config, 'slack') else False
        self.client = None
        
        if self.enabled:
            # 環境変数からSlack設定を取得
            bot_token = config.slack_bot_token
            user_id = config.slack_user_id_to_dm
            
            if not bot_token:
                logger.warning("Slack通知が有効ですが、SLACK_BOT_TOKEN環境変数が設定されていません")
                self.enabled = False
            elif not user_id:
                logger.warning("Slack通知が有効ですが、SLACK_USER_ID_TO_DM環境変数が設定されていません")
                self.enabled = False
            else:
                self.client = WebClient(token=bot_token)
                logger.info("Slack通知サービスを初期化しました")
        else:
            logger.debug("Slack通知は無効化されています")
    
    async def send_success_notification(self, paper: PaperMetadata, notion_page_id: str, processing_time: float) -> bool:
        """論文処理成功時の通知"""
        if not self.enabled or not config.slack.notify_success:
            return True
        
        try:
            # Notion ページURLを構築
            notion_url = self._build_notion_url(notion_page_id)
            
            # メッセージを構築
            message = self._build_success_message(paper, notion_url, processing_time)
            
            # DMを送信
            success = await self._send_dm(message)
            
            if success:
                logger.info(f"Slack成功通知を送信しました: {paper.title[:50]}...")
            
            return success
            
        except Exception as e:
            logger.error(f"Slack成功通知エラー: {e}")
            return False
    
    async def send_failure_notification(self, file_name: str, error_message: str, processing_time: float) -> bool:
        """論文処理失敗時の通知"""
        if not self.enabled or not config.slack.notify_failure:
            return True
        
        try:
            # メッセージを構築
            message = self._build_failure_message(file_name, error_message, processing_time)
            
            # DMを送信
            success = await self._send_dm(message)
            
            if success:
                logger.info(f"Slack失敗通知を送信しました: {file_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Slack失敗通知エラー: {e}")
            return False
    
    async def send_duplicate_notification(self, paper: PaperMetadata, existing_page_id: str) -> bool:
        """重複検出時の通知"""
        if not self.enabled or not config.slack.notify_duplicate:
            return True
        
        try:
            # 既存ページURLを構築
            existing_url = self._build_notion_url(existing_page_id)
            
            # メッセージを構築
            message = self._build_duplicate_message(paper, existing_url)
            
            # DMを送信
            success = await self._send_dm(message)
            
            if success:
                logger.info(f"Slack重複通知を送信しました: {paper.title[:50]}...")
            
            return success
            
        except Exception as e:
            logger.error(f"Slack重複通知エラー: {e}")
            return False
    
    def _build_success_message(self, paper: PaperMetadata, notion_url: str, processing_time: float) -> str:
        """成功通知メッセージを構築"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 基本メッセージ
        message_parts = [
            "🎉 *論文処理完了*",
            "",
            f"*タイトル:* {paper.title}",
            f"*処理時間:* {processing_time:.1f}秒",
            f"*完了時刻:* {timestamp}",
        ]
        
        # 著者情報
        if paper.authors:
            authors_str = ", ".join(paper.authors[:3])
            if len(paper.authors) > 3:
                authors_str += f" 他{len(paper.authors) - 3}名"
            message_parts.append(f"*著者:* {authors_str}")
        
        # 雑誌情報
        if paper.journal:
            journal_info = paper.journal
            if paper.publication_year:
                journal_info += f" ({paper.publication_year})"
            message_parts.append(f"*雑誌:* {journal_info}")
        
        # PMID情報
        if paper.pmid:
            pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{paper.pmid}/"
            message_parts.extend([
                f"*PMID:* <{pubmed_url}|{paper.pmid}>"
            ])
        
        # DOI情報
        if paper.doi:
            doi_url = f"https://doi.org/{paper.doi}" if not paper.doi.startswith('http') else paper.doi
            message_parts.append(f"*DOI:* <{doi_url}|{paper.doi}>")
        
        # Notionリンク
        message_parts.extend([
            "",
            f"📄 *Notionページ:* <{notion_url}|論文詳細を開く>"
        ])
        
        # 要約を含める場合
        if config.slack.include_summary and paper.summary_japanese:
            summary = paper.summary_japanese
            if len(summary) > 300:
                summary = summary[:297] + "..."
            message_parts.extend([
                "",
                "*📝 要約:*",
                f"```{summary}```"
            ])
        
        message = "\n".join(message_parts)
        
        # メッセージ長制限
        if len(message) > config.slack.max_message_length:
            # 要約を除去して再構築
            basic_parts = message_parts[:message_parts.index("") if "" in message_parts else len(message_parts)]
            basic_parts.append(f"📄 *Notionページ:* <{notion_url}|論文詳細を開く>")
            message = "\n".join(basic_parts)
        
        return message
    
    def _build_failure_message(self, file_name: str, error_message: str, processing_time: float) -> str:
        """失敗通知メッセージを構築"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        message_parts = [
            "❌ *論文処理失敗*",
            "",
            f"*ファイル:* {file_name}",
            f"*処理時間:* {processing_time:.1f}秒",
            f"*失敗時刻:* {timestamp}",
            "",
            "*エラー詳細:*",
            f"```{error_message}```"
        ]
        
        return "\n".join(message_parts)
    
    def _build_duplicate_message(self, paper: PaperMetadata, existing_url: str) -> str:
        """重複検出通知メッセージを構築"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        message_parts = [
            "🔄 *重複論文検出*",
            "",
            f"*タイトル:* {paper.title}",
            f"*検出時刻:* {timestamp}",
            "",
            "この論文は既にNotionに登録されています。",
            f"📄 *既存ページ:* <{existing_url}|既存の論文を開く>"
        ]
        
        return "\n".join(message_parts)
    
    def _build_notion_url(self, page_id: str) -> str:
        """Notion ページURLを構築"""
        # ページIDから'-'を除去してURL用に変換
        clean_id = page_id.replace('-', '')
        return f"https://www.notion.so/{clean_id}"
    
    async def _send_dm(self, message: str) -> bool:
        """DMを送信"""
        if not self.client:
            return False
        
        try:
            # 非同期でSlack APIを呼び出し
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat_postMessage(
                    channel=config.slack_user_id_to_dm,
                    text=message,
                    mrkdwn=True
                )
            )
            
            if response["ok"]:
                logger.debug("Slack DM送信成功")
                return True
            else:
                logger.error(f"Slack DM送信失敗: {response.get('error', 'Unknown error')}")
                return False
                
        except SlackApiError as e:
            logger.error(f"Slack API エラー: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"Slack DM送信エラー: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """Slack接続をテスト"""
        if not self.enabled:
            logger.info("Slack通知は無効化されています")
            return True
        
        try:
            # テストメッセージを送信
            test_message = "🤖 Paper Manager システムのSlack通知テストです。"
            success = await self._send_dm(test_message)
            
            if success:
                logger.info("Slack接続テスト成功")
            else:
                logger.error("Slack接続テスト失敗")
            
            return success
            
        except Exception as e:
            logger.error(f"Slack接続テストエラー: {e}")
            return False


# シングルトンインスタンス
slack_service = SlackService()