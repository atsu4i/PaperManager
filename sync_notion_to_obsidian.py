#!/usr/bin/env python3
"""
NotionとObsidianの同期スクリプト

Notionデータベースでアイテムやプロパティが修正されたときに
Obsidian Vaultの対応するファイルを更新します。

使用方法:
    python sync_notion_to_obsidian.py                    # 全ページを同期
    python sync_notion_to_obsidian.py --since 2024-01-01 # 特定日以降の更新のみ
    python sync_notion_to_obsidian.py --limit 10         # 最大10ページまで
    python sync_notion_to_obsidian.py --dry-run          # 実行前の確認のみ
"""

import asyncio
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.config import config
from app.models.paper import PaperMetadata
from app.services.notion_service import notion_service
from app.services.obsidian_service import obsidian_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class NotionObsidianSynchronizer:
    """NotionとObsidianの同期クラス"""

    def __init__(self):
        self.stats = {
            "total": 0,
            "updated": 0,
            "created": 0,
            "failed": 0,
            "skipped": 0
        }

    async def sync(self, since_date: Optional[str] = None, limit: Optional[int] = None,
                  dry_run: bool = False) -> None:
        """同期処理のメイン関数"""
        try:
            print("\n" + "="*60)
            print("Notion → Obsidian 同期処理")
            print("="*60 + "\n")

            # Obsidian連携が有効かチェック
            if not obsidian_service.enabled:
                print("❌ エラー: Obsidian連携が無効になっています")
                print("   OBSIDIAN_ENABLED=true に設定してください")
                return

            # Notion接続確認
            print("🔍 Notion接続確認中...")
            if not await notion_service.check_database_connection():
                print("❌ エラー: Notionデータベースに接続できません")
                return
            print("✅ Notion接続成功\n")

            # 同期設定表示
            print(f"📋 同期設定:")
            print(f"   - Obsidian Vault: {obsidian_service.vault_path}")
            print(f"   - 更新期間: {since_date if since_date else '全期間'}")
            print(f"   - 処理制限: {limit if limit else '制限なし'}")
            print(f"   - ドライラン: {'有効' if dry_run else '無効'}")
            print()

            # since_dateをISO 8601形式に変換
            since_timestamp = None
            if since_date:
                try:
                    # YYYY-MM-DD形式からISO 8601形式に変換
                    dt = datetime.strptime(since_date, "%Y-%m-%d")
                    since_timestamp = dt.isoformat() + ".000Z"
                except ValueError:
                    print(f"⚠️  警告: 日付形式が不正です（{since_date}）。全期間を対象にします。")

            # Notionから更新されたページを取得
            print("📥 Notionから更新ページを取得中...")
            pages = await notion_service.get_recently_updated_pages(
                since_timestamp=since_timestamp,
                page_size=limit if limit else 100
            )

            if not pages:
                print("ℹ️  更新されたページが見つかりませんでした")
                return

            self.stats["total"] = len(pages)
            print(f"✅ {self.stats['total']}件の更新ページを発見")
            print()

            if dry_run:
                print("🔎 ドライランモード: 以下のページが同期対象です\n")
                for i, page in enumerate(pages, 1):
                    page_info = self._extract_page_info(page)
                    last_edited = page.get("last_edited_time", "不明")
                    print(f"  {i:2d}. [{page_info.get('year', '????')}] {page_info['title'][:60]}...")
                    print(f"      最終更新: {last_edited}")
                print()
                return

            # 各ページを処理
            for i, page in enumerate(pages, 1):
                page_info = self._extract_page_info(page)
                page_id = page["id"]

                print(f"\n[{i}/{self.stats['total']}] 処理中: {page_info['title'][:50]}...")
                print(f"   📝 Notion ID: {page_id}")
                print(f"   🕒 最終更新: {page.get('last_edited_time', '不明')}")

                try:
                    # Notionの生プロパティデータを取得
                    notion_properties = page.get("properties", {})

                    # Obsidianファイルの更新または作成（カスタムプロパティも同期）
                    result = await self._sync_page(page_id, page_info, notion_properties)

                    if result == "updated":
                        self.stats["updated"] += 1
                        print(f"   ✅ 更新完了")
                    elif result == "created":
                        self.stats["created"] += 1
                        print(f"   ✨ 新規作成")
                    else:
                        self.stats["skipped"] += 1
                        print(f"   ⏭️  スキップ")

                except Exception as e:
                    self.stats["failed"] += 1
                    print(f"   ❌ エラー: {e}")
                    logger.error(f"ページ同期エラー [{page_id}]: {e}")

                # 進捗表示
                processed = self.stats["updated"] + self.stats["created"] + self.stats["failed"] + self.stats["skipped"]
                progress = (processed / self.stats["total"]) * 100
                print(f"   進捗: {progress:.1f}% ({processed}/{self.stats['total']})")

                # API制限対策
                if i < len(pages):
                    await asyncio.sleep(0.5)

            # 結果サマリー
            print("\n" + "="*60)
            print("✅ 同期処理完了!")
            print("="*60)
            print(f"\n📊 統計:")
            print(f"   - 対象ページ数: {self.stats['total']}")
            print(f"   - 更新: {self.stats['updated']}")
            print(f"   - 新規作成: {self.stats['created']}")
            print(f"   - 失敗: {self.stats['failed']}")
            print(f"   - スキップ: {self.stats['skipped']}")
            print()

        except KeyboardInterrupt:
            print(f"\n\n⚠️  ユーザーによる中断")
            processed = self.stats["updated"] + self.stats["created"] + self.stats["failed"] + self.stats["skipped"]
            print(f"   処理済み: {processed}/{self.stats['total']}")

        except Exception as e:
            print(f"\n❌ 同期処理でエラーが発生しました: {e}")
            logger.error(f"同期処理エラー: {e}")

    def _extract_page_info(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """NotionページからPaperMetadataを抽出"""
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

            # 要約の取得（childrenから）- ここでは簡略版
            summary = ""
            # 実際の要約はページコンテンツ取得が必要だが、ここでは省略

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

    async def _sync_page(self, page_id: str, page_info: Dict[str, Any],
                        notion_properties: Optional[Dict[str, Any]] = None) -> str:
        """個別ページの同期

        Args:
            page_id: Notion ページID
            page_info: 抽出済みの基本情報
            notion_properties: Notionの生プロパティデータ（カスタムプロパティ同期用）

        Returns:
            "updated": 既存ファイルを更新
            "created": 新規ファイルを作成
            "skipped": スキップ
        """
        try:
            # PaperMetadataオブジェクトを作成
            paper_metadata = PaperMetadata(
                title=page_info["title"],
                authors=page_info["authors"],
                journal=page_info["journal"],
                publication_year=str(page_info["year"]) if page_info["year"] else None,
                doi=page_info["doi"],
                pmid=page_info["pmid"],
                summary_japanese=page_info["summary"] or f"Notionから同期された論文データ（{datetime.now().strftime('%Y-%m-%d %H:%M')}）",
                keywords=page_info["keywords"],
                # 必須フィールド
                file_path="",  # PDF情報なし
                file_name="",
                file_size=0
            )

            # PubMed URLを設定
            if page_info["pmid"]:
                from app.services.pubmed_service import pubmed_service
                paper_metadata.pubmed_url = pubmed_service.create_pubmed_url(page_info["pmid"])

            # Obsidianファイルを更新（既存なら更新、新規なら作成）
            existing_file = obsidian_service.find_file_by_notion_id(page_id)

            if existing_file:
                # 既存ファイルを更新（Notionの生プロパティも渡す）
                success = await obsidian_service.update_paper(
                    paper_metadata,
                    page_id,
                    notion_properties=notion_properties
                )
                return "updated" if success else "failed"
            else:
                # 新規ファイルとして作成
                success = await obsidian_service.export_paper(
                    paper_metadata,
                    pdf_path=None,
                    notion_page_id=page_id
                )
                return "created" if success else "failed"

        except Exception as e:
            raise Exception(f"ページ同期エラー: {e}")


async def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="NotionとObsidianの同期スクリプト",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python sync_notion_to_obsidian.py                      # 全ページを同期
  python sync_notion_to_obsidian.py --since 2024-01-01   # 2024年1月1日以降の更新を同期
  python sync_notion_to_obsidian.py --limit 10           # 最大10ページまで同期
  python sync_notion_to_obsidian.py --dry-run            # 実行前の確認のみ

ヒント:
  - 定期的に実行して、Notionの変更をObsidianに反映できます
  - GUIの「同期」ボタンからも実行可能です
  - 常にNotionの内容が優先され、Obsidianファイルを上書きします
        """
    )

    parser.add_argument(
        "--since",
        type=str,
        help="指定した日付以降の更新のみを同期 (例: 2024-01-01)"
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="同期するページ数の上限"
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

    if not obsidian_service.enabled:
        print("❌ Obsidian連携が無効になっています")
        print("   OBSIDIAN_ENABLED=true に設定してください")
        return

    # 同期実行
    synchronizer = NotionObsidianSynchronizer()
    await synchronizer.sync(
        since_date=args.since,
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
