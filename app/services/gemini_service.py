"""
Gemini API連携サービス
論文の解析と要約を行う
"""

import asyncio
import json
import re
from typing import Dict, List, Optional, Tuple
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from ..config import config
from ..models.paper import PaperMetadata
from ..utils.logger import get_logger

logger = get_logger(__name__)


class GeminiService:
    """Gemini API連携クラス"""
    
    def __init__(self):
        if not config.gemini_api_key:
            raise ValueError("Gemini API キーが設定されていません")
        
        genai.configure(api_key=config.gemini_api_key)
        self.model = genai.GenerativeModel(
            model_name=config.gemini.model,
            generation_config=genai.types.GenerationConfig(
                temperature=config.gemini.temperature,
                max_output_tokens=config.gemini.max_tokens,
            ),
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
    
    async def analyze_paper(self, pdf_text: str, file_name: str) -> PaperMetadata:
        """論文の解析とメタデータ抽出"""
        try:
            logger.info(f"論文解析開始: {file_name}")
            
            # メタデータ抽出
            metadata = await self._extract_metadata(pdf_text)
            
            # 日本語要約作成
            japanese_summary = await self._create_japanese_summary(pdf_text)
            
            # PaperMetadataオブジェクトの作成
            paper_metadata = PaperMetadata(
                title=metadata.get('title', ''),
                authors=metadata.get('authors', []),
                publication_year=metadata.get('publication_year'),
                journal=metadata.get('journal'),
                volume=metadata.get('volume'),
                issue=metadata.get('issue'),
                pages=metadata.get('pages'),
                doi=metadata.get('doi'),
                keywords=metadata.get('keywords', []),
                abstract=metadata.get('abstract'),
                summary_japanese=japanese_summary,
                full_text=pdf_text,
                file_path="",  # 後で設定
                file_name=file_name,
                file_size=0  # 後で設定
            )
            
            logger.info(f"論文解析完了: {file_name}")
            return paper_metadata
            
        except Exception as e:
            logger.error(f"論文解析エラー: {e}")
            raise
    
    async def _extract_metadata(self, pdf_text: str) -> Dict:
        """論文からメタデータを抽出"""
        
        # テキストが長すぎる場合は最初の部分のみを使用
        text_to_analyze = pdf_text[:8000] if len(pdf_text) > 8000 else pdf_text
        
        prompt = f"""
以下の医学論文のテキストから、メタデータを抽出してJSON形式で出力してください。

論文テキスト:
{text_to_analyze}

抽出する項目:
- title: 論文タイトル（英語原文）
- authors: 著者名のリスト（姓名順、最大10名）
- publication_year: 発行年（YYYY形式）
- journal: 雑誌名
- volume: 巻号
- issue: 号数
- pages: ページ範囲（例: "123-130"）
- doi: DOI番号（あれば）
- keywords: キーワードのリスト（最大15個）
- abstract: 英語の抄録全文

JSON形式で出力してください。情報が見つからない場合はnullを設定してください。
著者名は "Last, First" 形式で抽出してください。

出力例:
{{
  "title": "Effects of...",
  "authors": ["Smith, John", "Johnson, Mary"],
  "publication_year": "2023",
  "journal": "Nature Medicine",
  "volume": "29",
  "issue": "3",
  "pages": "123-130",
  "doi": "10.1038/s41591-023-02345-6",
  "keywords": ["medicine", "treatment"],
  "abstract": "Background: ... Methods: ... Results: ... Conclusions: ..."
}}
"""
        
        try:
            response = await self._generate_with_retry(prompt)
            
            # JSONを抽出
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                metadata_json = json_match.group()
                metadata = json.loads(metadata_json)
                logger.info("メタデータ抽出成功")
                return metadata
            else:
                logger.warning("JSON形式のレスポンスが見つかりません")
                return {}
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析エラー: {e}")
            return {}
        except Exception as e:
            logger.error(f"メタデータ抽出エラー: {e}")
            return {}
    
    async def _create_japanese_summary(self, pdf_text: str) -> str:
        """日本語要約を作成"""
        
        # テキストが長すぎる場合は適切な長さに分割
        max_chunk_size = 12000
        if len(pdf_text) > max_chunk_size:
            # 重要な部分（抄録、結論など）を優先的に含める
            chunks = self._split_text_smart(pdf_text, max_chunk_size)
            text_to_summarize = chunks[0]  # 最初のチャンクを使用
        else:
            text_to_summarize = pdf_text
        
        prompt = f"""
以下の医学論文を日本語で要約してください。

論文テキスト:
{text_to_summarize}

要約要件:
- 文字数: 2000-3000文字
- 言語: 日本語
- 文体: 敬語・丁寧語
- 構成: 以下の項目を含めること
  1. 研究背景
  2. 目的
  3. 方法
  4. 結果
  5. 結論
  6. 意義
  7. 限界

論文全体の内容を包括的に要約し、抄録の単純な翻訳ではなく、
研究の意義や臨床的インパクトを含めた詳細な要約を作成してください。
医学専門用語は適切に日本語に翻訳してください。

要約:
"""
        
        try:
            summary = await self._generate_with_retry(prompt)
            
            # 不要なプレフィックスを除去
            summary = re.sub(r'^(要約[:：]?\s*)', '', summary, flags=re.IGNORECASE)
            summary = summary.strip()
            
            logger.info(f"日本語要約作成完了: {len(summary)}文字")
            return summary
            
        except Exception as e:
            logger.error(f"要約作成エラー: {e}")
            return "要約の作成に失敗しました。"
    
    def _split_text_smart(self, text: str, max_size: int) -> List[str]:
        """テキストを適切に分割"""
        
        # 重要なセクションを特定
        important_sections = [
            'abstract', 'summary', 'conclusion', 'results', 'discussion',
            'introduction', 'background', 'methods', 'methodology'
        ]
        
        chunks = []
        current_chunk = ""
        
        # 段落で分割
        paragraphs = text.split('\n\n')
        
        for paragraph in paragraphs:
            # 現在のチャンクに追加しても制限を超えない場合
            if len(current_chunk + paragraph) <= max_size:
                current_chunk += paragraph + '\n\n'
            else:
                # 現在のチャンクを保存
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # 新しいチャンクを開始
                if len(paragraph) <= max_size:
                    current_chunk = paragraph + '\n\n'
                else:
                    # 段落が長すぎる場合は分割
                    chunk_parts = [paragraph[i:i+max_size] for i in range(0, len(paragraph), max_size)]
                    chunks.extend(chunk_parts[:-1])
                    current_chunk = chunk_parts[-1] + '\n\n'
        
        # 最後のチャンクを追加
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    async def _generate_with_retry(self, prompt: str) -> str:
        """リトライ機能付きでテキスト生成"""
        
        for attempt in range(config.gemini.max_retries):
            try:
                response = self.model.generate_content(prompt)
                
                if response.text:
                    return response.text
                else:
                    raise ValueError("空のレスポンスが返されました")
                    
            except Exception as e:
                logger.warning(f"Gemini API呼び出し失敗 (試行 {attempt + 1}/{config.gemini.max_retries}): {e}")
                
                if attempt < config.gemini.max_retries - 1:
                    await asyncio.sleep(config.gemini.retry_delay * (attempt + 1))
                else:
                    raise
        
        raise Exception("Gemini API呼び出しが最大試行回数後も失敗しました")


# シングルトンインスタンス
gemini_service = GeminiService()