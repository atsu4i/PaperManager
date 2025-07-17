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
    
    # ファイル情報
    file_path: str
    file_name: str
    file_size: int
    processed_at: datetime = Field(default_factory=datetime.now)


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
    
    # 著者情報をmulti_select形式に変換
    authors_multi_select = [{"name": author} for author in paper.authors[:10]]  # 最大10人まで
    
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
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": paper.summary_japanese
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