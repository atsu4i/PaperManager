#!/usr/bin/env python3
"""
Notion SDK診断スクリプト
"""

import sys
import os

print("=" * 60)
print("Notion SDK 診断ツール")
print("=" * 60)
print()

# 1. Python環境の確認
print("1. Python環境")
print(f"   Python実行ファイル: {sys.executable}")
print(f"   Pythonバージョン: {sys.version}")
print()

# 2. notion-client のインストール確認
print("2. notion-client インストール状況")
try:
    import notion_client
    print(f"   ✅ notion-client インポート成功")

    # バージョン確認（複数の方法で試行）
    version = None
    if hasattr(notion_client, '__version__'):
        version = notion_client.__version__
        print(f"   バージョン (__version__): {version}")
    else:
        print(f"   ⚠️  __version__ 属性が存在しません")

        # 代替方法: importlib.metadata を使用
        try:
            from importlib.metadata import version as get_version
            version = get_version('notion-client')
            print(f"   バージョン (importlib.metadata): {version}")
        except Exception as e:
            print(f"   ⚠️  importlib.metadata でも取得失敗: {e}")

            # さらに代替: pkg_resources を使用
            try:
                import pkg_resources
                version = pkg_resources.get_distribution('notion-client').version
                print(f"   バージョン (pkg_resources): {version}")
            except Exception as e2:
                print(f"   ⚠️  pkg_resources でも取得失敗: {e2}")

    print(f"   インストール場所: {notion_client.__file__}")
    print(f"   モジュール属性: {dir(notion_client)[:10]}...")  # 最初の10個

except ImportError as e:
    print(f"   ❌ notion-client インポート失敗: {e}")
    sys.exit(1)

print()

# 3. Client クラスの確認
print("3. Client クラス")
try:
    from notion_client import Client
    print(f"   ✅ Client インポート成功")
    print(f"   Client クラス: {Client}")
except ImportError as e:
    print(f"   ❌ Client インポート失敗: {e}")
    sys.exit(1)

print()

# 4. databases エンドポイントの確認
print("4. databases エンドポイント")
try:
    # ダミーのクライアントを作成（トークンは無効でOK）
    client = Client(auth="dummy_token_for_testing")
    print(f"   ✅ Client インスタンス作成成功")
    print(f"   databases 属性: {client.databases}")
    print(f"   databases 型: {type(client.databases)}")

    # query メソッドの存在確認
    if hasattr(client.databases, 'query'):
        print(f"   ✅ databases.query メソッド存在")
    else:
        print(f"   ❌ databases.query メソッドが存在しません")
        print(f"   利用可能なメソッド: {dir(client.databases)}")

except Exception as e:
    print(f"   ❌ エラー: {e}")
    import traceback
    traceback.print_exc()

print()

# 5. pip show の情報
print("5. pip show notion-client")
import subprocess
try:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "show", "notion-client"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
except Exception as e:
    print(f"   エラー: {e}")

print()

# 6. 環境変数の確認
print("6. 環境変数")
print(f"   VIRTUAL_ENV: {os.environ.get('VIRTUAL_ENV', '未設定')}")
print(f"   PATH (最初の3つ): {':'.join(os.environ.get('PATH', '').split(':')[:3])}")

print()
print("=" * 60)
print("診断完了")
print("=" * 60)
