#!/usr/bin/env python3
"""
NotionからObsidianへの移行スクリプト

既存のNotionデータベースからPDFファイルをダウンロードし
改めてGeminiで解析してObsidian Vaultに保存するための一回限りのスクリプト

使用方法:
    python migrate_notion_to_obsidian.py
    python migrate_notion_to_obsidian.py --year 2024
    python migrate_notion_to_obsidian.py --limit 10
    python migrate_notion_to_obsidian.py --skip-download  # PDFダウンロードをスキップ
    python migrate_notion_to_obsidian.py --dry-run       # 実際の処理は行わずに確認のみ
"""

import asyncio
import argparse
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import requests

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.config import config
from app.models.paper import PaperMetadata
from app.services.notion_service import notion_service
from app.services.gemini_service import gemini_service
from app.services.pdf_processor import pdf_processor
from app.services.obsidian_service import obsidian_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class NotionToObsidianMigrator:
    """NotionからObsidianへの移行クラス"""
    
    def __init__(self):
        self.temp_dir = Path("./temp_migration_pdfs")
        self.temp_dir.mkdir(exist_ok=True)
        self.stats = {
            "total": 0,
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0
        }
    
    async def migrate(self, year_filter: Optional[int] = None, limit: Optional[int] = None, 
                     skip_download: bool = False, dry_run: bool = False) -> None:
        """移行処理のメイン関数"""
        try:
            print("NotionからObsidianへの移行を開始します...")
            
            if not obsidian_service.enabled:
                print("エラー: Obsidian連携が無効になっています設定を確認してください")
                return
            
            # Notion接続確認
            if not await notion_service.check_database_connection():
                print("エラー: Notionデータベースに接続できません")
                return
            
            print(f"Obsidian Vault: {obsidian_service.vault_path}")
            print(f"年フィルター: {year_filter if year_filter else '全年'}")
            print(f"処理制限: {limit if limit else '制限なし'}")
            print(f"PDFダウンロード: {'スキップ' if skip_download else '実行'}")
            print(f"ドライラン: {'有効' if dry_run else '無効'}")
            print()
            
            # Notionから論文データを取得
            print("Notionデータベースから論文データを取得中...")
            papers = await self._fetch_notion_papers(year_filter, limit)
            
            if not papers:
                print("エラー: 移行対象の論文が見つかりませんでした")
                return
            
            self.stats["total"] = len(papers)
            print(f" 移行対象: {self.stats['total']}件の論文")
            print()
            
            if dry_run:
                print(" ドライランモード: 以下の論文が処理対象です")
                for i, paper in enumerate(papers, 1):
                    print(f"  {i:2d}. [{paper.get('year', '????')}] {paper['title'][:60]}...")
                print()
                return
            
            # 各論文を処理
            for i, paper_data in enumerate(papers, 1):
                print(f"\n [{i}/{self.stats['total']}] 処理中: {paper_data['title'][:50]}...")
                
                try:
                    is_new = await self._process_paper(paper_data, skip_download)
                    if is_new:
                        self.stats["successful"] += 1
                    else:
                        self.stats["skipped"] += 1
                    print(f" 完了")

                except Exception as e:
                    self.stats["failed"] += 1
                    print(f" エラー: {e}")
                    logger.error(f"論文処理エラー [{paper_data.get('title', 'Unknown')}]: {e}")
                
                finally:
                    self.stats["processed"] += 1
                    
                    # 進捗表示
                    progress = (self.stats["processed"] / self.stats["total"]) * 100
                    print(f" 進捗: {progress:.1f}% ({self.stats['processed']}/{self.stats['total']})")
                
                # 処理間隔API制限対策
                if i < len(papers):
                    await asyncio.sleep(1)
            
            # 結果表示
            print(f"\n 移行処理完了!")
            print(f" 統計:")
            print(f"  - 対象論文数: {self.stats['total']}")
            print(f"  - 成功: {self.stats['successful']}")
            print(f"  - 失敗: {self.stats['failed']}")
            print(f"  - スキップ: {self.stats['skipped']}")
            
        except KeyboardInterrupt:
            print(f"\n ユーザーによる中断")
            print(f" 処理済み: {self.stats['processed']}/{self.stats['total']}")
            
        except Exception as e:
            print(f" 移行処理でエラーが発生しました: {e}")
            logger.error(f"移行処理エラー: {e}")
            
        finally:
            # 一時ファイルクリーンアップ
            await self._cleanup_temp_files()
    
    async def _fetch_notion_papers(self, year_filter: Optional[int] = None, 
                                  limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Notionデータベースから論文データを取得"""
        try:
            # Notionデータベースをクエリ
            query_filter = {}
            
            # 年フィルターを適用
            if year_filter:
                query_filter = {
                    "property": "Year",
                    "number": {
                        "equals": year_filter
                    }
                }
            
            # ページを取得
            pages = []
            has_more = True
            next_cursor = None
            
            while has_more and (not limit or len(pages) < limit):
                page_size = min(100, limit - len(pages) if limit else 100)
                
                response = await notion_service.query_database_pages(
                    filter_conditions=query_filter if query_filter else None,
                    page_size=page_size,
                    start_cursor=next_cursor
                )
                
                if not response:
                    break
                
                pages.extend(response.get("results", []))
                has_more = response.get("has_more", False)
                next_cursor = response.get("next_cursor")
                
                if limit and len(pages) >= limit:
                    pages = pages[:limit]
                    break
            
            # 論文データに変換
            papers = []
            for page in pages:
                try:
                    paper_data = self._parse_notion_page(page)
                    if paper_data:
                        papers.append(paper_data)
                except Exception as e:
                    logger.warning(f"ページ解析エラー [{page.get('id')}]: {e}")
                    continue
            
            return papers
            
        except Exception as e:
            logger.error(f"Notion論文データ取得エラー: {e}")
            return []
    
    def _parse_notion_page(self, page: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """NotionページからPDFファイルのメタデータを抽出"""
        try:
            properties = page.get("properties", {})

            # PDFプロパティを確認
            pdf_prop = properties.get("PDF") or properties.get("pdf")
            if not pdf_prop or not pdf_prop.get("files"):
                return None  # PDFがない場合はスキップ
            
            pdf_files = pdf_prop.get("files", [])
            if not pdf_files:
                return None
            
            # 最初のPDFファイルを使用
            pdf_file = pdf_files[0]
            pdf_url = pdf_file.get("file", {}).get("url") or pdf_file.get("external", {}).get("url")
            
            if not pdf_url:
                return None
            
            # メタデータ抽出
            title_prop = properties.get("Title") or properties.get("title")
            title = ""
            if title_prop:
                if title_prop.get("title"):
                    title = "".join([t.get("plain_text", "") for t in title_prop["title"]])
                elif title_prop.get("rich_text"):
                    title = "".join([t.get("plain_text", "") for t in title_prop["rich_text"]])
            
            if not title:
                title = f"Untitled_{page['id'][:8]}"
            
            # 年の取得
            year_prop = properties.get("Year")
            year = None
            if year_prop:
                # number型とselect型の両方に対応
                if year_prop.get("number"):
                    year = year_prop["number"]
                elif year_prop.get("select") and year_prop["select"].get("name"):
                    try:
                        year = int(year_prop["select"]["name"])
                    except (ValueError, TypeError):
                        year = None
            
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
            
            # DOIの取得
            doi_prop = properties.get("DOI")
            doi = ""
            if doi_prop and doi_prop.get("url"):
                doi = doi_prop["url"]

            # PMIDの取得（PubMedプロパティから）
            pubmed_prop = properties.get("PubMed")
            pmid = ""
            if pubmed_prop:
                # url型の場合（例: https://pubmed.ncbi.nlm.nih.gov/12345678/）
                if pubmed_prop.get("url"):
                    pubmed_url = pubmed_prop["url"]
                    # URLからPMIDを抽出
                    import re
                    match = re.search(r'/(\d+)/?$', pubmed_url)
                    if match:
                        pmid = match.group(1)
                # rich_text型の場合
                elif pubmed_prop.get("rich_text"):
                    pmid = "".join([t.get("plain_text", "") for t in pubmed_prop["rich_text"]])
                # number型の場合
                elif pubmed_prop.get("number"):
                    pmid = str(pubmed_prop["number"])

            return {
                "notion_id": page["id"],
                "title": title,
                "authors": authors,
                "journal": journal,
                "year": year,
                "doi": doi,
                "pmid": pmid,
                "pdf_url": pdf_url,
                "pdf_filename": pdf_file.get("name", f"{title[:30]}.pdf")
            }
            
        except Exception as e:
            logger.error(f"Notionページ解析エラー: {e}")
            return None
    
    async def _process_paper(self, paper_data: Dict[str, Any], skip_download: bool = False) -> bool:
        """個別論文の処理

        Returns:
            bool: True=新規作成、False=スキップ
        """
        try:
            # ステップ1: NotionデータからPMIDとDOIを取得
            pmid = paper_data.get("pmid", "")
            doi = paper_data.get("doi", "")

            # ステップ2: PMIDで重複チェック
            print(f"   重複チェック中...")
            if pmid:
                existing_file = obsidian_service._find_existing_file_by_pmid(pmid)
                if existing_file:
                    print(f"    既存ファイル発見（PMID: {pmid}）: {existing_file.name}")
                    print(f"    既にエクスポート済みのためスキップします")
                    return False  # スキップ

            # ステップ3: DOIで重複チェック（PMIDで見つからなかった場合）
            if doi:
                existing_file = obsidian_service._find_existing_file_by_doi(doi)
                if existing_file:
                    print(f"    既存ファイル発見（DOI: {doi}）: {existing_file.name}")
                    print(f"    既にエクスポート済みのためスキップします")
                    return False  # スキップ

            # ステップ4: 重複なし → PDFダウンロードと解析を実行
            pdf_path = None

            # PDFダウンロード
            if not skip_download:
                print(f"   PDFダウンロード中...")
                pdf_path = await self._download_pdf(paper_data["pdf_url"], paper_data["pdf_filename"])

                if not pdf_path:
                    raise Exception("PDFダウンロードに失敗しました")

            # PDF解析（ダウンロードした場合のみ）
            paper_metadata = None
            if pdf_path and pdf_path.exists():
                print(f"   PDF解析中...")

                # PDFからテキスト抽出
                pdf_text = await pdf_processor.extract_text_from_pdf(str(pdf_path))

                if not pdf_text or len(pdf_text.strip()) < 100:
                    raise Exception("PDFからテキストを抽出できませんでした")

                # Geminiで解析（キーワード抽出を強化）
                paper_metadata = await gemini_service.analyze_paper(pdf_text, paper_data["title"])

                # 既存のメタデータを保持・補完
                if not paper_metadata.title or len(paper_metadata.title) < len(paper_data["title"]):
                    paper_metadata.title = paper_data["title"]

                if not paper_metadata.authors and paper_data["authors"]:
                    paper_metadata.authors = paper_data["authors"]

                if not paper_metadata.journal and paper_data["journal"]:
                    paper_metadata.journal = paper_data["journal"]

                if not paper_metadata.publication_year and paper_data["year"]:
                    paper_metadata.publication_year = str(paper_data["year"])

                if not paper_metadata.doi and doi:
                    paper_metadata.doi = doi

                if not paper_metadata.pmid and pmid:
                    paper_metadata.pmid = pmid
                    from app.services.pubmed_service import pubmed_service
                    paper_metadata.pubmed_url = pubmed_service.create_pubmed_url(pmid)

                # ファイル情報を設定
                paper_metadata.file_path = str(pdf_path)
                paper_metadata.file_name = paper_data["pdf_filename"]
                paper_metadata.file_size = pdf_path.stat().st_size

                # PubMed検索を追加（PMIDがない場合のみ）
                if not pmid:
                    print(f"   PubMed検索中...")
                    try:
                        from app.services.pubmed_service import pubmed_service
                        pmid = await pubmed_service.search_pmid(paper_metadata)
                        if pmid:
                            paper_metadata.pmid = pmid
                            paper_metadata.pubmed_url = pubmed_service.create_pubmed_url(pmid)
                            print(f"    PMID発見: {pmid}")

                            # PubMedメタデータで補完
                            pubmed_metadata = await pubmed_service.fetch_metadata_from_pubmed(pmid)
                            if pubmed_metadata:
                                if not paper_metadata.authors and pubmed_metadata.get("authors"):
                                    paper_metadata.authors = pubmed_metadata["authors"]
                                    print(f"    著者情報を更新: {len(paper_metadata.authors)}名")
                        else:
                            print(f"    PMID見つからず")
                    except Exception as e:
                        print(f"    PubMed検索エラー: {e}")

            else:
                # PDFダウンロードをスキップした場合、既存データからメタデータを作成
                paper_metadata = PaperMetadata(
                    title=paper_data["title"],
                    authors=paper_data["authors"],
                    journal=paper_data["journal"],
                    publication_year=str(paper_data["year"]) if paper_data["year"] else None,
                    doi=doi,
                    pmid=pmid,
                    summary_japanese=f"NotionからObsidianに移行された論文データ\nPDF解析はスキップされました",
                    keywords=[],  # 空のキーワード
                    # 必須フィールド
                    file_path="",  # 空文字列（PDFなし）
                    file_name=paper_data["pdf_filename"],
                    file_size=0  # サイズ不明
                )

                # PubMed URLを設定
                if pmid:
                    from app.services.pubmed_service import pubmed_service
                    paper_metadata.pubmed_url = pubmed_service.create_pubmed_url(pmid)

            # Obsidianエクスポート
            print(f"   Obsidianエクスポート中...")
            success = await obsidian_service.export_paper(
                paper_metadata,
                None,  # PDFファイルコピーは無効
                paper_data["notion_id"]
            )

            if not success:
                raise Exception("Obsidianエクスポートに失敗しました")

            return True  # 新規作成成功

        except Exception as e:
            raise Exception(f"論文処理エラー: {e}")
    
    async def _download_pdf(self, pdf_url: str, filename: str) -> Optional[Path]:
        """PDFファイルをダウンロード"""
        try:
            # ファイル名をサニタイズ
            safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).strip()
            if not safe_filename.endswith('.pdf'):
                safe_filename += '.pdf'
            
            pdf_path = self.temp_dir / safe_filename
            
            # 既に存在する場合はスキップ
            if pdf_path.exists():
                logger.info(f"既存PDFを使用: {pdf_path}")
                return pdf_path
            
            # ダウンロード実行
            response = requests.get(pdf_url, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(pdf_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"PDFダウンロード完了: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            logger.error(f"PDFダウンロードエラー [{pdf_url}]: {e}")
            return None
    
    async def _cleanup_temp_files(self):
        """一時ファイルをクリーンアップ"""
        try:
            if self.temp_dir.exists():
                for file in self.temp_dir.glob("*.pdf"):
                    try:
                        file.unlink()
                    except Exception as e:
                        logger.warning(f"一時ファイル削除エラー [{file}]: {e}")
                
                # 空の場合はディレクトリも削除
                try:
                    self.temp_dir.rmdir()
                except OSError:
                    pass  # ディレクトリが空でない場合は残す
                    
        except Exception as e:
            logger.warning(f"一時ファイルクリーンアップエラー: {e}")


async def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="NotionからObsidianへの論文移行スクリプト",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python migrate_notion_to_obsidian.py                    # 全論文を移行
  python migrate_notion_to_obsidian.py --year 2024        # 2024年の論文のみ
  python migrate_notion_to_obsidian.py --limit 10         # 最初の10件のみ
  python migrate_notion_to_obsidian.py --skip-download    # PDFダウンロードをスキップ
  python migrate_notion_to_obsidian.py --dry-run          # 実行前の確認のみ
        """
    )
    
    parser.add_argument(
        "--year",
        type=int,
        help="指定した年の論文のみを移行 (例: 2024)"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        help="移行する論文数の上限"
    )
    
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="PDFダウンロードをスキップ既存メタデータのみでObsidianファイル作成"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実際の処理は行わず対象論文の一覧表示のみ"
    )
    
    args = parser.parse_args()
    
    # 設定確認
    if not config.is_setup_complete():
        print(" 設定が不完全です以下の項目を確認してください:")
        for missing in config.get_missing_configs():
            print(f"  - {missing}")
        return
    
    if not obsidian_service.enabled:
        print(" Obsidian連携が無効になっています")
        print("   OBSIDIAN_ENABLED=true に設定してください")
        return
    
    # 移行実行
    migrator = NotionToObsidianMigrator()
    await migrator.migrate(
        year_filter=args.year,
        limit=args.limit,
        skip_download=args.skip_download,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n 処理が中断されました")
    except Exception as e:
        print(f" エラーが発生しました: {e}")
        sys.exit(1)