"""
OpenAlex API Service

OpenAlex APIを使って論文の被引用数などのメタデータを取得するサービス
"""

import requests
from typing import Optional, Dict, Any
import time
from app.utils.logger import get_logger
from app.config import config

logger = get_logger(__name__)


class OpenAlexService:
    """OpenAlex API連携サービス"""

    def __init__(self):
        self.base_url = "https://api.openalex.org"
        # Polite poolアクセス（推奨）: メールアドレスを含めるとrate limitが緩和される
        self.email = config.pubmed_email if hasattr(config, 'pubmed_email') else None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PaperManager/1.9.0 (mailto:{})'.format(self.email or 'noreply@example.com')
        })

    def get_work_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        DOIから論文情報を取得

        Args:
            doi: DOI (例: "10.1038/s41586-020-2649-2")

        Returns:
            論文情報の辞書、見つからない場合はNone
        """
        if not doi:
            return None

        try:
            # DOIの正規化（URLプレフィックスを除去）
            doi_clean = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")

            # OpenAlex APIエンドポイント
            url = f"{self.base_url}/works/https://doi.org/{doi_clean}"

            # Polite poolパラメータ追加
            params = {}
            if self.email:
                params['mailto'] = self.email

            logger.info(f"Fetching OpenAlex data for DOI: {doi_clean}")
            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"Successfully fetched OpenAlex data for DOI: {doi_clean}")
                return data
            elif response.status_code == 404:
                logger.warning(f"DOI not found in OpenAlex: {doi_clean}")
                return None
            else:
                logger.error(f"OpenAlex API error: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"OpenAlex API timeout for DOI: {doi}")
            return None
        except Exception as e:
            logger.error(f"Error fetching OpenAlex data: {e}")
            return None

    def get_work_by_title(self, title: str, max_results: int = 5) -> Optional[Dict[str, Any]]:
        """
        タイトルから論文情報を検索

        Args:
            title: 論文タイトル
            max_results: 最大検索結果数

        Returns:
            最も一致度が高い論文情報、見つからない場合はNone
        """
        if not title or len(title) < 10:
            return None

        try:
            url = f"{self.base_url}/works"

            params = {
                'filter': f'title.search:{title}',
                'per-page': max_results
            }

            if self.email:
                params['mailto'] = self.email

            logger.info(f"Searching OpenAlex by title: {title[:50]}...")
            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])

                if results:
                    # 最初の結果を返す（最も関連性が高い）
                    logger.info(f"Found {len(results)} results, using top match")
                    return results[0]
                else:
                    logger.warning(f"No results found for title: {title[:50]}")
                    return None
            else:
                logger.error(f"OpenAlex API error: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"OpenAlex API timeout for title search")
            return None
        except Exception as e:
            logger.error(f"Error searching OpenAlex by title: {e}")
            return None

    def get_citation_count(self, doi: Optional[str] = None, title: Optional[str] = None) -> Optional[int]:
        """
        被引用数を取得

        Args:
            doi: DOI（優先）
            title: タイトル（DOIがない場合のフォールバック）

        Returns:
            被引用数、取得できない場合はNone
        """
        work_data = None

        # DOIで検索（優先）
        if doi:
            work_data = self.get_work_by_doi(doi)
            # API rate limitを考慮して少し待機
            time.sleep(0.1)

        # DOIで見つからない場合、タイトルで検索
        if not work_data and title:
            work_data = self.get_work_by_title(title)
            time.sleep(0.1)

        if work_data:
            cited_by_count = work_data.get('cited_by_count', 0)
            logger.info(f"Citation count: {cited_by_count}")
            return cited_by_count

        return None

    def get_paper_metadata(self, doi: Optional[str] = None, title: Optional[str] = None) -> Dict[str, Any]:
        """
        論文の詳細メタデータを取得

        Args:
            doi: DOI
            title: タイトル

        Returns:
            メタデータ辞書 {
                'cited_by_count': int,
                'publication_date': str,
                'publication_year': int,
                'title': str,
                'authors': List[str],
                'journal': str,
                'doi': str,
                'open_access': bool,
                'openalex_id': str,
                ...
            }
        """
        work_data = None

        # DOIで検索（優先）
        if doi:
            work_data = self.get_work_by_doi(doi)
            time.sleep(0.1)

        # DOIで見つからない場合、タイトルで検索
        if not work_data and title:
            work_data = self.get_work_by_title(title)
            time.sleep(0.1)

        if not work_data:
            return {
                'cited_by_count': None,
                'publication_date': None,
                'publication_year': None,
                'title': None,
                'authors': None,
                'journal': None,
                'doi': None,
                'open_access': None,
                'openalex_id': None
            }

        # メタデータ抽出
        metadata = {
            'cited_by_count': work_data.get('cited_by_count', 0),
            'publication_date': work_data.get('publication_date'),
            'open_access': work_data.get('open_access', {}).get('is_oa', False),
            'openalex_id': work_data.get('id'),
            'openalex_url': f"https://openalex.org/{work_data.get('id', '').split('/')[-1]}" if work_data.get('id') else None
        }

        # タイトル
        if work_data.get('title'):
            metadata['title'] = work_data['title']

        # DOI（正規化）
        if work_data.get('doi'):
            doi_url = work_data['doi']
            metadata['doi'] = doi_url.replace('https://doi.org/', '')

        # 出版年
        pub_date = work_data.get('publication_date')
        if pub_date:
            try:
                metadata['publication_year'] = int(pub_date.split('-')[0])
            except (ValueError, IndexError):
                metadata['publication_year'] = None
        else:
            metadata['publication_year'] = work_data.get('publication_year')

        # 著者リスト（"姓, 名" 形式）
        authorships = work_data.get('authorships', [])
        if authorships:
            authors = []
            for authorship in authorships[:20]:  # 最大20名
                author = authorship.get('author', {})
                author_name = author.get('display_name')
                if author_name:
                    authors.append(author_name)
            metadata['authors'] = authors
        else:
            metadata['authors'] = None

        # 雑誌名
        primary_location = work_data.get('primary_location', {})
        if primary_location:
            source = primary_location.get('source', {})
            if source:
                metadata['journal'] = source.get('display_name')
            else:
                metadata['journal'] = None
        else:
            metadata['journal'] = None

        logger.info(f"Retrieved OpenAlex metadata: citations={metadata['cited_by_count']}, "
                   f"title={metadata.get('title', 'N/A')[:50]}, "
                   f"authors={len(metadata.get('authors', [])) if metadata.get('authors') else 0}, "
                   f"journal={metadata.get('journal', 'N/A')}")
        return metadata


# シングルトンインスタンス
openalex_service = OpenAlexService()
