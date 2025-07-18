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
            
            # 複数の検索戦略を試行（確実性の高い順）
            search_strategies = [
                # 戦略1: 短縮タイトル + 著者（最も確実）
                self._try_short_title_with_authors,
                # 戦略2: 緩い条件での検索（年なし）
                self._try_flexible_search,
                # 戦略3: 部分タイトル + 主要著者 + 年
                self._try_partial_title_with_first_author,
                # 戦略4: 完全タイトル + 複数著者 + 年（長いタイトルでは失敗しやすい）
                self._try_exact_title_with_multiple_authors,
                # 戦略5: キーワード検索 + 著者（最後の手段、誤検出リスク高）
                self._try_keyword_search_with_authors
            ]
            
            for strategy in search_strategies:
                pmid = await strategy(paper, clean_title)
                if pmid:
                    return pmid
                    
                # 戦略間の待機
                await self._wait_for_rate_limit()
            
            return None
            
        except Exception as e:
            logger.warning(f"タイトル+著者検索エラー: {e}")
            return None
    
    async def _try_short_title_with_authors(self, paper: PaperMetadata, clean_title: str) -> Optional[str]:
        """戦略1: 短縮タイトル + 著者（最も確実）"""
        try:
            if not paper.authors:
                return None
                
            # タイトルから最初の重要な部分を抽出（最初の10単語または最初のコロンまで）
            title_words = clean_title.split()
            
            # コロンがある場合はコロンまで、なければ最初の10単語
            if ':' in clean_title:
                short_title = clean_title.split(':')[0].strip()
            else:
                short_title = ' '.join(title_words[:10])
            
            # さらに短縮（特殊なケース）
            if len(short_title) > 50:
                # 最初の3-5単語程度に短縮
                key_words = short_title.split()[:5]
                short_title = ' '.join(key_words)
            
            author_lastname = self._extract_author_lastname(paper.authors[0])
            if not author_lastname:
                return None
            
            query_parts = [f'"{short_title}"[Title]']
            query_parts.append(f'{author_lastname}[Author]')
            
            if paper.publication_year:
                query_parts.append(f'{paper.publication_year}[PDAT]')
            
            query = ' AND '.join(query_parts)
            logger.info(f"検索戦略1 (短縮タイトル): {query}")
            
            pmid = await self._execute_search(query)
            if pmid:
                logger.info(f"成功: 戦略1でPMID発見: {pmid}")
                return pmid
            
            return None
            
        except Exception as e:
            logger.warning(f"戦略1エラー: {e}")
            return None
    
    async def _try_exact_title_with_multiple_authors(self, paper: PaperMetadata, clean_title: str) -> Optional[str]:
        """戦略4: 完全タイトルと複数著者での検索"""
        try:
            # 上位5人の著者を試行
            for i, author in enumerate(paper.authors[:5]):
                author_lastname = self._extract_author_lastname(author)
                if not author_lastname:
                    continue
                
                query_parts = [f'"{clean_title}"[Title]']
                query_parts.append(f'{author_lastname}[Author]')
                
                if paper.publication_year:
                    query_parts.append(f'{paper.publication_year}[PDAT]')
                
                query = ' AND '.join(query_parts)
                logger.info(f"検索戦略4 (著者{i+1}): {query}")
                
                pmid = await self._execute_search(query)
                if pmid:
                    logger.info(f"成功: 戦略4で著者{i+1}番目でPMID発見: {pmid}")
                    return pmid
                
                if i < 4:  # 最後以外は短時間待機
                    await asyncio.sleep(0.5)
            
            return None
            
        except Exception as e:
            logger.warning(f"戦略4エラー: {e}")
            return None
    
    async def _try_partial_title_with_first_author(self, paper: PaperMetadata, clean_title: str) -> Optional[str]:
        """戦略3: 部分タイトルと主要著者での検索"""
        try:
            if not paper.authors:
                return None
                
            author_lastname = self._extract_author_lastname(paper.authors[0])
            if not author_lastname:
                return None
            
            # タイトルを部分的に使用（最初の10単語程度）
            title_words = clean_title.split()[:10]
            partial_title = ' '.join(title_words)
            
            query_parts = [f'"{partial_title}"[Title]']
            query_parts.append(f'{author_lastname}[Author]')
            
            if paper.publication_year:
                query_parts.append(f'{paper.publication_year}[PDAT]')
            
            query = ' AND '.join(query_parts)
            logger.info(f"検索戦略3 (部分タイトル): {query}")
            
            pmid = await self._execute_search(query)
            if pmid:
                logger.info(f"成功: 戦略3でPMID発見: {pmid}")
                return pmid
            
            return None
            
        except Exception as e:
            logger.warning(f"戦略3エラー: {e}")
            return None
    
    async def _try_keyword_search_with_authors(self, paper: PaperMetadata, clean_title: str) -> Optional[str]:
        """戦略5: キーワード検索と著者での検索"""
        try:
            if not paper.authors:
                return None
                
            author_lastname = self._extract_author_lastname(paper.authors[0])
            if not author_lastname:
                return None
            
            # タイトルから重要なキーワードを抽出（3-5単語程度）
            keywords = self._extract_important_keywords(clean_title)
            if not keywords:
                return None
            
            # キーワードをORで結合
            keyword_query = ' OR '.join([f'"{kw}"' for kw in keywords])
            
            query_parts = [f'({keyword_query})']
            query_parts.append(f'{author_lastname}[Author]')
            
            if paper.publication_year:
                query_parts.append(f'{paper.publication_year}[PDAT]')
            
            query = ' AND '.join(query_parts)
            logger.info(f"検索戦略5 (キーワード): {query}")
            
            pmid = await self._execute_search(query)
            if pmid:
                logger.info(f"成功: 戦略5でPMID発見: {pmid}")
                return pmid
            
            return None
            
        except Exception as e:
            logger.warning(f"戦略5エラー: {e}")
            return None
    
    async def _try_flexible_search(self, paper: PaperMetadata, clean_title: str) -> Optional[str]:
        """戦略2: 緩い条件での検索"""
        try:
            if not paper.authors:
                return None
                
            author_lastname = self._extract_author_lastname(paper.authors[0])
            if not author_lastname:
                return None
            
            # 年なしでの検索
            query_parts = [f'"{clean_title}"']
            query_parts.append(f'{author_lastname}[Author]')
            
            query = ' AND '.join(query_parts)
            logger.info(f"検索戦略2 (緩い条件): {query}")
            
            pmid = await self._execute_search(query)
            if pmid:
                logger.info(f"成功: 戦略2でPMID発見: {pmid}")
                return pmid
            
            return None
            
        except Exception as e:
            logger.warning(f"戦略2エラー: {e}")
            return None
    
    def _extract_author_lastname(self, author: str) -> str:
        """著者から姓を抽出"""
        if not author:
            return ""
        
        # "Last, First" 形式の場合
        if ',' in author:
            lastname = author.split(',')[0].strip()
        else:
            # "First Last" 形式の場合は最後の単語を使用
            parts = author.strip().split()
            lastname = parts[-1] if parts else ""
        
        # 特殊文字を除去
        lastname = re.sub(r'[^A-Za-z\s\-]', '', lastname).strip()
        
        return lastname
    
    def _extract_important_keywords(self, title: str) -> List[str]:
        """タイトルから重要なキーワードを抽出"""
        if not title:
            return []
        
        # 一般的なストップワードを除去
        stop_words = {
            'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
            'between', 'among', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can',
            'study', 'analysis', 'research', 'investigation', 'effect', 'effects', 'role', 'impact'
        }
        
        words = title.lower().split()
        keywords = []
        
        for word in words:
            # 特殊文字を除去
            clean_word = re.sub(r'[^a-z0-9]', '', word)
            
            # 3文字以上で、ストップワードでない単語を抽出
            if len(clean_word) >= 3 and clean_word not in stop_words:
                keywords.append(clean_word)
        
        # 最大5個のキーワードを返す
        return keywords[:5]
    
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
        """タイトルをクリーンアップ（医学論文に適した保守的なクリーニング）"""
        if not title:
            return ""
        
        # より保守的なクリーニング：医学用語や特殊文字を保持
        # 削除対象：明らかに不要な文字のみ
        cleaned = re.sub(r'["\[\]{}|\\<>]', '', title)  # 引用符や括弧の一部のみ除去
        
        # 複数の空白を単一に
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # 前後の空白を削除
        cleaned = cleaned.strip()
        
        # 長すぎる場合は単語境界で切り詰め
        if len(cleaned) > 200:
            words = cleaned.split()
            truncated = []
            char_count = 0
            
            for word in words:
                if char_count + len(word) + 1 <= 200:  # +1 for space
                    truncated.append(word)
                    char_count += len(word) + 1
                else:
                    break
            
            cleaned = ' '.join(truncated)
        
        logger.debug(f"タイトルクリーニング: '{title}' → '{cleaned}'")
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
    
    async def fetch_metadata_from_pubmed(self, pmid: str) -> Optional[Dict]:
        """PMIDからPubMedメタデータを取得"""
        if not pmid:
            return None
        
        try:
            logger.info(f"PubMedメタデータ取得開始: PMID {pmid}")
            
            # API制限回避
            await self._wait_for_rate_limit()
            
            # efetch APIを使用してメタデータを取得
            handle = Entrez.efetch(
                db="pubmed",
                id=pmid,
                retmode="xml",
                rettype="abstract"
            )
            
            records = Entrez.read(handle)
            handle.close()
            
            if not records or not records.get("PubmedArticle"):
                logger.warning(f"PubMedメタデータが見つかりません: PMID {pmid}")
                return None
            
            article = records["PubmedArticle"][0]
            medline_citation = article["MedlineCitation"]
            article_info = medline_citation["Article"]
            
            # メタデータを抽出
            metadata = self._extract_metadata_from_article(article_info, medline_citation)
            metadata["pmid"] = pmid
            
            logger.info(f"PubMedメタデータ取得完了: {metadata.get('title', 'N/A')[:50]}...")
            return metadata
            
        except Exception as e:
            logger.error(f"PubMedメタデータ取得エラー (PMID: {pmid}): {e}")
            return None
    
    def _extract_metadata_from_article(self, article_info: Dict, medline_citation: Dict) -> Dict:
        """PubMed記事からメタデータを抽出"""
        metadata = {}
        
        try:
            # タイトル
            title = article_info.get("ArticleTitle", "")
            if isinstance(title, str):
                metadata["title"] = title.strip()
            elif hasattr(title, 'strip'):
                metadata["title"] = str(title).strip()
            else:
                metadata["title"] = ""
            
            # 著者情報
            authors = []
            author_list = article_info.get("AuthorList", [])
            for author in author_list:
                if isinstance(author, dict):
                    last_name = author.get("LastName", "")
                    first_name = author.get("ForeName", "")
                    initials = author.get("Initials", "")
                    
                    if last_name:
                        # "LastName, FirstName" 形式
                        if first_name:
                            full_name = f"{last_name}, {first_name}"
                        elif initials:
                            full_name = f"{last_name}, {initials}"
                        else:
                            full_name = last_name
                        authors.append(full_name)
            
            metadata["authors"] = authors
            
            # 雑誌情報
            journal = article_info.get("Journal", {})
            if isinstance(journal, dict):
                journal_title = journal.get("Title", "")
                if not journal_title:
                    journal_title = journal.get("ISOAbbreviation", "")
                metadata["journal"] = journal_title
            
            # 発行年
            pub_date = article_info.get("ArticleDate", [])
            if not pub_date:
                journal_issue = journal.get("JournalIssue", {})
                pub_date = journal_issue.get("PubDate", {})
            
            year = ""
            if isinstance(pub_date, list) and pub_date:
                year = pub_date[0].get("Year", "")
            elif isinstance(pub_date, dict):
                year = pub_date.get("Year", "")
            
            metadata["publication_year"] = str(year) if year else ""
            
            # DOI
            doi = ""
            article_id_list = article_info.get("ELocationID", [])
            for article_id in article_id_list:
                if isinstance(article_id, dict) and article_id.get("EIdType") == "doi":
                    doi = article_id.get("content", "")
                    break
            
            metadata["doi"] = doi
            
            # 抄録
            abstract = ""
            abstract_text = article_info.get("Abstract", {})
            if isinstance(abstract_text, dict):
                abstract_parts = abstract_text.get("AbstractText", [])
                if isinstance(abstract_parts, list):
                    abstract = " ".join([str(part) for part in abstract_parts])
                else:
                    abstract = str(abstract_parts)
            
            metadata["abstract"] = abstract.strip()
            
            # キーワード・MeSH用語
            keywords = []
            mesh_headings = medline_citation.get("MeshHeadingList", [])
            for mesh in mesh_headings:
                if isinstance(mesh, dict):
                    descriptor = mesh.get("DescriptorName", "")
                    if descriptor:
                        keywords.append(str(descriptor))
            
            metadata["keywords"] = keywords
            
            logger.debug(f"抽出されたメタデータ: タイトル={metadata.get('title', 'N/A')[:50]}..., 著者数={len(metadata.get('authors', []))}, 雑誌={metadata.get('journal', 'N/A')}")
            
        except Exception as e:
            logger.error(f"メタデータ抽出エラー: {e}")
        
        return metadata


# シングルトンインスタンス
pubmed_service = PubMedService()