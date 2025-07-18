# 論文管理システム (Paper Manager)

医学論文のPDFファイルを自動解析し、Notionデータベースに登録する完全自動化システムです。

## 機能

- 📄 **PDF自動処理**: フォルダ監視により新しいPDFファイルを自動検出
- 🔍 **テキスト抽出**: Google Cloud Vision APIによる高精度なOCR処理
- 🤖 **AI解析**: Gemini 2.5 Proによる論文メタデータ抽出と1900文字以内の構造化された日本語要約
- 🔬 **PubMed連携**: 高精度PMID検索（6段階検索戦略）とPubMedリンク生成
- 📊 **メタデータ統合**: PubMedから正確なメタデータを取得し、Geminiの結果と統合
- 📚 **Notion統合**: 構造化されたデータベースへの自動投稿（重複チェック機能付き）
- 📁 **PDFアップロード**: 論文タイトルでリネームしたPDFファイルを自動アップロード
- ⚡ **並行処理**: 複数ファイルの同時処理対応（最大3ファイル）
- 🗂️ **自動ファイル管理**: 処理済みPDFの自動移動・整理・アーカイブ

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
- ファイル処理設定 (最大サイズ50MB、並行数3など)
- Gemini AI設定 (モデル: gemini-2.5-pro、温度0.1、トークン数8192など)
- PubMed検索設定 (5段階検索戦略、API制限対応)
- Vision API設定 (言語ヒント、リトライ設定など)
- ログ設定 (カラーログ、ローテーション設定)

### config/article_template.json
Notion投稿用のテンプレート (自動使用)

## ログ

- コンソール出力: カラー付きログ
- ファイル出力: `logs/paper_manager.log` (ローテーション対応)

## 処理フロー

1. **ファイル検出**: 監視フォルダ内の新しいPDFを自動検出
2. **PDF処理**: Google Cloud Vision APIによる高精度なテキスト抽出
3. **論文解析**: Gemini 2.5 Proでメタデータ抽出と1900文字以内の構造化された日本語要約作成
4. **PubMed検索**: 6段階検索戦略による高精度PMID検索
   - DOI検索（最優先）
   - 短縮タイトル + 著者 + 年
   - 緩い条件検索（年なし）
   - 年度範囲を柔軟にした検索（±2年）
   - 著者 + キーワード検索
   - タイトルのみ検索
5. **PubMedメタデータ統合**: PMID取得成功時に正確なメタデータを取得・統合
6. **重複チェック**: Notion内の既存記事確認
7. **PDFアップロード**: 論文タイトルでリネームしたPDFファイルをNotionにアップロード
8. **データ投稿**: Notionデータベースにページ作成
9. **ファイル移動**: 処理済みPDFを`processed_pdfs`フォルダに自動移動・整理

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

## 主要な技術的特徴

### 高精度PubMed検索システム
- **6段階検索戦略**: 確実性の高い順序でPMID検索を実行
- **DOI最優先検索**: DOIがある場合は複数の方法で検索
- **年度範囲柔軟化**: ±2年の範囲で検索
- **動的タイトル短縮**: 長いタイトルでも確実に検索
- **複数著者対応**: 上位5人の著者で順次検索
- **医学用語優先**: 専門用語を優先的にキーワード化
- **カンマ問題対応**: Notionで無効な文字を自動処理
- **API制限対応**: 自動レート制限とリトライ機能

### PubMedメタデータ統合
- **正確なメタデータ**: PubMedから取得した公式データを優先使用
- **包括的情報**: タイトル、著者、雑誌、DOI、MeSH用語、抄録を取得
- **データマージ**: GeminiとPubMedの結果を適切に統合
- **品質保証**: 査読済み論文の標準化された情報

### 高度な要約生成
- **厳密な文字数制限**: 1900文字以内の厳守
- **構造化された内容**: 背景・目的・方法・結果・結論・意義を含む
- **常体での出力**: 簡潔で読みやすい文体
- **プレフィックス除去**: 不要な説明文を自動除去
- **文境界での切り詰め**: 自然な文で終わる要約

### PDFアップロード機能
- **論文タイトルリネーム**: 元のファイル名を論文タイトルに変更
- **ファイル名サニタイゼーション**: 無効文字を全角文字に自動変換
- **Notion File Upload API**: 3段階のアップロード処理
- **サイズ制限対応**: 最大50MBまでのファイルをサポート
- **重複処理**: 既存ファイルの自動検出と処理スキップ

### 堅牢性とパフォーマンス
- **非同期処理**: 最大3ファイルの並行処理
- **包括的エラーハンドリング**: 各APIのリトライ機能
- **自動ファイル管理**: 処理済みファイルの自動移動・整理
- **詳細ログ**: カラー付きコンソール出力とファイルローテーション

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

## 更新履歴

### v1.0.0 (2024-12-17)
- ✅ 初回リリース
- ✅ 基本的な論文処理機能
- ✅ Gemini 2.5 Pro統合
- ✅ PubMed検索機能
- ✅ Notion自動投稿

### v1.1.0 (2024-12-18)
- ✅ 高精度PubMed検索システム（6段階戦略）
- ✅ PubMedメタデータ統合機能
- ✅ 要約生成の大幅改善（1900文字制限、常体出力）
- ✅ 包括的エラーハンドリング
- ✅ 自動ファイル管理システム

### v1.2.0 (2024-12-18)
- ✅ Notion PDFアップロード機能実装
- ✅ 論文タイトルでのファイル名自動変更
- ✅ PubMed検索精度の大幅向上（DOI最優先、年度範囲柔軟化）
- ✅ メタデータマージ機能の完全実装
- ✅ Notionカンマ問題の自動修正
- ✅ ファイル名サニタイゼーション機能

## 開発者情報

Paper Manager Team  
🤖 Generated with [Claude Code](https://claude.ai/code)

## 貢献

プロジェクトへの貢献を歓迎します！Issue作成やPull Requestをお待ちしています。