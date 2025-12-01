"""
処理済みDBから失敗したファイルを削除するスクリプト
"""

import json
from pathlib import Path

def reset_failed_files():
    """処理に失敗したファイルを処理済みDBから削除"""
    db_path = Path("processed_files.json")

    if not db_path.exists():
        print("処理済みDBが見つかりません")
        return

    # DBを読み込み
    with open(db_path, 'r', encoding='utf-8') as f:
        db = json.load(f)

    print(f"現在の処理済みファイル数: {len(db)}件")

    # 失敗したファイルをカウント
    failed_files = {k: v for k, v in db.items() if not v.get('success', False)}
    print(f"失敗したファイル数: {len(failed_files)}件")

    # 失敗したファイルを表示
    print("\n削除対象のファイル:")
    for file_path in failed_files.keys():
        file_name = Path(file_path).name
        print(f"  - {file_name}")

    # ユーザーに確認
    response = input("\nこれらのファイルを処理済みDBから削除しますか？ (y/n): ")

    if response.lower() == 'y':
        # 成功したファイルのみ残す
        success_db = {k: v for k, v in db.items() if v.get('success', False)}

        # バックアップを作成
        backup_path = Path("processed_files.json.backup")
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print(f"\nバックアップを作成しました: {backup_path}")

        # 新しいDBを保存
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(success_db, f, ensure_ascii=False, indent=2)

        print(f"\n処理済みDBを更新しました")
        print(f"削除: {len(failed_files)}件")
        print(f"残り: {len(success_db)}件")
        print("\nGUIを再起動すると、削除されたファイルが再度処理されます。")
    else:
        print("\nキャンセルしました")

if __name__ == "__main__":
    reset_failed_files()
