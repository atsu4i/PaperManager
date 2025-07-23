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
            
            # データの安全なクリーニング
            def safe_get_list(data, key, default=None):
                """リスト型フィールドを安全に取得"""
                value = data.get(key, default)
                if value is None:
                    return []
                if isinstance(value, list):
                    return value
                if isinstance(value, str):
                    return [value]
                return []
            
            def safe_get_str(data, key, default=''):
                """文字列型フィールドを安全に取得"""
                value = data.get(key, default)
                return str(value) if value is not None else default
            
            # PaperMetadataオブジェクトの作成
            paper_metadata = PaperMetadata(
                title=safe_get_str(metadata, 'title'),
                authors=safe_get_list(metadata, 'authors'),
                publication_year=safe_get_str(metadata, 'publication_year') or None,
                journal=safe_get_str(metadata, 'journal') or None,
                volume=safe_get_str(metadata, 'volume') or None,
                issue=safe_get_str(metadata, 'issue') or None,
                pages=safe_get_str(metadata, 'pages') or None,
                doi=safe_get_str(metadata, 'doi') or None,
                keywords=safe_get_list(metadata, 'keywords'),
                abstract=safe_get_str(metadata, 'abstract') or None,
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
- keywords: キーワードのリスト（論文の主要概念、手法、分野、対象を含む最大20個、英語で。複数形を優先し、ハイフン区切りで表記。例: "large-language-models", "electronic-health-records", "natural-language-processing"）
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
  "keywords": ["electronic-health-records", "functional-limitations", "geriatrics", "healthcare-data", "activities-of-daily-living", "instrumental-activities-of-daily-living", "mobility-assessments", "aging-research", "clinical-documentation"],
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
以下の医学論文を日本語で要約する。厳密に要求される形式と文字数制限を守ること。

論文テキスト:
{text_to_summarize}

【厳格な要求事項】
1. 出力文字数：1900文字以内（厳守）
2. 文体：常体（である調、だ調）のみ使用
3. 構成：背景・目的・方法・結果・結論・意義を含む
4. 出力形式：要約内容のみ（プレフィックス、ヘッダー、説明文は一切不要）
5. 簡潔性：「です・ます調」は禁止、冗長表現を避ける

【出力例の文体】
○「この研究では...を検討した」「...であることが判明した」「...は重要である」
×「この研究では...を検討しました」「...であることが判明しました」「...は重要です」

【注意】
- 文字数を常に意識し、1900文字を超えないよう調整する
- 論文の抄録の翻訳ではなく、論文全体の包括的要約を作成する
- 医学専門用語は適切な日本語を使用する
- 研究の臨床的意義と限界を必ず含める

要約内容を直接出力せよ：
"""
        
        try:
            summary = await self._generate_with_retry(prompt)
            
            # 包括的なプレフィックス・サフィックス除去
            summary = self._clean_summary_output(summary)
            
            # 文字数確認とログ
            char_count = len(summary)
            logger.info(f"日本語要約作成完了: {char_count}文字")
            
            # 1900文字を超えている場合の警告
            if char_count > 1900:
                logger.warning(f"要約が制限を超過: {char_count}文字 > 1900文字")
                # 文の境界で切り詰め
                summary = self._truncate_at_sentence_boundary(summary, 1900)
                logger.info(f"要約を切り詰め: {len(summary)}文字")
            
            return summary
            
        except Exception as e:
            logger.error(f"要約作成エラー: {e}")
            return "要約の作成に失敗した。"
    
    def _clean_summary_output(self, text: str) -> str:
        """要約出力から不要なプレフィックス・サフィックスを除去"""
        if not text:
            return text
        
        # 一般的なプレフィックスパターンを除去
        prefixes_to_remove = [
            r'^要約[:：]?\s*',
            r'^以下.*要約.*[:：]\s*',
            r'^.*要約内容.*[:：]\s*',
            r'^この論文.*要約.*[:：]\s*',
            r'^【要約】\s*',
            r'^\*\*要約\*\*\s*',
            r'^要約を以下に.*[:：]\s*',
            r'^医学論文.*要約.*[:：]\s*'
        ]
        
        for pattern in prefixes_to_remove:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
        
        # 一般的なサフィックスパターンを除去
        suffixes_to_remove = [
            r'\s*以上が要約.*$',
            r'\s*これで要約.*$',
            r'\s*要約は以上.*$',
            r'\s*\(.*文字.*\)$'
        ]
        
        for pattern in suffixes_to_remove:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
        
        # 前後の空白・改行を除去
        text = text.strip()
        
        # 複数の改行を単一に
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text
    
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