# 論文管理システム (Paper Manager)

医学論文のPDFファイルを自動解析し、Notionデータベースに登録する完全自動化システムです。

## 概要

このシステムは、医学論文のPDFファイルをフォルダに保存するだけで、以下の処理を自動実行します：

1. **PDF内容の自動読み取り** - Google Cloud Vision APIで高精度にテキストを抽出
2. **AI論文解析** - Gemini 2.5 Proで論文情報を自動抽出・要約
3. **PubMed検索** - 論文のPMIDを自動検索してリンクを生成
4. **Notion自動投稿** - 構造化されたデータとPDFファイルをNotionに投稿
5. **Slack通知** - 処理完了時にSlackでお知らせ

## 主な機能

- 📄 **PDF自動処理**: フォルダ監視により新しいPDFファイルを自動検出
- 🔍 **高精度テキスト抽出**: Google Cloud Vision APIによるOCR処理
- 🤖 **AI論文解析**: Gemini 2.5 Proによる論文メタデータ抽出と日本語要約生成
- 🔬 **PubMed統合**: 高精度PMID検索（6段階検索戦略）とPubMedリンク生成
- 📊 **メタデータ統合**: PubMedから正確なメタデータを取得し、AIの結果と統合
- 📚 **Notion統合**: 構造化されたデータベースへの自動投稿（重複チェック機能付き）
- 📁 **PDFアップロード**: 論文タイトルでリネームしたPDFファイルを自動アップロード
- 💬 **Slack通知**: 処理完了時の自動通知（成功・失敗・重複検出）
- ⚡ **並行処理**: 複数ファイルの同時処理対応（最大3ファイル）
- 🗂️ **自動ファイル管理**: 処理済みPDFの自動移動・整理・アーカイブ

## システム要件

- **Windows 10/11** または **macOS** または **Linux**
- **Python 3.8以上**
- **インターネット接続** （各種API利用のため）

## 事前準備（APIアカウント設定）

このシステムを使用するには、以下のAPIアカウントが必要です：

### 1. Google Cloud アカウント
- **Google Cloud Vision API** (PDF読み取り用)
- **Gemini API** (AI解析用)

### 2. Notion アカウント
- **Notion API** (データベース投稿用)

### 3. Slack アカウント（オプション）
- **Slack Bot** (通知用、任意)

## 詳細インストール手順

### ステップ1: Pythonのインストール

