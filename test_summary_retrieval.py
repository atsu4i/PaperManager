#!/usr/bin/env python3
"""
要約取得テストスクリプト

Notionページから要約（blocks）が正しく取得できるかテストします。

使用方法:
    python test_summary_retrieval.py
"""

import asyncio
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.config import config
from app.services.notion_service import notion_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def test_summary_retrieval():
    """要約取得のテスト"""
    try:
        print("\n" + "="*60)
        print("Notion要約取得テスト")
        print("="*60 + "\n")

        # Notion接続確認
        print("🔍 Notion接続確認中...")
        if not await notion_service.check_database_connection():
            print("❌ エラー: Notionデータベースに接続できません")
            return
        print("✅ Notion接続成功\n")

        # テスト用に1件のページを取得
        print("📥 テスト用ページを1件取得中...")
        pages = await notion_service.get_recently_updated_pages(
            since_timestamp=None,
            page_size=1
        )

        if not pages:
            print("❌ ページが見つかりませんでした")
            return

        page = pages[0]
        page_id = page["id"]

        # ページタイトル取得
        properties = page.get("properties", {})
        title_prop = properties.get("Title") or properties.get("title")
        title = ""
        if title_prop:
            if title_prop.get("title"):
                title = "".join([t.get("plain_text", "") for t in title_prop["title"]])
            elif title_prop.get("rich_text"):
                title = "".join([t.get("plain_text", "") for t in title_prop["rich_text"]])

        print(f"✅ テスト対象ページ取得成功\n")
        print(f"📄 ページ情報:")
        print(f"   ID: {page_id}")
        print(f"   タイトル: {title}")
        print()

        # 要約（blocks）を取得
        print("📖 要約（blocks）を取得中...")
        summary = await notion_service.get_page_content(page_id)

        if summary:
            print(f"✅ 要約取得成功!\n")
            print("="*60)
            print("取得された要約:")
            print("="*60)
            print(summary)
            print("="*60)
            print(f"\n📏 要約の長さ: {len(summary)}文字")
            print()

            # ベクトル化対象テキストのプレビュー
            vectorize_text = f"{title}\n\n{summary}"
            print("="*60)
            print("ベクトル化対象テキスト（プレビュー）:")
            print("="*60)
            preview_length = 500
            if len(vectorize_text) > preview_length:
                print(vectorize_text[:preview_length] + "...")
                print(f"\n（以下略 - 全{len(vectorize_text)}文字）")
            else:
                print(vectorize_text)
            print("="*60)
            print()

        else:
            print("⚠️  要約が取得できませんでした")
            print("   原因考察:")
            print("   - ページにブロックコンテンツが存在しない可能性")
            print("   - API権限の問題")
            print("   - ページ構造が想定と異なる可能性")
            print()

        # 結論
        print("="*60)
        print("テスト結果:")
        print("="*60)
        if summary:
            print("✅ 要約取得機能は正常に動作しています")
            print("💡 migrate_to_chromadb.pyで全件再移行できます")
        else:
            print("❌ 要約取得に失敗しました")
            print("💡 notion_service.pyの実装を確認してください")
        print()

    except Exception as e:
        print(f"\n❌ テスト中にエラーが発生しました: {e}")
        logger.error(f"要約取得テストエラー: {e}", exc_info=True)


async def main():
    """メイン関数"""
    # 設定確認
    if not config.is_setup_complete():
        print("❌ 設定が不完全です。以下の項目を確認してください:")
        for missing in config.get_missing_configs():
            print(f"  - {missing}")
        return

    await test_summary_retrieval()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  テストが中断されました")
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        sys.exit(1)
