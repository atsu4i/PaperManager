"""
論文データモデル
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class Author(BaseModel):
    """著者情報"""
    name: str
    affiliation: Optional[str] = None


class PaperMetadata(BaseModel):
    """論文メタデータ"""
    title: str
    authors: List[str] = Field(default_factory=list)
    publication_year: Optional[str] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    pmid: Optional[str] = None
    pubmed_url: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    abstract: Optional[str] = None
    summary_japanese: Optional[str] = None
    full_text: Optional[str] = None
    additional_info: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    # ファイル情報
    file_path: str
    file_name: str
    file_size: int
    processed_at: datetime = Field(default_factory=datetime.now)
    
    @property
    def summary(self) -> Optional[str]:
        """要約のエイリアス（ObsidianService互換性のため）"""
        return self.summary_japanese
    
    @property  
    def year(self) -> Optional[int]:
        """年のエイリアス（互換性のため）"""
        if self.publication_year:
            try:
                return int(self.publication_year)
            except (ValueError, TypeError):
                return None
        return None


class NotionPage(BaseModel):
    """Notion投稿用データ"""
    parent: Dict[str, str]
    properties: Dict[str, Any]
    children: List[Dict[str, Any]] = Field(default_factory=list)


class ProcessingResult(BaseModel):
    """処理結果"""
    success: bool
    paper_metadata: Optional[PaperMetadata] = None
    notion_page_id: Optional[str] = None
    error_message: Optional[str] = None
    processing_time: float = 0.0


def create_notion_page_data(paper: PaperMetadata, database_id: str) -> NotionPage:
    """論文データからNotion投稿用データを作成"""
    
    # 著者情報をmulti_select形式に変換（カンマ除去）
    authors_multi_select = []
    for author in paper.authors[:10]:  # 最大10人まで
        # カンマを除去してクリーニング
        clean_name = author.replace(',', ' ').strip()
        clean_name = ' '.join(clean_name.split())  # 複数スペースを単一に
        if clean_name and len(clean_name) > 1:
            authors_multi_select.append({"name": clean_name[:100]})
    
    # キーワードをmulti_select形式に変換
    keywords_multi_select = [{"name": keyword} for keyword in paper.keywords[:20]]  # 最大20個まで
    
    # DOI URLの作成
    doi_url = f"https://doi.org/{paper.doi}" if paper.doi else None
    
    # プロパティの構築
    properties = {
        "Title": {
            "title": [{"text": {"content": paper.title}}]
        },
        "Authors": {
            "multi_select": authors_multi_select
        },
        "Year": {
            "select": {"name": paper.publication_year} if paper.publication_year else None
        },
        "Journal": {
            "select": {"name": paper.journal} if paper.journal else None
        },
        "Volume": {
            "rich_text": [{"text": {"content": paper.volume}}] if paper.volume else []
        },
        "Issue": {
            "rich_text": [{"text": {"content": paper.issue}}] if paper.issue else []
        },
        "Pages": {
            "rich_text": [{"text": {"content": paper.pages}}] if paper.pages else []
        },
        "DOI": {
            "url": doi_url
        },
        "PubMed": {
            "url": paper.pubmed_url
        },
        "Key Words": {
            "multi_select": keywords_multi_select
        }
    }
    
    # Noneの値を除去
    properties = {k: v for k, v in properties.items() if v is not None}
    
    # 要約をchildren（本文）として追加
    children = []
    if paper.summary_japanese:
        # 要約の長さを制限（Notionの2000文字制限、安全マージン含め1900文字）
        summary_content = _truncate_at_sentence_boundary(paper.summary_japanese, 1900)
        
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": summary_content
                        }
                    }
                ]
            }
        })
    
    return NotionPage(
        parent={"database_id": database_id},
        properties=properties,
        children=children
    )


def _truncate_at_sentence_boundary(text: str, max_length: int) -> str:
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