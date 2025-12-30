#!/usr/bin/env python3
"""
既存論文の被引用数一括更新スクリプト

NotionとChromaDBに登録されている既存の論文に対して、
OpenAlex APIから被引用数を取得して更新します。

使用方法:
    python update_citations.py                    # 全論文を更新
    python update_citations.py --limit 10         # 最大10件まで
    python update_citations.py --dry-run          # 実行前の確認のみ
    python update_citations.py --force            # 既に被引用数があっても再取得
"""

import asyncio
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.config import config
from app.services.notion_service import notion_service
from app.services.chromadb_service import chromadb_service
from app.services.openalex_service import openalex_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CitationUpdater:
    """被引用数更新クラス"""

    def __init__(self):
        self.stats = {
            "total": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "no_doi_or_title": 0
        }

    async def update(self, limit: Optional[int] = None, dry_run: bool = False, force: bool = False) -> None:
        """更新処理のメイン関数"""
        try:
            print("\n" + "="*60)
            print("論文被引用数一括更新処理（OpenAlex API）")
            print("="*60 + "\n")

            # Notion接続確認
            print("🔍 Notion接続確認中...")
            if not await notion_service.check_database_connection():
                print("❌ エラー: Notionデータベースに接続できません")
                return
            print("✅ Notion接続成功\n")

            # ChromaDB接続確認
            print("🔍 ChromaDB接続確認中...")
            current_count = chromadb_service.get_count()
            print(f"✅ ChromaDB接続成功（現在の登録数: {current_count}件）\n")

            # 更新設定表示
            print(f"📋 更新設定:")
            print(f"   - 処理制限: {limit if limit else '制限なし'}")
            print(f"   - ドライラン: {'有効' if dry_run else '無効'}")
            print(f"   - 強制更新: {'有効' if force else '無効'}")
            print()

            # Notionから論文ページを取得
            print("📥 Notionから論文ページを取得中...")
            pages = await notion_service.get_recently_updated_pages(
                since_timestamp=None,  # 全期間
                page_size=limit if limit else 10000
            )

            if not pages:
                print("ℹ️  論文ページが見つかりませんでした")
                return

            self.stats["total"] = len(pages)
            print(f"✅ {self.stats['total']}件の論文ページを発見")
            print()

            if dry_run:
                print("🔎 ドライランモード: 以下のページが更新対象です\n")
                for i, page in enumerate(pages[:20], 1):  # 最初の20件のみ表示
                    page_info = self._extract_page_info(page)
                    print(f"  {i:2d}. [{page_info.get('year', '????')}] {page_info['title'][:50]}...")
                if len(pages) > 20:
                    print(f"  ... 他 {len(pages) - 20} 件\n")
                else:
                    print()
                return

            # 各ページを処理
            print("🔄 被引用数の更新を開始します...\n")
            for i, page in enumerate(pages, 1):
                page_info = self._extract_page_info(page)
                page_id = page['id']

                print(f"[{i}/{self.stats['total']}] 処理中: {page_info['title'][:50]}...")

                # 既に被引用数がある場合はスキップ（forceオプションがない場合）
                if not force and page_info.get('citations') is not None:
                    print(f"  ⏭️  スキップ（既に被引用数あり: {page_info['citations']}件）")
                    self.stats['skipped'] += 1
                    continue

                # DOIまたはタイトルがない場合はスキップ
                doi = page_info.get('doi')
                title = page_info.get('title')

                if not doi and not title:
                    print(f"  ⚠️  スキップ（DOIとタイトルが両方とも不明）")
                    self.stats['no_doi_or_title'] += 1
                    continue

                # OpenAlexから被引用数を取得
                try:
                    openalex_metadata = await asyncio.to_thread(
                        openalex_service.get_paper_metadata,
                        doi=doi,
                        title=title
                    )

                    if openalex_metadata and openalex_metadata.get('cited_by_count') is not None:
                        cited_by_count = openalex_metadata['cited_by_count']
                        openalex_id = openalex_metadata.get('openalex_id')

                        print(f"  📊 被引用数取得: {cited_by_count}件")

                        # Notionを更新
                        await self._update_notion_page(page_id, cited_by_count)

                        # ChromaDBを更新
                        await self._update_chromadb(page_id, cited_by_count)

                        print(f"  ✅ 更新完了")
                        self.stats['updated'] += 1

                    else:
                        print(f"  ⚠️  OpenAlexで論文が見つかりませんでした")
                        self.stats['failed'] += 1

                except Exception as e:
                    print(f"  ❌ エラー: {e}")
                    logger.error(f"被引用数更新エラー [{page_id}]: {e}")
                    self.stats['failed'] += 1

                # API rate limitを考慮して待機
                await asyncio.sleep(0.15)

            # 統計情報表示
            self._print_stats()

        except Exception as e:
            logger.error(f"更新処理エラー: {e}")
            print(f"\n❌ エラーが発生しました: {e}")

    def _extract_page_info(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """ページから必要な情報を抽出"""
        properties = page.get('properties', {})

        # タイトル
        title = "不明"
        title_prop = properties.get('Title', {})
        if 'title' in title_prop and title_prop['title']:
            title = title_prop['title'][0]['text']['content']

        # 年
        year = None
        year_prop = properties.get('Year', {})
        if 'select' in year_prop and year_prop['select']:
            year = year_prop['select']['name']
        elif 'number' in year_prop and year_prop['number']:
            year = str(year_prop['number'])

        # DOI
        doi = None
        doi_prop = properties.get('DOI', {})
        if 'url' in doi_prop and doi_prop['url']:
            doi_url = doi_prop['url']
            # URLからDOI部分を抽出
            if 'doi.org/' in doi_url:
                doi = doi_url.split('doi.org/')[-1]

        # 被引用数（既存）
        citations = None
        citations_prop = properties.get('Citations', {})
        if 'number' in citations_prop and citations_prop['number'] is not None:
            citations = citations_prop['number']

        return {
            'title': title,
            'year': year,
            'doi': doi,
            'citations': citations
        }

    async def _update_notion_page(self, page_id: str, cited_by_count: int) -> None:
        """Notionページの被引用数を更新"""
        try:
            # Notion APIで直接更新
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: notion_service.client.pages.update(
                    page_id=page_id,
                    properties={
                        "Citations": {
                            "number": cited_by_count
                        }
                    }
                )
            )
            logger.debug(f"Notion更新成功 [{page_id}]: {cited_by_count}件")
        except Exception as e:
            logger.error(f"Notion更新エラー [{page_id}]: {e}")
            raise

    async def _update_chromadb(self, notion_page_id: str, cited_by_count: int) -> None:
        """ChromaDBのメタデータを更新"""
        try:
            # ChromaDBでページを検索
            results = chromadb_service.collection.get(
                where={"notion_page_id": notion_page_id},
                include=["metadatas"]
            )

            if results and results['ids']:
                # メタデータを更新
                doc_id = results['ids'][0]
                metadata = results['metadatas'][0]
                metadata['cited_by_count'] = str(cited_by_count)

                # ChromaDBを更新
                chromadb_service.collection.update(
                    ids=[doc_id],
                    metadatas=[metadata]
                )
                logger.debug(f"ChromaDB更新成功 [{notion_page_id}]: {cited_by_count}件")
            else:
                logger.warning(f"ChromaDBに該当ページが見つかりません [{notion_page_id}]")

        except Exception as e:
            logger.error(f"ChromaDB更新エラー [{notion_page_id}]: {e}")
            # ChromaDBエラーは致命的ではないので続行

    def _print_stats(self) -> None:
        """統計情報を表示"""
        print("\n" + "="*60)
        print("📊 更新結果")
        print("="*60)
        print(f"  総ページ数:        {self.stats['total']:4d} 件")
        print(f"  更新成功:          {self.stats['updated']:4d} 件")
        print(f"  スキップ:          {self.stats['skipped']:4d} 件")
        print(f"  失敗:              {self.stats['failed']:4d} 件")
        print(f"  DOI/タイトル不明:  {self.stats['no_doi_or_title']:4d} 件")
        print("="*60 + "\n")


async def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="既存論文の被引用数をOpenAlex APIから一括更新",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python update_citations.py                    # 全論文を更新
  python update_citations.py --limit 10         # 最大10件まで
  python update_citations.py --dry-run          # 実行前の確認のみ
  python update_citations.py --force            # 既に被引用数があっても再取得
        """
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='処理する最大ページ数'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='実際には更新せず、対象ページのみ表示'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='既に被引用数があっても再取得して更新'
    )

    args = parser.parse_args()

    updater = CitationUpdater()
    await updater.update(
        limit=args.limit,
        dry_run=args.dry_run,
        force=args.force
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  ユーザーによる中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        logger.error(f"メイン処理エラー: {e}")
        sys.exit(1)
