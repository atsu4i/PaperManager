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

        # メタデータ抽出用モデル
        self.metadata_model = genai.GenerativeModel(
            model_name=config.gemini.metadata_model,
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

        # 要約作成用モデル
        self.summary_model = genai.GenerativeModel(
            model_name=config.gemini.summary_model,
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

        # 後方互換性のため残す
        self.model = self.metadata_model

        # 使用中のモデルをログ出力
        logger.info(f"Gemini Service初期化完了")
        logger.info(f"  メタデータ抽出用モデル: {config.gemini.metadata_model}")
        logger.info(f"  要約作成用モデル: {config.gemini.summary_model}")
    
    async def analyze_paper(self, pdf_text: str, file_name: str) -> PaperMetadata:
        """論文の解析とメタデータ抽出（後方互換性のため残す）"""
        try:
            logger.info(f"論文解析開始: {file_name}")

            # メタデータ抽出
            metadata = await self._extract_metadata(pdf_text)

            # 日本語要約作成
            japanese_summary = await self._create_japanese_summary(pdf_text)

            # PaperMetadataオブジェクトの作成
            paper_metadata = self._create_paper_metadata(metadata, japanese_summary, pdf_text, file_name)

            logger.info(f"論文解析完了: {file_name}")
            return paper_metadata

        except Exception as e:
            logger.error(f"論文解析エラー: {e}")
            raise

    async def extract_metadata_only(self, pdf_text: str, file_name: str) -> PaperMetadata:
        """メタデータのみを抽出（要約なし）"""
        try:
            logger.info(f"メタデータ抽出開始: {file_name}")

            # メタデータ抽出
            metadata = await self._extract_metadata(pdf_text)

            # 要約なしでPaperMetadataオブジェクトを作成
            paper_metadata = self._create_paper_metadata(
                metadata,
                "", # 要約は空
                pdf_text,
                file_name
            )

            logger.info(f"メタデータ抽出完了: {file_name}")
            return paper_metadata

        except Exception as e:
            logger.error(f"メタデータ抽出エラー: {e}")
            raise

    async def add_summary_to_metadata(self, paper_metadata: PaperMetadata, pdf_text: str) -> PaperMetadata:
        """既存のメタデータに日本語要約を追加"""
        try:
            logger.info(f"要約作成開始: {paper_metadata.title[:50]}...")

            # 日本語要約作成
            japanese_summary = await self._create_japanese_summary(pdf_text)

            # 要約を追加
            paper_metadata.summary_japanese = japanese_summary

            logger.info(f"要約作成完了: {len(japanese_summary)}文字")
            return paper_metadata

        except Exception as e:
            logger.error(f"要約作成エラー: {e}")
            raise

    def _create_paper_metadata(self, metadata: Dict, japanese_summary: str,
                               pdf_text: str, file_name: str) -> PaperMetadata:
        """メタデータ辞書からPaperMetadataオブジェクトを作成"""
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
        return PaperMetadata(
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
            # メタデータ抽出用モデルを使用
            response = await self._generate_with_retry(prompt, model=self.metadata_model)
            
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
あなたは医学論文の専門要約者である。以下の論文を段階的に理解し、高品質な日本語要約を作成せよ。

【論文テキスト】
{text_to_summarize}

【タスク：段階的に実行】
ステップ1: 論文全体を読み、研究の目的・方法・結果・結論を把握する
ステップ2: 重要な数値データ（対象者数、p値、効果量等）を抽出する
ステップ3: 以下の厳格な要件に従って日本語要約を作成する

【厳格な出力要件】
1. **文字数**: 1800-1900文字（必ず守る）
2. **文体**: 常体（である調、だ調）を使用。「です・ます調」は禁止
3. **構成**: 必ず以下の要素を含める
   - 研究背景（2-3文）：なぜこの研究が必要か
   - 目的（1-2文）：何を明らかにするか
   - 方法（3-4文）：対象者数、研究デザイン、評価指標
   - 結果（4-6文）：主要な発見と統計データ（p値、効果量を必ず記載）
   - 結論（2-3文）：何が示されたか
   - 意義（2-3文）：臨床的・学術的価値
   - 限界（1-2文）：研究の制約や今後の課題
4. **データの明記**: 以下を必ず含める
   - 対象者数（n=XX）
   - 統計的有意性（p値、信頼区間等）
   - 主要評価項目の具体的数値
   - 研究デザイン（RCT、コホート研究等）

【医学論文特有の注意点】
- 医学専門用語は正確な日本語を使用（例：RCT→ランダム化比較試験）
- 略語は初出時にフル表記を併記（例：HSCT（造血幹細胞移植））
- 統計結果は必ず数値とp値をセットで記載（例：有意に減少した（p=0.004））
- 臨床的意義と研究の限界を必ず明記する
- 論文全体の包括的要約を作成（抄録の単純翻訳ではない）

【出力形式】
- プレフィックス・ヘッダー・説明文は一切不要
- 要約内容のみを直接出力
- 段落分けは自然に行う（改行で区切る）

【良い出力例の文体】
○「本研究では、HSCTを受ける患者21名（介入群11名、対照群10名）を対象に、ペット型ロボットの効果を検証した。」
○「介入群では、ストレスマーカーであるCgA濃度が有意に減少した（p=0.004）。」
○「この知見は、免疫不全患者への安全な精神ケア手段を提供する点で臨床的意義が大きい。」
○「ただし、本研究はサンプルサイズが小さく、今後大規模研究での検証が必要である。」

【悪い出力例】
×「本研究では...を検証しました。」（です・ます調）
×「ストレスが減少した。」（数値データなし）
×「有効性が示された。」（具体性に欠ける）
×（研究の限界に言及なし）

要約を直接出力せよ：
"""

        try:
            # 要約作成用モデルを使用
            summary = await self._generate_with_retry(prompt, model=self.summary_model)
            
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
    
    async def _generate_with_retry(self, prompt: str, model=None) -> str:
        """リトライ機能付きでテキスト生成（レート制限対応強化版）

        Args:
            prompt: プロンプトテキスト
            model: 使用するモデル（Noneの場合はself.modelを使用）
        """
        # モデルが指定されていない場合はデフォルトモデルを使用
        if model is None:
            model = self.model

        for attempt in range(config.gemini.max_retries):
            try:
                response = model.generate_content(prompt)

                if response.text:
                    return response.text
                else:
                    raise ValueError("空のレスポンスが返されました")

            except Exception as e:
                error_message = str(e).lower()
                is_rate_limit_error = (
                    'resource exhausted' in error_message or
                    'rate limit' in error_message or
                    '429' in error_message or
                    'quota' in error_message
                )

                if is_rate_limit_error:
                    # レート制限エラーの場合は長めの待機時間
                    wait_time = config.gemini.retry_delay * (2 ** attempt) * 2  # エクスポネンシャルバックオフ × 2
                    logger.warning(
                        f"Gemini APIレート制限検出 (試行 {attempt + 1}/{config.gemini.max_retries}): "
                        f"{wait_time}秒待機します..."
                    )
                else:
                    # 通常のエラーの場合
                    wait_time = config.gemini.retry_delay * (attempt + 1)
                    logger.warning(
                        f"Gemini API呼び出し失敗 (試行 {attempt + 1}/{config.gemini.max_retries}): {e}"
                    )

                if attempt < config.gemini.max_retries - 1:
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Gemini API呼び出しが最大試行回数後も失敗: {e}")
                    raise

        raise Exception("Gemini API呼び出しが最大試行回数後も失敗しました")


# シングルトンインスタンス
gemini_service = GeminiService()