#!/usr/bin/env python3
"""
論文管理システム CLI
"""

import argparse
import asyncio
import sys
from pathlib import Path

# パッケージパスを追加
sys.path.insert(0, str(Path(__file__).parent))

from app.main import app
from app.config import config
from app.utils.logger import get_logger
from app.utils.file_manager import file_manager

logger = get_logger(__name__)


async def process_file(file_path: str):
    """単一ファイルの処理"""
    logger.info(f"単一ファイル処理開始: {file_path}")
    
    result = await app.process_single_file(file_path)
    
    if result.success:
        print(f"✅ 処理成功: {file_path}")
        print(f"   処理時間: {result.processing_time:.1f}秒")
        if result.notion_page_id:
            print(f"   Notion Page ID: {result.notion_page_id}")
        if result.paper_metadata:
            print(f"   タイトル: {result.paper_metadata.title}")
            if result.paper_metadata.pmid:
                print(f"   PMID: {result.paper_metadata.pmid}")
    else:
        print(f"❌ 処理失敗: {file_path}")
        print(f"   エラー: {result.error_message}")


async def start_daemon():
    """デーモンモードでシステム開始"""
    logger.info("デーモンモードでシステム開始")
    print(f"📁 監視フォルダ: {config.watch_folder}")
    print("🔄 ファイル監視を開始しました...")
    print("⏹️  停止するには Ctrl+C を押してください")
    
    await app.start()


def check_config():
    """設定チェック"""
    print("🔧 設定チェック")
    print("=" * 50)
    
    # 必須設定のチェック
    errors = []
    warnings = []
    
    if not config.gemini_api_key:
        errors.append("GEMINI_API_KEY が設定されていません")
    
    if not config.notion_token:
        errors.append("NOTION_TOKEN が設定されていません")
    
    if not config.google_credentials_path:
        warnings.append("GOOGLE_APPLICATION_CREDENTIALS が設定されていません")
    
    # 監視フォルダの確認
    watch_folder = Path(config.watch_folder)
    if not watch_folder.exists():
        warnings.append(f"監視フォルダが存在しません: {watch_folder}")
    
    # 設定内容を表示
    print(f"Gemini Model: {config.gemini.model}")
    print(f"Notion Database ID: {config.notion_database_id}")
    print(f"監視フォルダ: {config.watch_folder}")
    print(f"最大並行処理数: {config.file_processing.max_concurrent_files}")
    print(f"ログレベル: {config.logging.level}")
    
    # エラー・警告の表示
    if errors:
        print("\n❌ エラー:")
        for error in errors:
            print(f"   {error}")
    
    if warnings:
        print("\n⚠️  警告:")
        for warning in warnings:
            print(f"   {warning}")
    
    if not errors:
        print("\n✅ 設定に問題ありません")
        return True
    else:
        print("\n❌ 設定に問題があります")
        return False


def create_env_file():
    """環境設定ファイルの作成"""
    env_file = Path(".env")
    example_file = Path(".env.example")
    
    if env_file.exists():
        response = input(f"{env_file} は既に存在します。上書きしますか? (y/N): ")
        if response.lower() != 'y':
            print("キャンセルされました")
            return
    
    if example_file.exists():
        # .env.exampleの内容をコピー
        content = example_file.read_text(encoding='utf-8')
        env_file.write_text(content, encoding='utf-8')
        print(f"✅ {env_file} を作成しました")
        print("必要な設定値を編集してください:")
        print("  - GEMINI_API_KEY")
        print("  - NOTION_TOKEN")
        print("  - GOOGLE_APPLICATION_CREDENTIALS (Vision API使用時)")
    else:
        print("❌ .env.example ファイルが見つかりません")


def create_folders():
    """必要なフォルダの作成"""
    folders = [
        Path(config.watch_folder),
        Path(config.processed_folder),
        Path("logs")
    ]
    
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
        print(f"📁 フォルダ作成: {folder}")
    
    # 処理済みフォルダ内のサブフォルダも作成
    processed_subfolders = [
        Path(config.processed_folder) / "success",
        Path(config.processed_folder) / "failed",
        Path(config.processed_folder) / "backup"
    ]
    
    for subfolder in processed_subfolders:
        subfolder.mkdir(parents=True, exist_ok=True)
        print(f"📁 サブフォルダ作成: {subfolder}")
    
    print("✅ 必要なフォルダを作成しました")


