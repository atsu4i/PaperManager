# 論文管理システム (Paper Manager)

医学論文のPDFファイルを自動解析し、Notionデータベースに登録する完全自動化システムです。

## 🚀 何ができるの？

PDFファイルをフォルダに保存するだけで、以下を**完全自動**で実行します：

1. **📄 PDF内容の読み取り** - AIが論文の内容を高精度で読み取り
2. **🤖 論文情報の抽出** - タイトル、著者、雑誌名、要約を自動生成
3. **🔬 PubMed検索** - 論文のPMIDを自動検索してリンクを作成
4. **📚 Notion自動投稿** - 構造化されたデータベースに自動保存
5. **📝 Obsidian連携** - Markdown形式でローカルVaultに保存（オプション）
6. **💬 Slack通知** - 処理完了をSlackでお知らせ（オプション）

## 🎯 対象ユーザー

- **医学研究者・学生** - 論文管理を自動化したい方
- **初心者歓迎** - プログラミング知識不要、GUIで簡単操作
- **Windows ユーザー** - ワンクリックで簡単インストール

## 📋 事前に準備するもの

以下のアカウントを作成してください（すべて無料で始められます）：

### 1. Google アカウント
- **Google Cloud** - PDFの読み取りとAI解析に使用
- 📝 [Google Cloud Console](https://console.cloud.google.com/) でアカウント作成

### 2. Notion アカウント
- **Notion** - 論文データベースの保存先
- 📝 [Notion](https://www.notion.so/) でアカウント作成

### 3. Slack アカウント（オプション）
- **Slack** - 処理完了通知用（任意）
- 📝 [Slack](https://slack.com/) でワークスペース作成

## 🔧 インストール方法

### 🖼️ Windows向け

#### ステップ1: Pythonのインストール

1. [Python公式サイト](https://www.python.org/downloads/)から最新版をダウンロード
2. インストーラーを実行
3. **重要**: 「Add Python to PATH」に必ずチェックを入れる
4. インストール完了

#### ステップ2: Paper Managerのダウンロード

1. [リリースページ](https://github.com/atsu4i/PaperManager/releases)から最新版をダウンロード
2. ZIPファイルを解凍
3. フォルダを適当な場所（デスクトップなど）に配置

#### ステップ3: 自動インストール

**🎉 とっても簡単！バッチファイルをダブルクリックするだけ**

1. `quick_install.bat` をダブルクリック
2. 自動的に必要なプログラムがインストールされます
3. 完了まで2-3分お待ちください

```
📁 PaperManager/
├── quick_install.bat  ← これをダブルクリック！
├── start_gui.bat
└── ...
```

#### ステップ4: GUIの起動

1. `start_gui.bat` をダブルクリック
2. **自動設定チェック**: システムが設定状況を確認します

**✨ 初回起動時の流れ**:
```
start_gui.bat をダブルクリック
    ↓
設定チェック実行
    ↓
┌─ 設定完了済み ─→ メインGUI起動 (http://localhost:8501)
└─ 設定未完了 ──→ 設定ツール起動 (http://localhost:8502)
                    ↓
                設定完了後に start_gui.bat を再実行
```

**🎯 完全自動化されたユーザー体験**:
- 設定が必要な場合は自動的に設定画面を表示
- 設定完了済みの場合は直接メインアプリを起動
- 手動でファイルを確認する必要なし

**⚙️ 手動設定を行いたい場合**:
1. `.env.example` を `.env` にコピー
2. テキストエディタで各API設定を入力
3. `start_gui.bat` を再実行

**🔧 トラブルシューティング**:
- 問題診断: `python debug_startup.py`
- 強制設定モード: `setup_config.bat` を直接実行

### 🍎 Mac向け

#### ステップ1: Pythonの確認

Macには通常Pythonがプリインストールされていますが、最新版を推奨します：

```bash
# Python3のバージョン確認
python3 --version

# 古い場合は最新版をインストール
# Homebrewを使用（推奨）
brew install python@3.11

# または公式サイトからダウンロード
```

#### ステップ2: Paper Managerのダウンロード

1. [リリースページ](https://github.com/atsu4i/PaperManager/releases)から最新版をダウンロード
2. ZIPファイルを解凍
3. フォルダをアプリケーションフォルダまたはホームディレクトリに配置

#### ステップ3: 自動インストール

**🚀 ターミナルで簡単インストール**

1. **ターミナルを開く**: `Cmd + Space` → "ターミナル"と入力
2. **フォルダに移動**:
```bash
cd ~/Desktop/PaperManager  # フォルダの場所に応じて変更
```
3. **自動インストール実行**:
```bash
./quick_install.sh
```

#### ステップ4: GUIの起動

```bash
./start_gui.sh  # 推奨方法
```

**✨ 自動設定チェック機能**:
- 設定が未完了の場合 → 設定ツール自動起動 (`http://localhost:8502`)
- 設定が完了済みの場合 → メインアプリ起動 (`http://localhost:8501`)

**手動設定の場合**:
```bash
cp .env.example .env    # テンプレートをコピー
nano .env              # 設定を編集
./start_gui.sh         # 再起動
```

## ⚙️ API設定方法（GUI画面で設定）

Paper ManagerのGUI画面で「⚙️ 設定」タブを開いて、以下の手順で設定してください。

### Google Cloud の設定

#### 1. プロジェクトの作成
1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. 「プロジェクトを作成」をクリック
3. プロジェクト名を入力（例：`paper-manager`）

#### 2. Vision API の有効化
1. 左メニュー「APIとサービス」→「ライブラリ」
2. 「Cloud Vision API」を検索
3. 「有効にする」をクリック

#### 3. Gemini API キーの取得
1. [Google AI Studio](https://aistudio.google.com/)にアクセス
2. 「Get API key」をクリック
3. APIキーをコピーして、GUI設定画面の「Gemini API Key」に貼り付け

#### 4. モデル選択（コスト最適化）
GUIの「⚙️ 設定」タブで、メタデータ抽出と要約作成に使用するモデルを選択できます。

**推奨設定（コスパ最適）**:
- **メタデータ抽出**: `gemma-3-27b-it`（無料・十分な品質）
- **要約作成**: `gemini-2.5-flash-lite`（低コスト・高品質）

**コスト比較**（年間100論文処理の場合）:
- gemini-2.5-pro のみ: 約¥2,520
- 推奨設定: 約¥50（**98%削減**）

**その他の選択肢**:
- より高品質重視: 要約を `gemini-2.5-flash-preview` に変更（年間¥315）
- 完全無料: 両方を `gemma-3-27b-it` に設定（品質は若干低下）

**重要**: モデル設定を変更した場合は、アプリを再起動してください（ターミナルで`Ctrl+C` → `./start_gui.sh`）

#### 5. サービスアカウントキーの作成
1. Google Cloud Console「APIとサービス」→「認証情報」
2. 「認証情報を作成」→「サービスアカウント」
3. 名前を入力（例：`paper-manager-sa`）
4. 作成後、「キー」タブ→「新しいキーを作成」→「JSON」
5. ダウンロードしたJSONファイルをPaper Managerフォルダに保存
6. GUI設定画面の「Google Cloud認証ファイル」にファイルパスを入力

### Notion の設定

#### 1. Integration の作成
1. [Notion Developers](https://www.notion.so/my-integrations)にアクセス
2. 「New integration」をクリック
3. 名前を入力（例：`Paper Manager`）
4. 作成後、「Internal Integration Token」をコピー
5. GUI設定画面の「Notion Token」に貼り付け

#### 2. データベースの作成
1. Notionで新しいページを作成
2. 「/database」と入力してデータベースを作成
3. 以下のプロパティを追加：

| プロパティ名 | タイプ | 説明 |
|------------|--------|------|
| Title | タイトル | 論文タイトル |
| Authors | マルチセレクト | 著者リスト |
| Journal | セレクト | 雑誌名 |
| Year | 数値 | 出版年 |
| DOI | URL | DOI |
| PMID | 数値 | PubMed ID |
| PubMed | URL | PubMedリンク |
| Summary | テキスト | 日本語要約 |
| pdf | ファイル | PDFファイル |

4. データベース設定で作成したIntegrationを接続
5. データベースURLをコピーして、32文字のIDを抽出
6. GUI設定画面の「Notion Database ID」に入力

### Obsidian の設定（オプション）

Obsidian連携を有効にすると、論文をMarkdown形式でローカル保存できます。

#### 1. Obsidian Vaultの準備
1. [Obsidian](https://obsidian.md/)をインストール（無料）
2. 新しいVaultを作成、または既存のVaultを使用
3. Vaultのパスをメモ（例：`C:\Users\YourName\Documents\ObsidianVault`）

#### 2. Paper Managerでの設定
`.env` ファイルまたはGUI設定画面で以下を設定：

```env
# Obsidian連携を有効化
OBSIDIAN_ENABLED=true

# Obsidian Vaultのパス
OBSIDIAN_VAULT_PATH=C:\Users\YourName\Documents\ObsidianVault

# 年別フォルダで整理（papers/2024/, papers/2025/）
OBSIDIAN_ORGANIZE_BY_YEAR=true

# PDFファイルも保存（attachments/pdfs/）
OBSIDIAN_INCLUDE_PDF=false

# キーワードをObsidianタグとして設定
OBSIDIAN_TAG_KEYWORDS=true
```

#### 3. 自動生成される構造
```
ObsidianVault/
├── papers/
│   ├── 2024/
│   │   └── Smith_2024_Large_Language_Models.md
│   └── 2025/
│       └── Johnson_2025_Clinical_NLP.md
├── attachments/
│   └── pdfs/  # OBSIDIAN_INCLUDE_PDF=true の場合
└── templates/
    └── paper_template.md
```

#### 4. Markdownファイルの内容
- **YAMLフロントマター**: タイトル、著者、タグなどのメタデータ
- **基本情報**: 著者、雑誌、発行年、DOI、PMID
- **要約**: 2000-3000文字の日本語要約
- **キーワードタグ**: `#large-language-models #nlp #clinical-decision-support`
- **関連リンク**: Notion記事へのリンク

#### 5. タグ付けガイドライン
統一されたタグ付けルールに基づいて自動タグ生成：
- **複数形優先**: `large-language-models`、`electronic-health-records`
- **略語併記**: `natural-language-processing` + `nlp` を自動追加
- **年代タグ**: `year-2024`、`year-2025`
- 詳細は `tagging_guidelines.md` を参照

### Slack の設定（オプション）

#### 1. Slack Bot の作成
1. [Slack API](https://api.slack.com/apps)にアクセス
2. 「Create New App」→「From scratch」
3. 「OAuth & Permissions」で以下のスコープを追加：
   - `chat:write`
   - `users:read`
4. 「Install to Workspace」をクリック
5. 「Bot User OAuth Token」をコピー
6. GUI設定画面の「Slack Bot Token」に入力

#### 2. ユーザーIDの取得
1. Slackで自分のプロフィールを開く
2. 「メンバーIDをコピー」
3. GUI設定画面の「Slack User ID」に入力

## 🎮 使い方

### 基本的な使い方（推奨）

#### 1. システムの開始
1. GUIのダッシュボードで「🚀 システム開始」ボタンをクリック
2. 「🟢 システム実行中」と表示されればOK

#### 2. PDFファイルの処理
**方法1: フォルダ監視（推奨）**
1. `pdfs/` フォルダにPDFファイルを保存
2. 自動的に処理が開始されます
3. 処理状況はGUIで確認できます

**方法2: ドラッグ&ドロップ**
1. 「📄 ファイル処理」タブを開く
2. PDFファイルをドラッグ&ドロップ
3. 「🚀 処理を開始」ボタンをクリック

#### 3. 結果の確認
- **Notion**: データベースに自動的に論文情報が追加されます
- **Obsidian**: Markdown形式でVaultに保存されます（有効時）
- **Slack**: 処理完了通知が届きます（設定時）
- **GUI**: ダッシュボードで統計を確認できます

### 📊 処理結果について

#### ファイルの保存場所
```
📁 processed_pdfs/
├── 📁 backup/           # オリジナルファイル名で保持
│   ├── 論文タイトル.pdf
│   └── 別の論文.pdf
├── 📁 success/          # 処理成功（処理情報付き）
│   └── 📁 2025-01/
│       └── ✓_20250120_143022_論文タイトル_a1b2c3d4.pdf
└── 📁 failed/           # 処理失敗（処理情報付き）
    └── 📁 2025-01/
        └── ✗_20250120_143022_論文タイトル.pdf
```

#### 統計情報
- **総処理数**: 処理したファイルの総数
- **成功率**: 正常に処理された割合
- **平均処理時間**: 1ファイルあたりの平均時間
- **今日の処理数**: 本日処理したファイル数

## 🔄 システムの終了方法

### 安全な終了手順
1. **GUIで停止**: 「🛑 システム停止」ボタンをクリック
2. **ブラウザを閉じる**: タブまたはウィンドウを閉じる
3. **コマンドプロンプトを終了**: `Ctrl+C` を押すか、ウィンドウを閉じる

### 注意事項
- 処理中のファイルがある場合は、完了を待ってから終了することを推奨
- 強制終了した場合、次回起動時に未処理ファイルが再処理されます

## 🔧 トラブルシューティング

### よくある問題

#### 1. 「python: command not found」エラー
**解決方法**: Pythonを再インストールし、「Add Python to PATH」をチェック

#### 2. インストールスクリプトが失敗する

**Windows の場合**:
```bash
# コマンドプロンプトで実行
install_gui.bat
```

**Mac の場合**:
```bash
# 実行権限を確認・付与
chmod +x quick_install.sh start_gui.sh

# 再実行
./quick_install.sh
```

#### 3. 文字化けエラー（UnicodeDecodeError）
**解決方法**: 
```bash
# requirements-simple.txt を使用
pip install -r requirements-simple.txt
```

#### 4. GUIが開かない
**解決方法**:
1. コマンドプロンプトで以下を実行：
```bash
cd PaperManager
paper_manager_env\Scripts\activate
python start_gui.py
```
2. ブラウザで `http://localhost:8501` を開く

#### 5. 統計が更新されない
**解決方法**:
1. GUIで「🔄 手動更新」ボタンをクリック
2. システムを一度停止して再開

#### 6. Vision API エラー
**対策**: システムが自動的にエラーを解決します（リトライ機能付き）

#### 7. PDFが処理されない
**確認項目**:
- ファイルサイズが50MB以下か
- PDFが破損していないか
- 他のアプリで開いていないか
- 処理済みデータベースに記録されていないか

**解決方法**:
1. GUI「設定」タブ → 「データベース管理」タブを開く
2. 失敗したファイルの一覧を確認
3. 「失敗したファイルを削除」ボタンをクリック
4. システムを再起動すると再度処理されます

#### 8. Notionエラー「Invalid select option, commas not allowed」
**原因**: Journal名にカンマが含まれている（例: `Healthcare (Basel, Switzerland)`）
**解決方法**: 自動的にカンマをスペースに置き換えて処理されます（v1.6.1以降）

#### 9. Mac特有の問題

**「zsh: permission denied」エラー**:
```bash
# 実行権限を付与
chmod +x quick_install.sh start_gui.sh
```

**Homebrew関連エラー**:
```bash
# Homebrewをインストール
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Python再インストール
brew install python@3.11
```

**「command not found: python」エラー（Mac）**:
```bash
# python3を使用
python3 start_gui.py

# またはエイリアス作成
echo "alias python=python3" >> ~/.zshrc
source ~/.zshrc
```

### ログの確認
詳細なエラー情報は以下で確認できます：

**Windows**:
```bash
type logs\paper_manager.log
```

**Mac**:
```bash
cat logs/paper_manager.log

# リアルタイム監視
tail -f logs/paper_manager.log
```

## 💡 コツとベストプラクティス

### 効率的な使い方
1. **複数ファイル処理**: `pdfs/` フォルダに複数ファイルを配置（1つずつ順次処理でAPI制限を回避）
2. **定期的な監視**: GUIを開いたままにして処理状況を確認
3. **バックアップ活用**: `backup/` フォルダのオリジナルファイルを活用
4. **データベース管理**: GUI「設定」→「データベース管理」で失敗ファイルをリセット

### 設定のコツ
1. **APIキー管理**: GUI設定画面で安全に管理
2. **Notion構造**: データベースプロパティは正確に作成
3. **フォルダ整理**: 月別に自動整理されるため、定期的な確認のみでOK

## 🎯 上級者向け：CLI使用方法

GUIではなくコマンドラインで使用したい場合：

### 基本コマンド

**Windows**:
```bash
# 仮想環境を有効化
paper_manager_env\Scripts\activate

# システム開始（常駐モード）
python cli.py start

# 単一ファイル処理
python cli.py process path/to/paper.pdf

# 設定確認
python cli.py config

# システム状態確認
python cli.py status
```

**Mac**:
```bash
# 仮想環境を有効化
source paper_manager_env/bin/activate

# システム開始（常駐モード）
python cli.py start

# 単一ファイル処理
python cli.py process path/to/paper.pdf

# 設定確認
python cli.py config

# システム状態確認
python cli.py status
```

### NotionからObsidianへの移行

既存のNotionデータベースをObsidianに一括移行する場合：

**Windows**:
```bash
# 全論文を移行
python migrate_notion_to_obsidian.py

# 2024年の論文のみ移行
python migrate_notion_to_obsidian.py --year 2024

# 最初の10件をテスト移行
python migrate_notion_to_obsidian.py --limit 10

# PDFダウンロードをスキップ（高速）
python migrate_notion_to_obsidian.py --skip-download

# 実行前に対象論文を確認
python migrate_notion_to_obsidian.py --dry-run
```

**Mac**:
```bash
# 仮想環境を有効化してから実行
source paper_manager_env/bin/activate
python migrate_notion_to_obsidian.py
```

### 設定ファイル編集
- **環境変数**: `.env` ファイルを直接編集
- **詳細設定**: `config/config.yaml` ファイルを編集

## 📈 システム仕様

### 対応ファイル
- **形式**: PDF
- **最大サイズ**: 50MB
- **言語**: 英語・日本語の論文

### 処理能力
- **同時処理**: 1ファイルずつ順次処理（Gemini APIレート制限対策）
- **処理時間**: 1論文あたり30-60秒
- **精度**: Vision API + Gemini 2.5 Pro による高精度処理
- **安定性**: スレッドセーフなセマフォによる確実な順次処理

### API制限
- **Google Cloud**: 課金設定に依存
- **Notion**: 1秒間に3リクエスト
- **PubMed**: 1秒間に3リクエスト

## 🆕 更新履歴

### v1.6.2 (2025-12-17) - 最新版
- ✅ **Gemini APIコスト最適化** - DOI抽出による早期重複チェック（APIコール削減）
- ✅ **モデル選択機能** - メタデータ抽出と要約作成で異なるモデルを使用可能
  - 推奨設定: メタデータ=gemma-3-27b-it（無料）、要約=gemini-2.5-flash-lite（低コスト）
  - 年間100論文で約¥50、最大98%のコスト削減を実現
- ✅ **要約プロンプト最適化** - flash-lite向けの段階的指示で高品質出力を実現
- ✅ **GUI設定改善** - 設定保存時に再起動警告を表示
- ✅ **モデル動作確認機能** - 起動時ログとGUI接続テストタブで使用中モデルを表示

### v1.6.1 (2025-12-01)
- ✅ **Gemini APIレート制限対策** - スレッドセーフなセマフォによる厳密な順次処理実装
- ✅ **イベントループ問題修正** - GUIバックグラウンド処理の安定化（threading.Semaphore採用）
- ✅ **Notion Journal名エラー修正** - カンマを含むジャーナル名の自動クリーニング
- ✅ **GUIデータベース管理機能** - 設定タブから失敗ファイルのリセットが可能に
- ✅ **処理安定性向上** - 複数ファイルの確実な順次処理を保証

### v1.6.0 (2025-01-24)
- ✅ **Obsidian連携機能** - Markdown形式でローカルVaultに自動保存
- ✅ **統一タグ付けシステム** - tagging_guidelines.mdに基づく自動タグ正規化
- ✅ **Notion→Obsidian移行ツール** - 既存Notionデータの一括移行スクリプト
- ✅ **重複チェック機能** - Notion IDベースの重複検出・スキップ
- ✅ **ファイル名衝突回避** - 異なる論文の自動連番追加

### v1.5.0 (2025-01-20)
- ✅ GUI完全修正（統計リアルタイム更新・エラー解決）
- ✅ 重複処理防止（1ファイル1回処理を保証）
- ✅ オリジナルファイル名保持（backupフォルダ）
- ✅ Windows完全対応（文字エンコーディング問題解決）

### v1.4.0 (2025-01-19)
- ✅ Streamlit GUI実装
- ✅ ダッシュボード・統計機能
- ✅ ドラッグ&ドロップ処理

### v1.3.0 (2025-01-19)
- ✅ Slack通知機能
- ✅ セキュリティ強化

## 🤝 サポート

### 問題が解決しない場合
1. **ログ確認**: `logs/paper_manager.log` でエラー詳細を確認
2. **設定見直し**: GUIの設定タブで各種APIキーを再確認
3. **再インストール**: `quick_install.bat` を再実行

### フィードバック
- GitHubのIssueページで問題報告・機能要望
- 使用例や改善案も歓迎します

## 📄 ライセンス

MIT License

---

**🎉 Paper Manager で論文管理を完全自動化し、研究に集中しましょう！**

🤖 Generated with [Claude Code](https://claude.ai/code)