#### Windows の場合:
1. [Python公式サイト](https://www.python.org/downloads/)から最新版をダウンロード
2. インストーラーを実行し、**「Add Python to PATH」にチェック**を入れる
3. コマンドプロンプトで確認: `python --version`

#### macOS の場合:
```bash
# Homebrewを使用（推奨）
brew install python@3.11

# または公式サイトからダウンロード
```

#### Linux の場合:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv

# CentOS/RHEL
sudo yum install python3 python3-pip
```

### ステップ2: プロジェクトのダウンロード

#### コマンドプロンプト/ターミナルを開く:
- **Windows**: スタートメニューで「cmd」と検索
- **macOS**: Spotlight で「ターミナル」と検索
- **Linux**: Ctrl+Alt+T

#### プロジェクトをダウンロード:
```bash
# 作業フォルダに移動（例：デスクトップ）
cd Desktop

# プロジェクトをクローン
git clone https://github.com/your-username/PaperManager.git
cd PaperManager
```

### ステップ3: 仮想環境の作成と有効化

仮想環境を使用することで、他のPythonプロジェクトと干渉せずに済みます。

#### Windows の場合:
```cmd
# 仮想環境を作成
python -m venv paper_manager_env

# 仮想環境を有効化
paper_manager_env\Scripts\activate

# 有効化されると、プロンプトに (paper_manager_env) が表示されます
```

#### macOS/Linux の場合:
```bash
# 仮想環境を作成
python3 -m venv paper_manager_env

# 仮想環境を有効化
source paper_manager_env/bin/activate

# 有効化されると、プロンプトに (paper_manager_env) が表示されます
```

### ステップ4: 必要なライブラリのインストール

```bash
# 仮想環境が有効化されていることを確認してから実行
pip install -r requirements.txt
```

### ステップ5: 初期セットアップ

```bash
# フォルダ構造とサンプル設定ファイルを作成
python cli.py setup
```

## API設定手順

### Google Cloud 設定

#### 1. Google Cloud プロジェクトの作成
1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. 「プロジェクトを作成」をクリック
3. プロジェクト名を入力（例：「paper-manager」）
4. 作成をクリック

#### 2. Vision API の有効化
1. 左メニューの「APIとサービス」→「ライブラリ」
2. 「Cloud Vision API」を検索
3. 「有効にする」をクリック

#### 3. サービスアカウントキーの作成
1. 左メニューの「APIとサービス」→「認証情報」
2. 「認証情報を作成」→「サービスアカウント」
3. サービスアカウント名を入力（例：「paper-manager-sa」）
4. 作成をクリック
5. 作成されたサービスアカウントをクリック
6. 「キー」タブ→「キーを追加」→「新しいキーを作成」
7. JSON形式を選択してダウンロード
8. ダウンロードしたファイルをプロジェクトフォルダに保存（例：`credentials.json`）

#### 4. Gemini API の設定
1. [Google AI Studio](https://aistudio.google.com/)にアクセス
2. 「Get API key」をクリック
3. APIキーを生成してコピー

### Notion 設定

#### 1. Notion Integration の作成
1. [Notion Developers](https://www.notion.so/my-integrations)にアクセス
2. 「New integration」をクリック
3. 名前を入力（例：「Paper Manager」）
4. ワークスペースを選択
5. 「Submit」をクリック
6. 「Internal Integration Token」をコピー

#### 2. データベースの準備
1. Notionで論文管理用のデータベースを作成
2. 以下のプロパティを追加:
   - `Title` (タイトル)
   - `Authors` (マルチセレクト)
   - `Journal` (セレクト)
   - `Year` (数値)
   - `DOI` (URL)
   - `PMID` (数値)
   - `PubMed` (URL)
   - `Summary` (テキスト)
   - `pdf` (ファイル)
3. データベースの「設定」→「コネクト」から作成したIntegrationを追加
4. データベースURLからIDをコピー（32文字の文字列）

### Slack 設定（オプション）

#### 1. Slack Bot の作成
1. [Slack API](https://api.slack.com/apps)にアクセス
2. 「Create New App」→「From scratch」
3. App名とワークスペースを選択
4. 「OAuth & Permissions」→「Bot Token Scopes」に以下を追加:
   - `chat:write`
   - `users:read`
5. 「Install to Workspace」をクリック
6. 「Bot User OAuth Token」（`xoxb-`で始まる）をコピー

#### 2. ユーザーIDの取得
1. Slackアプリで自分のプロフィールを開く
2. 「その他」→「メンバーIDをコピー」
3. `U`で始まる文字列をコピー

## 環境変数の設定

プロジェクトフォルダに `.env` ファイルを作成し、以下を記入:

```env
# Google Cloud 認証（ダウンロードしたJSONファイルのパス）
GOOGLE_APPLICATION_CREDENTIALS=./credentials.json

# Gemini API Key
GEMINI_API_KEY=your_gemini_api_key_here

# Notion API
NOTION_TOKEN=your_notion_token_here
NOTION_DATABASE_ID=your_database_id_here

# PubMed API (任意)
PUBMED_EMAIL=your_email@example.com

# Slack通知（任意）
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_USER_ID_TO_DM=U12345ABCDE

# フォルダ設定
WATCH_FOLDER=./pdfs
PROCESSED_FOLDER=./processed_pdfs

# ログレベル
LOG_LEVEL=INFO
```

## Slack通知の設定

### config.yaml でのSlack設定

`config/config.yaml` ファイルを編集してSlack通知を有効化:

```yaml
slack:
  enabled: true  # 通知を有効にする
  # 通知レベル設定
  notify_success: true   # 成功時の通知
  notify_failure: true   # 失敗時の通知
  notify_duplicate: false  # 重複検出時の通知
  # メッセージ設定
  include_summary: false  # 要約をメッセージに含めるか
  max_message_length: 1000  # メッセージの最大長
```

### 通知内容

- **成功通知**: 論文処理完了時に論文情報とNotionリンクを送信
- **失敗通知**: エラー発生時にファイル名とエラー詳細を送信
- **重複通知**: 既存論文検出時にお知らせ（任意）

## 使用方法

### 準備: 仮想環境の有効化

毎回使用する前に、仮想環境を有効化してください：

#### Windows:
```cmd
cd PaperManager
paper_manager_env\Scripts\activate
```

#### macOS/Linux:
```bash
cd PaperManager
source paper_manager_env/bin/activate
```

### 設定チェック

まず設定が正しく読み込まれているか確認:

```bash
python cli.py config
```

### 基本的な使用方法

#### 🖥️ GUI版（推奨・初心者向け）
**Webブラウザで使える直感的なインターフェース:**

```bash
# Windows の場合
start_gui.bat

# macOS/Linux の場合
./start_gui.sh

# または直接実行
python start_gui.py
```

ブラウザで `http://localhost:8501` が自動的に開きます。

**GUI機能:**
- 📊 **ダッシュボード**: リアルタイム統計とグラフ表示
- 📄 **ファイル処理**: ドラッグ&ドロップでPDF処理
- ⚙️ **設定管理**: 直感的なAPI設定フォーム
- 📋 **ログ監視**: リアルタイムログ表示と検索

#### 💻 CLI版（上級者向け）

#### 1. 自動監視モード
システムを常駐させてPDFフォルダを監視:

```bash
python cli.py start
```

PDFファイルを `pdfs/` フォルダに保存するだけで自動処理されます。

#### 2. 単一ファイル処理
特定のPDFファイルを手動で処理:

```bash
python cli.py process path/to/your/paper.pdf
```

#### 3. 複数ファイル一括処理
フォルダ内の全PDFを一度に処理:

```bash
# pdfsフォルダ内のすべてのPDFを処理
python cli.py process ./pdfs/
```

### 便利なコマンド

#### システム状態確認
```bash
python cli.py status
```

#### 古いファイルのクリーンアップ
```bash
# 30日以前のバックアップファイルを削除
python cli.py cleanup --days 30
```

#### ログの確認
```bash
# リアルタイムでログを表示（Windowsの場合）
type logs\paper_manager.log

# macOS/Linuxの場合
tail -f logs/paper_manager.log
```

## 処理フロー

システムが実行する処理の流れ:

1. **ファイル検出**: 監視フォルダ内の新しいPDFを自動検出
2. **PDF処理**: Google Cloud Vision APIでテキストを高精度抽出
3. **AI解析**: Gemini 2.5 Proで以下を自動生成:
   - 論文タイトル
   - 著者リスト
   - 雑誌名・出版年
   - DOI
   - 構造化された日本語要約（2000-3000文字）
4. **PubMed検索**: 6段階の検索戦略でPMIDを検索:
   - DOI検索（最優先）
   - タイトル + 著者 + 年検索
   - 緩い条件検索
   - 年度範囲柔軟検索（±2年）
   - 著者 + キーワード検索
   - タイトルのみ検索
5. **メタデータ統合**: PubMedから正確なメタデータを取得・統合
6. **重複チェック**: Notion内の既存記事を確認
7. **PDFアップロード**: 論文タイトルでリネームしてNotionにアップロード
8. **データ投稿**: Notionデータベースに構造化データで投稿
9. **Slack通知**: 処理完了をSlackで通知
10. **ファイル移動**: 処理済みPDFを `processed_pdfs/` に自動移動・整理

## フォルダ構造

システム実行後の構造:

```
PaperManager/
├── pdfs/                   # PDF監視フォルダ（ここにPDFを配置）
├── processed_pdfs/         # 処理済みPDFの保存先
│   ├── success/           # 正常処理されたPDF
│   │   └── 2024-12/      # 月別サブフォルダ
│   ├── failed/            # 処理失敗したPDF
│   │   └── 2024-12/
│   └── backup/            # バックアップファイル
├── logs/                  # ログファイル
│   └── paper_manager.log
├── paper_manager_env/     # Python仮想環境
├── credentials.json       # Google Cloud認証ファイル
├── .env                   # 環境変数設定
└── processed_files.json   # 処理済みファイル管理DB
```

## トラブルシューティング

### よくある問題と解決方法

#### 1. 「python: command not found」エラー
**原因**: Pythonがインストールされていない、またはPATHが通っていない  
**解決方法**: 
- Pythonを再インストールし、インストール時に「Add Python to PATH」をチェック
- macOSの場合: `python3` コマンドを使用

#### 2. 「pip: command not found」エラー
**解決方法**:
```bash
# Windowsの場合
python -m pip --version

# macOS/Linuxの場合
python3 -m pip --version
```

#### 3. Vision API認証エラー
**原因**: Google Cloud認証設定の問題  
**確認項目**:
- `.env` ファイルの `GOOGLE_APPLICATION_CREDENTIALS` パスが正しいか
- JSONファイルが存在するか
- Vision APIが有効化されているか
- Google Cloudプロジェクトの課金が有効か

#### 4. Gemini API エラー
**確認項目**:
- APIキーが正しいか
- API使用量の制限に達していないか
- インターネット接続が安定しているか

#### 5. Notion API エラー
**確認項目**:
- トークンが正しいか
- データベースIDが正しいか
- IntegrationがデータベースにConnectされているか
- データベースのプロパティ名が正しいか

#### 6. Slack通知が届かない
**確認項目**:
- Slack Botトークンが正しいか（`xoxb-`で始まる）
- ユーザーIDが正しいか（`U`で始まる）
- BotがワークスペースにInstallされているか
- `config.yaml` で `enabled: true` になっているか

#### 7. PDF処理エラー
**確認項目**:
- PDFファイルが破損していないか
- ファイルサイズが50MB以下か
- ファイルが使用中でないか（他のアプリで開いていないか）

#### 8. GUI起動エラー
**原因**: Streamlitがインストールされていない、または仮想環境の問題  
**解決方法**:
```bash
# 1. 仮想環境を有効化
# Windows
paper_manager_env\Scripts\activate

# macOS/Linux  
source paper_manager_env/bin/activate

# 2. GUI関連パッケージをインストール
pip install streamlit plotly

# 3. GUIを起動
python start_gui.py
```

**簡単インストール（Windows）**:
```bash
install_gui.bat  # 依存関係を自動インストール
```

### ログの確認方法

詳細なエラー情報は以下で確認できます:

```bash
# 最新のログを確認
# Windows
type logs\paper_manager.log

# macOS/Linux
cat logs/paper_manager.log

# リアルタイム監視（macOS/Linux）
tail -f logs/paper_manager.log
```

### サポート情報

- **ログファイル**: `logs/paper_manager.log`
- **設定ファイル**: `config/config.yaml`
- **処理済み管理**: `processed_files.json`

## 高度な設定

### カスタム設定

`config/config.yaml` で詳細設定をカスタマイズできます:

```yaml
# ファイル処理設定
file_processing:
  max_pdf_size: 50        # PDF最大サイズ (MB)
  max_concurrent_files: 3  # 同時処理数
  processing_interval: 2   # 処理間隔 (秒)

# AI解析設定
gemini:
  model: "gemini-2.5-pro"  # 使用モデル
  temperature: 0.1         # 回答の創造性 (0-1)
  max_tokens: 8192        # 最大トークン数

# PubMed検索設定
pubmed:
  timeout: 30             # 検索タイムアウト (秒)
  max_retries: 3          # リトライ回数
  max_results: 10         # 検索結果最大数
```

### Windows用起動スクリプト

毎回コマンドを入力するのが面倒な場合、`start.bat` ファイルを作成:

```batch
@echo off
cd /d "%~dp0"
call paper_manager_env\Scripts\activate
python cli.py start
pause
```

ダブルクリックで起動できます。

## 更新履歴

### v1.4.0 (2025-01-19) - 最新版
- ✅ **Streamlit GUI実装**: 直感的なWebベースインターフェース追加
- ✅ **ダッシュボード機能**: リアルタイム統計・グラフ表示
- ✅ **ドラッグ&ドロップ**: PDFファイルの簡単アップロード処理
- ✅ **設定管理GUI**: API設定の視覚的管理画面
- ✅ **ログ監視機能**: リアルタイムログ表示と検索
- ✅ **ワンクリック起動**: バッチファイルでの簡単起動

### v1.3.0 (2025-01-19)
- ✅ **Slack通知機能追加**: 論文処理完了時の自動通知
- ✅ **セキュリティ改善**: Slack認証情報を環境変数で管理
- ✅ **初心者向け手順**: 詳細なインストール・設定ガイド追加
- ✅ **仮想環境対応**: Python環境分離による安定性向上

### v1.2.0 (2024-12-18)
- ✅ Notion PDFアップロード機能実装
- ✅ 論文タイトルでのファイル名自動変更
- ✅ PubMed検索精度の大幅向上（DOI最優先、年度範囲柔軟化）
- ✅ メタデータマージ機能の完全実装
- ✅ ファイル名サニタイゼーション機能

### v1.1.0 (2024-12-18)
- ✅ 高精度PubMed検索システム（6段階戦略）
- ✅ PubMedメタデータ統合機能
- ✅ 要約生成の大幅改善（文字数制限、常体出力）
- ✅ 包括的エラーハンドリング
- ✅ 自動ファイル管理システム

### v1.0.0 (2024-12-17)
- ✅ 初回リリース
- ✅ 基本的な論文処理機能
- ✅ Gemini 2.5 Pro統合
- ✅ PubMed検索機能
- ✅ Notion自動投稿

## 技術仕様

### 対応ファイル形式
- **PDF**: 最大50MB、テキスト抽出可能なファイル

### API制限
- **Vision API**: Google Cloud課金設定に依存
- **Gemini API**: 1分間あたりのリクエスト制限あり
- **Notion API**: 1秒間に3リクエストまで
- **PubMed API**: 1秒間に3リクエストまで（自動調整）

### パフォーマンス
- **処理速度**: 1論文あたり30-60秒（API応答時間に依存）
- **並行処理**: 最大3ファイル同時処理
- **メモリ使用量**: 約200-500MB（PDFサイズに依存）

## サポート・フィードバック

### 問題報告
- GitHubのIssueページで報告
- ログファイルを添付してください

### 機能要望
- 新機能のリクエストも歓迎します
- 使用例と具体的な要望を記載してください

## ライセンス

MIT License

## 謝辞

このプロジェクトは以下の技術を活用しています：
- Google Cloud Vision API
- Google Gemini API
- Notion API
- Slack API
- PubMed/NCBI API

🤖 Generated with [Claude Code](https://claude.ai/code)

---

**🎉 Paper Manager で論文管理を自動化し、研究効率を大幅に向上させましょう！**