async def show_status():
    """システム状態の表示"""
    print("📊 システム状態")
    print("=" * 50)
    
    # 設定情報
    print(f"監視フォルダ: {config.watch_folder}")
    print(f"処理済みフォルダ: {config.processed_folder}")
    
    # フォルダ存在チェック
    watch_exists = Path(config.watch_folder).exists()
    processed_exists = Path(config.processed_folder).exists()
    
    print(f"監視フォルダ存在: {'✅' if watch_exists else '❌'}")
    print(f"処理済みフォルダ存在: {'✅' if processed_exists else '❌'}")
    
    if watch_exists:
        # 監視フォルダ内のPDF数
        pdf_files = list(Path(config.watch_folder).rglob("*.pdf"))
        print(f"監視中PDFファイル数: {len(pdf_files)}件")
    
    # ストレージ情報
    storage_info = file_manager.get_storage_info()
    if storage_info:
        print(f"\n📁 処理済みファイル統計:")
        print(f"  成功: {storage_info['success_files']}件")
        print(f"  失敗: {storage_info['failed_files']}件")
        print(f"  バックアップ: {storage_info['backup_files']}件")
        print(f"  総使用量: {storage_info['total_size_mb']} MB")
    
    # 処理済みファイルDB
    db_path = Path(config.processed_files_db)
    if db_path.exists():
        try:
            import json
            with open(db_path, 'r', encoding='utf-8') as f:
                processed_data = json.load(f)
            print(f"\n🗃️  処理履歴: {len(processed_data)}件")
        except Exception as e:
            print(f"\n🗃️  処理履歴読み込みエラー: {e}")
    else:
        print(f"\n🗃️  処理履歴: 0件（未作成）")


def cleanup_old_files(days: int):
    """古いファイルのクリーンアップ"""
    print(f"🧹 {days}日以前のファイルをクリーンアップ中...")
    
    try:
        file_manager.cleanup_old_files(days)
        print("✅ クリーンアップ完了")
        
        # クリーンアップ後の状態表示
        storage_info = file_manager.get_storage_info()
        if storage_info:
            print(f"現在の使用量: {storage_info['total_size_mb']} MB")
            
    except Exception as e:
        print(f"❌ クリーンアップエラー: {e}")


async def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="論文管理システム",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python cli.py start                    # デーモンモード開始
  python cli.py process paper.pdf       # 単一ファイル処理
  python cli.py config                   # 設定チェック
  python cli.py setup                    # 初期セットアップ
  python cli.py status                   # システム状態確認
  python cli.py cleanup --days 30       # 30日以前のファイルクリーンアップ
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='コマンド')
    
    # startコマンド
    subparsers.add_parser('start', help='デーモンモードでシステム開始')
    
    # processコマンド
    process_parser = subparsers.add_parser('process', help='単一ファイルの処理')
    process_parser.add_argument('file', help='処理するPDFファイルのパス')
    
    # configコマンド
    subparsers.add_parser('config', help='設定チェック')
    
    # setupコマンド
    subparsers.add_parser('setup', help='初期セットアップ')
    
    # statusコマンド
    subparsers.add_parser('status', help='システム状態確認')
    
    # cleanupコマンド
    cleanup_parser = subparsers.add_parser('cleanup', help='古いファイルのクリーンアップ')
    cleanup_parser.add_argument('--days', type=int, default=30, help='保持日数（デフォルト: 30日）')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'start':
            if not check_config():
                print("設定を修正してから再実行してください")
                sys.exit(1)
            await start_daemon()
            
        elif args.command == 'process':
            if not check_config():
                print("設定を修正してから再実行してください")
                sys.exit(1)
            await process_file(args.file)
            
        elif args.command == 'config':
            check_config()
            
        elif args.command == 'setup':
            print("🛠️  初期セットアップ")
            create_env_file()
            create_folders()
            print("\n次の手順:")
            print("1. .env ファイルを編集して必要な設定を入力")
            print("2. python cli.py config で設定をチェック")
            print("3. python cli.py start でシステム開始")
            
        elif args.command == 'status':
            await show_status()
            
        elif args.command == 'cleanup':
            cleanup_old_files(args.days)
            
    except KeyboardInterrupt:
        print("\n⏹️  中断されました")
    except Exception as e:
        logger.error(f"CLIエラー: {e}")
        print(f"❌ エラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())