#!/usr/bin/env python3
"""
NotionデータベースからChromaDBへの一括移行スクリプト

既存のNotionデータベースに登録されている論文を
ChromaDBにベクトル化して登録します。

使用方法:
    python migrate_to_chromadb.py                    # 全論文を登録
    python migrate_to_chromadb.py --limit 10         # 最大10件まで
    python migrate_to_chromadb.py --dry-run          # 実行前の確認のみ
"""

import asyncio
import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.config import config
from app.models.paper import PaperMetadata
from app.services.notion_service import notion_service
from app.services.obsidian_service import obsidian_service
from app.services.chromadb_service import chromadb_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ChromaDBMigrator:
    """ChromaDB移行クラス"""

    def __init__(self):
        self.stats = {
            "total": 0,
            "added": 0,
            "skipped": 0,
            "failed": 0
        }

    async def migrate(self, limit: Optional[int] = None, dry_run: bool = False) -> None:
        """移行処理のメイン関数"""
        try:
            print("\n" + "="*60)
            print("Notion → ChromaDB 一括移行処理")
            print("="*60 + "\n")

            # ChromaDB接続確認
            print("🔍 ChromaDB接続確認中...")
            current_count = chromadb_service.get_count()
            print(f"✅ ChromaDB接続成功（現在の登録数: {current_count}件）\n")

            # Notion接続確認
            print("🔍 Notion接続確認中...")
            if not await notion_service.check_database_connection():
                print("❌ エラー: Notionデータベースに接続できません")
                return
            print("✅ Notion接続成功\n")

            # 移行設定表示
            print(f"📋 移行設定:")
            print(f"   - 処理制限: {limit if limit else '制限なし'}")
            print(f"   - ドライラン: {'有効' if dry_run else '無効'}")
            print()

            # Notionから論文ページを取得
            print("📥 Notionから論文ページを取得中...")
            # すべてのページを取得（最近更新されたページから）
            # limitが指定されていない場合は10000件（実質全件）を取得
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
                print("🔎 ドライランモード: 以下のページが移行対象です\n")
                for i, page in enumerate(pages, 1):
                    page_info = self._extract_page_info(page)
                    print(f"  {i:2d}. [{page_info.get('year', '????')}] {page_info['title'][:60]}...")
                print()
                return

            # バッチサイズ（最大100件）
            BATCH_SIZE = 100

            # ページをバッチごとに処理
            for batch_start in range(0, len(pages), BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, len(pages))
                batch_pages = pages[batch_start:batch_end]

                print(f"\n{'='*60}")
                print(f"📦 バッチ処理 [{batch_start + 1}-{batch_end}/{self.stats['total']}]")
                print(f"{'='*60}")

                # バッチ用データ準備
                batch_data = []

                for i, page in enumerate(batch_pages):
                    page_id = page["id"]
                    page_info = self._extract_page_info(page)

                    # すでに登録済みかチェック
                    existing = chromadb_service.get_paper(page_id)
                    if existing:
                        self.stats["skipped"] += 1
                        print(f"[{batch_start + i + 1:3d}] ⏭️  スキップ: {page_info['title'][:50]}...")
                        continue

                    # Notionページのコンテンツ（要約）を取得
                    summary = await notion_service.get_page_content(page_id)
                    if summary:
                        page_info["summary"] = summary

                    # PaperMetadataオブジェクトを作成
                    paper_metadata = PaperMetadata(
                        title=page_info["title"],
                        authors=page_info["authors"],
                        journal=page_info["journal"],
                        publication_year=str(page_info["year"]) if page_info["year"] else None,
                        doi=page_info["doi"],
                        pmid=page_info["pmid"],
                        summary_japanese=page_info["summary"] or "（要約なし）",
                        keywords=page_info["keywords"],
                        # 必須フィールド
                        file_path="",
                        file_name="",
                        file_size=0
                    )

                    # Notion URL生成
                    notion_url = f"https://www.notion.so/{page_id.replace('-', '')}"

                    # Obsidianファイルパスを取得
                    obsidian_path = None
                    if obsidian_service.enabled:
                        obsidian_file = obsidian_service.find_file_by_notion_id(page_id)
                        if obsidian_file:
                            obsidian_path = str(obsidian_file)

                    # バッチデータに追加
                    batch_data.append({
                        "paper": paper_metadata,
                        "notion_page_id": page_id,
                        "notion_url": notion_url,
                        "obsidian_path": obsidian_path,
                        "title": page_info["title"]  # 表示用
                    })

                    print(f"[{batch_start + i + 1:3d}] 📝 準備: {page_info['title'][:50]}...")

                # バッチ処理実行
                if batch_data:
                    print(f"\n🚀 {len(batch_data)}件をバッチ処理中...")

                    try:
                        result = await chromadb_service.add_papers_batch(batch_data)

                        self.stats["added"] += result["success"]
                        self.stats["failed"] += result["failed"]

                        print(f"✅ バッチ処理完了: 成功 {result['success']}件, 失敗 {result['failed']}件")

                        if result["failed_ids"]:
                            print(f"   ❌ 失敗したID: {', '.join(result['failed_ids'][:5])}{'...' if len(result['failed_ids']) > 5 else ''}")

                    except Exception as e:
                        print(f"❌ バッチ処理エラー: {e}")
                        logger.error(f"バッチ処理エラー: {e}")
                        self.stats["failed"] += len(batch_data)

                # 進捗表示
                processed = self.stats["added"] + self.stats["failed"] + self.stats["skipped"]
                progress = (processed / self.stats["total"]) * 100
                print(f"\n📊 全体進捗: {progress:.1f}% ({processed}/{self.stats['total']})")

                # 次のバッチまでの待機（API制限対策）
                if batch_end < len(pages):
                    print(f"⏳ 次のバッチまで待機中...")
                    await asyncio.sleep(2)

            # 結果サマリー
            print("\n" + "="*60)
            print("✅ 移行処理完了!")
            print("="*60)
            print(f"\n📊 統計:")
            print(f"   - 対象ページ数: {self.stats['total']}")
            print(f"   - 登録: {self.stats['added']}")
            print(f"   - スキップ: {self.stats['skipped']}")
            print(f"   - 失敗: {self.stats['failed']}")
            print()

            # 最終的なChromaDB登録数
            final_count = chromadb_service.get_count()
            print(f"📦 ChromaDB最終登録数: {final_count}件")
            print()

        except KeyboardInterrupt:
            print(f"\n\n⚠️  ユーザーによる中断")
            processed = self.stats["added"] + self.stats["failed"] + self.stats["skipped"]
            print(f"   処理済み: {processed}/{self.stats['total']}")

        except Exception as e:
            print(f"\n❌ 移行処理でエラーが発生しました: {e}")
            logger.error(f"移行処理エラー: {e}")

    def _extract_page_info(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """Notionページから基本情報を抽出"""
        try:
            properties = page.get("properties", {})

            # タイトル取得
            title_prop = properties.get("Title") or properties.get("title")
            title = ""
            if title_prop:
                if title_prop.get("title"):
                    title = "".join([t.get("plain_text", "") for t in title_prop["title"]])
                elif title_prop.get("rich_text"):
                    title = "".join([t.get("plain_text", "") for t in title_prop["rich_text"]])

            if not title:
                title = f"Untitled_{page['id'][:8]}"

            # 著者の取得
            authors_prop = properties.get("Authors")
            authors = []
            if authors_prop and authors_prop.get("multi_select"):
                authors = [opt["name"] for opt in authors_prop["multi_select"]]

            # 雑誌の取得
            journal_prop = properties.get("Journal")
            journal = ""
            if journal_prop:
                if journal_prop.get("select"):
                    journal = journal_prop["select"]["name"]
                elif journal_prop.get("rich_text"):
                    journal = "".join([t.get("plain_text", "") for t in journal_prop["rich_text"]])

            # 年の取得
            year_prop = properties.get("Year")
            year = None
            if year_prop:
                if year_prop.get("number"):
                    year = year_prop["number"]
                elif year_prop.get("select") and year_prop["select"].get("name"):
                    try:
                        year = int(year_prop["select"]["name"])
                    except (ValueError, TypeError):
                        year = None

            # DOIの取得
            doi_prop = properties.get("DOI")
            doi = ""
            if doi_prop and doi_prop.get("url"):
                doi = doi_prop["url"]

            # PMIDの取得
            pubmed_prop = properties.get("PubMed")
            pmid = ""
            if pubmed_prop:
                if pubmed_prop.get("url"):
                    pubmed_url = pubmed_prop["url"]
                    import re
                    match = re.search(r'/(\d+)/?$', pubmed_url)
                    if match:
                        pmid = match.group(1)
                elif pubmed_prop.get("rich_text"):
                    pmid = "".join([t.get("plain_text", "") for t in pubmed_prop["rich_text"]])
                elif pubmed_prop.get("number"):
                    pmid = str(pubmed_prop["number"])

            # キーワードの取得
            keywords_prop = properties.get("Key Words")
            keywords = []
            if keywords_prop and keywords_prop.get("multi_select"):
                keywords = [opt["name"] for opt in keywords_prop["multi_select"]]

            # 要約の取得（Notion APIでは簡略版）
            summary = ""
            # 実際の要約は別途ページコンテンツ取得が必要

            return {
                "title": title,
                "authors": authors,
                "journal": journal,
                "year": year,
                "doi": doi,
                "pmid": pmid,
                "keywords": keywords,
                "summary": summary
            }

        except Exception as e:
            logger.error(f"ページ情報抽出エラー: {e}")
            return {
                "title": f"Error_{page.get('id', 'unknown')[:8]}",
                "authors": [],
                "journal": "",
                "year": None,
                "doi": "",
                "pmid": "",
                "keywords": [],
                "summary": ""
            }


async def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="NotionデータベースからChromaDBへの一括移行スクリプト",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python migrate_to_chromadb.py                   # 全論文を登録
  python migrate_to_chromadb.py --limit 10        # 最大10件まで
  python migrate_to_chromadb.py --dry-run         # 実行前の確認のみ

ヒント:
  - 初回実行時は --dry-run で対象ページを確認してから実行することをお勧めします
  - すでに登録済みの論文は自動的にスキップされます
  - Gemini API制限を考慮し、一度に大量のデータを処理する場合は --limit で分割実行してください
        """
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="移行するページ数の上限"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実際の処理は行わず、対象ページの一覧表示のみ"
    )

    args = parser.parse_args()

    # 設定確認
    if not config.is_setup_complete():
        print("❌ 設定が不完全です。以下の項目を確認してください:")
        for missing in config.get_missing_configs():
            print(f"  - {missing}")
        return

    # 移行実行
    migrator = ChromaDBMigrator()
    await migrator.migrate(
        limit=args.limit,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  処理が中断されました")
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        sys.exit(1)
