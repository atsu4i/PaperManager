"""
PubMed検索サービス
論文のPMIDを検索し、PubMedリンクを生成
"""

import asyncio
import re
import time
from typing import Optional, List, Dict, Any
from Bio import Entrez
import requests
from urllib.parse import quote

from ..config import config
from ..models.paper import PaperMetadata
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PubMedService:
    """PubMed検索クラス"""
    
    def __init__(self):
        # Entrezの設定
        if config.pubmed_email:
            Entrez.email = config.pubmed_email
        else:
            logger.warning("PubMed検索の推奨設定: メールアドレスが設定されていません")
        
        # API制限回避のための最後のリクエスト時刻
        self._last_request_time = 0
    
    async def search_pmid(self, paper: PaperMetadata) -> Optional[str]:
        """論文のPMIDを検索"""
        try:
            logger.info(f"PubMed検索開始: {paper.title[:50]}...")
            
            # 複数の検索戦略を試行
            search_strategies = [
                self._search_by_title_and_authors,
                self._search_by_title_and_journal,
                self._search_by_doi,
                self._search_by_title_only
            ]
            
            for strategy in search_strategies:
                pmid = await strategy(paper)
                if pmid:
                    logger.info(f"PMID検索成功: {pmid}")
                    return pmid
                    
                # API制限を避けるための待機
                await self._wait_for_rate_limit()
            
            logger.info("PMIDが見つかりませんでした")
            return None
            
        except Exception as e:
            logger.error(f"PubMed検索エラー: {e}")
            return None
    
    async def _search_by_title_and_authors(self, paper: PaperMetadata) -> Optional[str]:
        """タイトルと著者で検索"""
        if not paper.title or not paper.authors:
            return None
        
        try:
            # タイトルをクリーンアップ
            clean_title = self._clean_title(paper.title)
            
            # 最初の著者の姓を取得
            first_author = paper.authors[0] if paper.authors else ""
            author_lastname = first_author.split(',')[0].strip() if ',' in first_author else first_author.split()[0]
            
            # 検索クエリの構築
            query_parts = [f'"{clean_title}"[Title]']
            if author_lastname:
                query_parts.append(f'{author_lastname}[Author]')
            
            if paper.publication_year:
                query_parts.append(f'{paper.publication_year}[PDAT]')
            
            query = ' AND '.join(query_parts)
            logger.debug(f"検索クエリ (title+author): {query}")
            
            return await self._execute_search(query)
            
        except Exception as e:
            logger.warning(f"タイトル+著者検索エラー: {e}")
            return None
    
    async def _search_by_title_and_journal(self, paper: PaperMetadata) -> Optional[str]:
        """タイトルと雑誌名で検索"""
        if not paper.title or not paper.journal:
            return None
        
        try:
            clean_title = self._clean_title(paper.title)
            clean_journal = self._clean_journal_name(paper.journal)
            
            query_parts = [f'"{clean_title}"[Title]']
            if clean_journal:
                query_parts.append(f'"{clean_journal}"[Journal]')
            
            if paper.publication_year:
                query_parts.append(f'{paper.publication_year}[PDAT]')
            
            query = ' AND '.join(query_parts)
            logger.debug(f"検索クエリ (title+journal): {query}")
            
            return await self._execute_search(query)
            
        except Exception as e:
            logger.warning(f"タイトル+雑誌検索エラー: {e}")
            return None
    
    async def _search_by_doi(self, paper: PaperMetadata) -> Optional[str]:
        """DOIで検索"""
        if not paper.doi:
            return None
        
        try:
            # DOIをクリーンアップ
            clean_doi = paper.doi.strip()
            if clean_doi.startswith('http'):
                clean_doi = clean_doi.split('/')[-2] + '/' + clean_doi.split('/')[-1]
            
            query = f'"{clean_doi}"[AID]'
            logger.debug(f"検索クエリ (DOI): {query}")
            
            return await self._execute_search(query)
            
        except Exception as e:
            logger.warning(f"DOI検索エラー: {e}")
            return None
    
    async def _search_by_title_only(self, paper: PaperMetadata) -> Optional[str]:
        """タイトルのみで検索"""
        if not paper.title:
            return None
        
        try:
            clean_title = self._clean_title(paper.title)
            
            # タイトルが短すぎる場合は検索しない
            if len(clean_title) < 10:
                return None
            
            query = f'"{clean_title}"[Title]'
            if paper.publication_year:
                query += f' AND {paper.publication_year}[PDAT]'
            
            logger.debug(f"検索クエリ (title only): {query}")
            
            return await self._execute_search(query)
            
        except Exception as e:
            logger.warning(f"タイトル検索エラー: {e}")
            return None
    
    async def _execute_search(self, query: str) -> Optional[str]:
        """検索クエリを実行"""
        try:
            await self._wait_for_rate_limit()
            
            # 検索実行
            handle = Entrez.esearch(
                db="pubmed",
                term=query,
                retmax=config.pubmed.max_results,
                retmode="xml"
            )
            
            record = Entrez.read(handle)
            handle.close()
            
            # 結果の確認
            if record["Count"] == "0":
                return None
            
            # 最初の結果を取得
            id_list = record["IdList"]
            if not id_list:
                return None
            
            pmid = id_list[0]
            
            # 検索結果が複数ある場合は詳細確認
            if len(id_list) > 1:
                verified_pmid = await self._verify_search_result(pmid, query)
                return verified_pmid if verified_pmid else pmid
            
            return pmid
            
        except Exception as e:
            logger.warning(f"検索実行エラー: {e}")
            return None
    
    async def _verify_search_result(self, pmid: str, original_query: str) -> Optional[str]:
        """検索結果の妥当性を確認"""
        try:
            await self._wait_for_rate_limit()
            
            # 詳細情報を取得
            handle = Entrez.efetch(
                db="pubmed",
                id=pmid,
                retmode="xml"
            )
            
            records = Entrez.read(handle)
            handle.close()
            
            if not records["PubmedArticle"]:
                return None
            
            # 簡単な妥当性チェック（より詳細な検証も可能）
            article = records["PubmedArticle"][0]
            article_title = ""
            
            try:
                article_title = article["MedlineCitation"]["Article"]["ArticleTitle"]
            except KeyError:
                pass
            
            # タイトルの類似性チェック（簡易版）
            if article_title and len(article_title) > 10:
                return pmid
            
            return None
            
        except Exception as e:
            logger.warning(f"検索結果確認エラー: {e}")
            return pmid  # エラーの場合は元のPMIDを返す
    
    def _clean_title(self, title: str) -> str:
        """タイトルをクリーンアップ"""
        if not title:
            return ""
        
        # 特殊文字を除去
        cleaned = re.sub(r'[^\w\s\-\:\(\)]', ' ', title)
        
        # 複数の空白を単一に
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # 前後の空白を削除
        cleaned = cleaned.strip()
        
        # 長すぎる場合は切り詰め
        if len(cleaned) > 200:
            cleaned = cleaned[:200]
        
        return cleaned
    
    def _clean_journal_name(self, journal: str) -> str:
        """雑誌名をクリーンアップ"""
        if not journal:
            return ""
        
        # 一般的な雑誌名の短縮形を展開
        journal_mappings = {
            "J": "Journal",
            "Am": "American",
            "Br": "British",
            "Eur": "European",
            "Int": "International",
            "Med": "Medicine",
            "Sci": "Science"
        }
        
        cleaned = journal.strip()
        
        # 略語を展開（単語境界で）
        for abbrev, full in journal_mappings.items():
            pattern = r'\b' + re.escape(abbrev) + r'\b'
            cleaned = re.sub(pattern, full, cleaned, flags=re.IGNORECASE)
        
        return cleaned
    
    async def _wait_for_rate_limit(self):
        """API制限を避けるための待機"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < config.pubmed.request_delay:
            wait_time = config.pubmed.request_delay - time_since_last
            await asyncio.sleep(wait_time)
        
        self._last_request_time = time.time()
    
    @staticmethod
    def create_pubmed_url(pmid: str) -> str:
        """PMIDからPubMed URLを生成"""
        if not pmid:
            return ""
        return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"


# シングルトンインスタンス
pubmed_service = PubMedService()