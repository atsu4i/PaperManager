# CLAUDE.md - 論文管理システム開発記録

## プロジェクト概要

医学論文のPDFファイルを自動解析し、Notionデータベースに登録するPythonベースの自動化システムです。

### 開発背景
- 手動でのPDFアップロード→Claude解析→Notion投稿の工程を完全自動化
- GASベースのSlack Botの知見を活用しつつ、スタンドアロンアプリケーションとして再設計
- Gemini 2.5 ProとGoogle Cloud Vision APIを活用した高精度な論文解析

## システム構成

### 主要技術スタック
- **言語**: Python 3.8+
- **PDF処理**: PyMuPDF + Google Cloud Vision API
- **AI解析**: Gemini 2.5 Pro
- **PubMed連携**: Biopython
- **Notion連携**: Notion Python SDK
- **ファイル監視**: Watchdog

### アーキテクチャ
```
論文管理システム
├── PDF監視サービス (watchdog)
├── PDF処理サービス (Vision API)
├── 論文解析サービス (Gemini)
├── PubMed検索サービス (Biopython)
├── Notion投稿サービス (Notion SDK)
└── ファイル管理サービス (自動移動・整理)
```

## 実装された機能

### 1. 自動PDF処理
- フォルダ監視による新規PDFファイル検出
- PyMuPDF → Google Cloud Vision API のフォールバック処理
- 50MB制限、並行処理対応（最大3ファイル同時）

### 2. AI解析エンジン
- Gemini 2.5 Proによる論文メタデータ抽出
  - タイトル、著者、雑誌名、DOI等
- 2000-3000文字の構造化された日本語要約自動生成
- 医学論文特化のプロンプト設計

### 3. PubMed統合
- 複数検索戦略による高精度PMID検索
  - タイトル+著者名
  - タイトル+雑誌名
  - DOI検索
  - タイトル単独検索
- 自動PubMedリンク生成

### 4. Notion連携
- 既存テンプレート形式での自動投稿
- 重複チェック機能
- エラーハンドリングとデータ修正

### 5. ファイル管理システム
- 処理済みPDFの自動移動・整理
- 成功/失敗別アーカイブ
- 月別サブフォルダ管理
- 処理状態がわかるファイル命名規則

### 6. 包括的管理機能
- 処理済みファイルデータベース
- システム状態監視
- 古いファイルの自動クリーンアップ
- 詳細ログ機能

## 設定・環境変数

### 必須設定
```env
GEMINI_API_KEY=your_gemini_api_key
NOTION_TOKEN=your_notion_token
NOTION_DATABASE_ID=your_notion_database_id_here
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
```

### オプション設定
```env
PUBMED_EMAIL=your_email@example.com
WATCH_FOLDER=./pdfs
PROCESSED_FOLDER=./processed_pdfs
LOG_LEVEL=INFO
```

## 使用方法

### 基本コマンド
```bash
# 初期セットアップ
python cli.py setup

# 設定確認
python cli.py config

# システム開始（デーモンモード）
python cli.py start

# 単一ファイル処理
python cli.py process paper.pdf

# システム状態確認
python cli.py status

# ファイルクリーンアップ
python cli.py cleanup --days 30
```

### Windows用起動スクリプト
```batch
start.bat  # ダブルクリックで起動
```

## フォルダ構造

```
PaperManager/
├── app/                    # メインアプリケーション
│   ├── models/            # データモデル
│   │   └── paper.py       # 論文データモデル
│   ├── services/          # 各種サービス
│   │   ├── pdf_processor.py      # PDF処理
│   │   ├── gemini_service.py     # Gemini連携
│   │   ├── pubmed_service.py     # PubMed検索
│   │   ├── notion_service.py     # Notion連携
│   │   └── file_watcher.py       # ファイル監視
│   ├── utils/             # ユーティリティ
│   │   ├── logger.py      # ログ設定
│   │   └── file_manager.py # ファイル管理
│   ├── config.py          # 設定管理
│   └── main.py            # メインアプリケーション
├── config/                # 設定ファイル
│   ├── config.yaml        # システム設定
│   └── article_template.json # Notionテンプレート
├── pdfs/                  # PDF監視フォルダ
├── processed_pdfs/        # 処理済みPDF保存先
│   ├── success/          # 成功ファイル
│   ├── failed/           # 失敗ファイル
│   └── backup/           # バックアップ
├── logs/                  # ログファイル
├── cli.py                 # CLIインターフェース
├── start.bat             # Windows起動スクリプト
├── requirements.txt      # 依存関係
├── README.md             # 使用方法
└── CLAUDE.md             # このファイル
```

## 処理フロー

1. **ファイル検出**: `pdfs/`フォルダ内の新規PDFを自動検出
2. **テキスト抽出**: PyMuPDF → Vision API のフォールバック処理
3. **論文解析**: Gemini 2.5 Proで包括的なメタデータ抽出と要約生成
4. **PMID検索**: 複数戦略でPubMed検索実行
5. **重複チェック**: Notion内既存記事の確認
6. **データ投稿**: Notionデータベースへの構造化投稿
7. **ファイル整理**: 処理済みPDFの自動移動・アーカイブ

## エラーハンドリング

### 堅牢性設計
- 各APIのリトライ機能（指数バックオフ）
- データサイズ制限対応（Notion API制限等）
- ファイルロック状態の検出と待機
- 包括的例外処理とログ記録

### フォールバック機能
- PDF処理: PyMuPDF → Vision API
- PubMed検索: 複数検索戦略の段階的実行
- Notion投稿: データ修正とリトライ

## パフォーマンス

### 最適化要素
- 並行処理（最大3ファイル同時）
- 非同期処理（asyncio）
- 適切なAPI制限遵守
- メモリ効率的なPDF処理

### 制限事項
- PDFファイルサイズ: 50MB上限
- 同時処理数: 3ファイル（設定可能）
- Gemini 2.5 Proトークン制限: 8192トークン
- Vision API制限: Google Cloud課金設定依存

## 開発時の技術的判断

### フレームワーク選択理由
**Python選択理由:**
1. PDF処理ライブラリの豊富さ（PyMuPDF、pdfplumber等）
2. Google AI Python SDKでのシームレスなGemini連携
3. Notion公式Pythonクライアントの安定性
4. 非同期処理とファイル監視の実装容易性

### アーキテクチャ設計
**モジュラー設計:**
- 各サービスの独立性確保
- 設定ファイルによる柔軟な調整
- シングルトンパターンでリソース管理

**エラーハンドリング戦略:**
- 段階的フォールバック処理
- 詳細ログによるデバッグ支援
- 処理失敗時のファイル保護

## 将来の拡張可能性

### 機能拡張案
- 他の文書形式対応（Word、PowerPoint等）
- 複数Notionデータベース対応
- Web UI実装
- Docker化
- クラウドデプロイ対応

### 技術的改善案
- ベクトル検索による類似論文検出
- 論文分類・タグ付け自動化
- 引用関係の自動解析
- 多言語対応

## 運用上の考慮事項

### セキュリティ
- API キーの環境変数管理
- ファイルパスの検証
- 一時ファイルの自動削除

### 保守性
- 包括的ログ機能
- 設定ファイルでの動作調整
- CLIツールによる管理機能

### 可用性
- 処理失敗時の自動復旧
- システム状態監視
- ファイル整合性チェック

## 開発完了日
2024年12月17日

---

このシステムにより、医学論文の管理が手動プロセスから完全自動化され、研究効率の大幅な向上を実現します。