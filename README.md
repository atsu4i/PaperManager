# 論文管理システム (Paper Manager)

医学論文のPDFファイルを自動解析し、Notionデータベースに登録するシステムです。

## 機能

- 📄 **PDF自動処理**: フォルダ監視により新しいPDFファイルを自動検出
- 🔍 **テキスト抽出**: Google Cloud Vision API + PyMuPDFで高精度なテキスト抽出
- 🤖 **AI解析**: Gemini 2.0 Flash Expによる論文メタデータ抽出と日本語要約
- 🔬 **PubMed連携**: 自動PMID検索とPubMedリンク生成
- 📚 **Notion統合**: 構造化されたデータベースへの自動投稿
- ⚡ **並行処理**: 複数ファイルの同時処理対応

## システム要件

- Python 3.8以上
- Google Cloud プロジェクト (Vision API有効)
- Gemini API アクセス
- Notion API アクセス

## インストール

### 1. リポジトリのクローン
```bash
git clone <repository-url>
cd PaperManager
```

### 2. 依存関係のインストール
```bash
pip install -r requirements.txt
```

### 3. 初期セットアップ
```bash
python cli.py setup
```

### 4. 環境設定
`.env`ファイルを編集して必要な設定を入力:

```env
# Google Cloud 認証
GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json

# Gemini API Key
GEMINI_API_KEY=your_gemini_api_key_here

# Notion API
NOTION_TOKEN=your_notion_token_here
NOTION_DATABASE_ID=3567584d934242a2b85acd3751b3997b

# PubMed API (オプション)
PUBMED_EMAIL=your_email@example.com

# PDF監視フォルダ
WATCH_FOLDER=./pdfs

# ログレベル
LOG_LEVEL=INFO
```

## 使用方法

### デーモンモード（推奨）
システムを常駐させてフォルダを監視:
```bash
python cli.py start
```

### 単一ファイル処理
特定のPDFファイルを手動処理:
```bash
python cli.py process path/to/paper.pdf
```

### 設定チェック
現在の設定を確認:
```bash
python cli.py config
```

### システム状態確認
処理済みファイル数やストレージ使用量を確認:
```bash
python cli.py status
```

### ファイルクリーンアップ
古いバックアップファイルを削除:
```bash
python cli.py cleanup --days 30  # 30日以前のファイルを削除
```

## API設定

### Google Cloud Vision API
1. Google Cloud Consoleでプロジェクトを作成
2. Vision APIを有効化
3. サービスアカウントキーを作成
4. `GOOGLE_APPLICATION_CREDENTIALS`環境変数にパスを設定

### Gemini API
1. Google AI Studioでプロジェクトを作成
2. APIキーを生成
3. `GEMINI_API_KEY`環境変数に設定

### Notion API
1. Notion Integrationを作成
2. データベースにIntegrationを招待
3. `NOTION_TOKEN`環境変数にトークンを設定

## 設定ファイル

### config/config.yaml
システムの詳細設定:
- ファイル処理設定 (最大サイズ、並行数など)
- AI設定 (モデル、温度、トークン数など)
- PubMed検索設定
- ログ設定

### config/article_template.json
Notion投稿用のテンプレート (自動使用)

## ログ

- コンソール出力: カラー付きログ
- ファイル出力: `logs/paper_manager.log` (ローテーション対応)

## 処理フロー

1. **ファイル検出**: 監視フォルダ内の新しいPDFを検出
2. **PDF処理**: テキスト抽出 (PyMuPDF → Vision API)
3. **論文解析**: Geminiでメタデータ抽出と要約作成
4. **PubMed検索**: タイトル・著者・DOIでPMID検索
5. **重複チェック**: Notion内の既存記事確認
6. **データ投稿**: Notionデータベースにページ作成
7. **ファイル移動**: 処理済みPDFを`processed_pdfs`フォルダに移動

## フォルダ構造

```
PaperManager/
├── pdfs/                   # PDF監視フォルダ（ここにPDFを配置）
├── processed_pdfs/         # 処理済みPDFの保存先
│   ├── success/           # 正常処理されたPDF
│   │   └── 2024-12/      # 月別サブフォルダ
│   ├── failed/            # 処理失敗したPDF
│   │   └── 2024-12/
│   └── backup/            # バックアップファイル
└── logs/                   # ログファイル
```

### ファイル命名規則

処理済みファイルは以下の形式で名前が変更されます：
- 成功: `✓_20241217_123456_original_filename_12345678.pdf`
- 失敗: `✗_20241217_123456_original_filename.pdf`

形式: `[ステータス]_[日時]_[元ファイル名]_[NotionページID(成功時のみ)].pdf`

## トラブルシューティング

### よくある問題

1. **Vision API エラー**
   - Google Cloud認証を確認
   - Vision APIが有効化されているか確認
   - 課金設定を確認

2. **Gemini API エラー**
   - APIキーの有効性を確認
   - API制限に達していないか確認

3. **Notion API エラー**
   - トークンの有効性を確認
   - データベースIDが正しいか確認
   - Integrationがデータベースに招待されているか確認

4. **PDF処理エラー**
   - ファイルが破損していないか確認
   - ファイルサイズが制限内か確認 (デフォルト50MB)

### ログの確認
```bash
tail -f logs/paper_manager.log
```

## ディレクトリ構造
```
PaperManager/
├── app/                    # メインアプリケーション
│   ├── models/            # データモデル
│   ├── services/          # 各種サービス
│   ├── utils/             # ユーティリティ
│   ├── config.py          # 設定管理
│   └── main.py            # メインアプリケーション
├── config/                # 設定ファイル
├── logs/                  # ログファイル
├── pdfs/                  # PDF監視フォルダ (デフォルト)
├── cli.py                 # CLIインターフェース
├── requirements.txt       # 依存関係
└── README.md              # このファイル
```

## ライセンス

MIT License

## 開発者情報

Paper Manager Team