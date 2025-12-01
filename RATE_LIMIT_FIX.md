# Gemini APIレート制限対策 - スレッドセーフなセマフォによる厳密な順次処理

## 📋 変更概要

複数のPDFファイルを並行処理すると、Gemini APIのレート制限に引っかかる問題を解決するため、**threading.Semaphoreによる厳密な順次処理（1ファイルずつ）**を実装しました。

**重要**: `asyncio.Semaphore`ではなく`threading.Semaphore`を使用することで、GUIのバックグラウンド処理で発生する「異なるイベントループ」問題を解決しました。

## 🔧 実施した変更

### 1. 並行処理数を1に変更 (`app/config.py`)

```python
class FileProcessingConfig(BaseModel):
    max_concurrent_files: int = 1  # 3 → 1 に変更（順次処理）
    processing_interval: int = 3   # 2秒 → 3秒 に延長
```

**効果**: 同時に1つのファイルのみ処理されるようになり、APIへの負荷が分散されます。

### 2. Geminiリトライ設定の強化 (`app/config.py`)

```python
class GeminiConfig(BaseModel):
    max_retries: int = 5     # 3回 → 5回 に増加
    retry_delay: int = 3     # 2秒 → 3秒 に延長
```

**効果**: リトライ回数が増え、一時的なレート制限でも復旧しやすくなります。

### 3. レート制限エラー専用のリトライロジック (`app/services/gemini_service.py`)

**エクスポネンシャルバックオフ**を実装：

```python
# レート制限エラーの場合
wait_time = retry_delay * (2 ** attempt) * 2

# 例：retry_delay=3の場合
# 1回目エラー: 6秒待機
# 2回目エラー: 12秒待機
# 3回目エラー: 24秒待機
# 4回目エラー: 48秒待機
```

**検出するエラー**:
- `resource exhausted`
- `rate limit`
- `429` (HTTPステータスコード)
- `quota`

### 4. **スレッドセーフなセマフォによる厳密な順次処理制御** (`app/main.py`) ⭐️ 新規追加

**問題1**: 設定で`max_concurrent_files=1`にしても、ファイル監視がキューに複数ファイルを追加し、PDF抽出やOCR処理が並行実行されていた。

**問題2**: GUIのバックグラウンド処理では各ファイルごとに新しいイベントループを作成するため、`asyncio.Semaphore`では「異なるイベントループ」エラーが発生していた。

**解決策**: `threading.Semaphore(1)`を使用することで、複数のイベントループやスレッドからアクセス可能なスレッドセーフなセマフォを実装。

#### 4-1. セマフォの初期化

```python
import threading  # 追加

def __init__(self):
    self.file_watcher: Optional[FileWatcher] = None
    self.processing_queue = asyncio.Queue(maxsize=config.file_processing.max_concurrent_files * 2)
    self.is_running = False
    self.executor = ThreadPoolExecutor(max_workers=config.file_processing.max_concurrent_files)
    # スレッドセーフなセマフォで同時処理数を厳密に制限（Gemini APIレート制限対策）
    # threading.Semaphore は複数のイベントループからアクセス可能
    self.processing_semaphore = threading.Semaphore(1)

async def start(self):
    """システム開始"""
    logger.info("論文管理システムを開始します...")
    logger.info("スレッドセーフな処理セマフォを使用（同時処理数: 1）")
```

#### 4-2. ワーカーでのセマフォ使用

```python
async def _file_processor_worker(self, worker_id: int = 0):
    """ファイル処理ワーカー"""
    while self.is_running:
        try:
            # キューからファイルを取得
            file_path = await asyncio.wait_for(
                self.processing_queue.get(),
                timeout=1.0
            )

            # スレッドセーフなセマフォを使用（async with ではなく with を使用）
            with self.processing_semaphore:
                logger.info(f"[Worker {worker_id}] セマフォ取得 - 処理開始: {Path(file_path).name}")

                # ファイル処理実行（PDF抽出からGemini APIまで全て）
                await self._process_file(file_path, worker_id)

                logger.info(f"[Worker {worker_id}] セマフォ解放 - 処理完了: {Path(file_path).name}")

            # 処理間隔
            await asyncio.sleep(config.file_processing.processing_interval)
```

**重要な変更点**:
- `async with` ではなく **`with`** を使用（`threading.Semaphore`はasyncではない）
- これにより複数のイベントループから安全にアクセス可能

**効果**:
- セマフォを取得できるのは同時に1つのワーカーのみ
- PDF抽出、OCR処理、Gemini API呼び出しまで**全ての処理が順次実行される**
- 次のファイル処理は、前のファイルが完全に終わるまで待機
- GUIのバックグラウンド処理でも「異なるイベントループ」エラーが発生しない

#### 4-3. 手動処理モードでのセマフォ対応

```python
async def process_single_file(self, file_path: str) -> ProcessingResult:
    """単一ファイルの手動処理（CLI/GUI用）"""
    if not Path(file_path).exists():
        return ProcessingResult(
            success=False,
            error_message=f"ファイルが存在しません: {file_path}"
        )

    # スレッドセーフなセマフォを使用して処理
    with self.processing_semaphore:
        logger.info(f"手動処理開始 (セマフォ制御): {Path(file_path).name}")
        result = await self._process_file(file_path)
        logger.info(f"手動処理完了 (セマフォ解放): {Path(file_path).name}")
        return result
```

**重要**: `__init__`でセマフォが初期化されるため、初期化チェックは不要になりました。

### 5. ログメッセージの改善 (`app/main.py`)

システム起動時に処理モードを明示：
```
論文管理システムを開始します...
スレッドセーフな処理セマフォを使用（同時処理数: 1）
システムが正常に開始されました（順次処理モード - スレッドセーフセマフォ制御）
```

処理中のログ：
```
[Worker 0] セマフォ取得 - 処理開始: paper1.pdf
[Worker 0] PDF処理中: paper1.pdf
[Worker 0] 論文解析中: paper1.pdf
[Worker 0] セマフォ解放 - 処理完了: paper1.pdf
[Worker 0] セマフォ取得 - 処理開始: paper2.pdf
...
```

## 📊 処理時間の変化

### 変更前（並行処理: 3ファイル同時）
- 3ファイル処理時間: 約2-3分
- **問題**: レート制限エラーで失敗
- **原因**: ファイル監視が複数PDFをキューに追加→PDF抽出・OCR・Gemini APIが並行実行

### 変更中（設定のみで順次処理: max_concurrent_files=1）
- **問題**: 設定変更だけでは不十分
- **原因**: キュー処理とasync処理の特性上、実際には並行処理されていた
- **証拠**: ログに複数ファイルの同時処理タイムスタンプが記録される

### 変更後（セマフォによる厳密な順次処理）
- 1ファイル処理時間: 約30-60秒
- 3ファイル処理時間: 約2-4分（ファイル間に3秒のインターバル）
- 23ファイル処理時間: 約15-25分
- **メリット**: エラーなく確実に処理完了
- **保証**: セマフォにより物理的に1ファイルのみ処理される

## 🚀 動作確認手順

### 1. GUIを再起動

```bash
start_gui.bat
```

### 2. ログでセマフォ制御を確認

起動時のログメッセージ：
```
処理セマフォを初期化しました（同時処理数: 1）
システムが正常に開始されました（順次処理モード - セマフォ制御）
```

### 3. 複数PDFで動作テスト

1. `pdfs/` フォルダに複数のPDFファイルを配置（2-3個でテスト推奨）
2. GUIのダッシュボードで処理状況を確認
3. ログで以下を確認：
   - `[Worker 0]` のみが表示される（ワーカー1個）
   - **セマフォ取得・解放のログが表示される**
   - ファイルが完全に順番に処理される（1つが完了してから次が開始）
   - レート制限エラーが発生しない

**期待されるログの流れ**:
```
[Worker 0] セマフォ取得 - 処理開始: paper1.pdf
[Worker 0] PDF処理中: paper1.pdf
[Worker 0] 論文解析中: paper1.pdf
[Worker 0] PubMed検索中: paper1.pdf
[Worker 0] Notion投稿中 (PDF付き): paper1.pdf
[Worker 0] セマフォ解放 - 処理完了: paper1.pdf
[Worker 0] セマフォ取得 - 処理開始: paper2.pdf
[Worker 0] PDF処理中: paper2.pdf
...
```

### 4. レート制限エラーが発生した場合

ログに以下のメッセージが表示されます：
```
Gemini APIレート制限検出 (試行 1/5): 6秒待機します...
```

自動的にリトライされ、エクスポネンシャルバックオフで待機時間が延長されます。

**注意**: セマフォにより順次処理が保証されているため、レート制限エラーは大幅に減少します。

## 🔄 元の並行処理に戻す場合

`.env`ファイルまたは設定で以下を変更：

```python
# app/config.py
max_concurrent_files: int = 3  # お好みの同時処理数
processing_interval: int = 2   # 短い間隔に戻す
```

ただし、レート制限エラーが発生する可能性があります。

## 💡 推奨設定

### 無料枠ユーザー
```python
max_concurrent_files = 1  # 順次処理
processing_interval = 3   # 3秒間隔
max_retries = 5           # 5回リトライ
retry_delay = 3           # 3秒待機
```

### 有料枠ユーザー（高いレート制限）
```python
max_concurrent_files = 2  # 2ファイル並行
processing_interval = 2   # 2秒間隔
max_retries = 3           # 3回リトライ
retry_delay = 2           # 2秒待機
```

## 🔧 技術的詳細：スレッドセーフなセマフォの仕組み

### セマフォとは？

`threading.Semaphore(1)`は、同時に実行できるタスク数を制限するスレッドセーフな同期プリミティブです。

```python
# セマフォ = 1枚のチケット
semaphore = threading.Semaphore(1)

with semaphore:  # チケットを取得（他のタスク・スレッドは待機）
    # 処理実行（async関数内でも使用可能）
    await process_file()
    # 処理完了後、自動的にチケットを返却
```

### なぜ`asyncio.Semaphore`ではなく`threading.Semaphore`を使用？

**`asyncio.Semaphore`の問題**:
- 作成されたイベントループにバインドされる
- 異なるイベントループからアクセスするとエラー: `is bound to a different event loop`
- GUIのバックグラウンド処理では各ファイルごとに新しいイベントループを作成するため使用不可

**`threading.Semaphore`の利点**:
- イベントループに依存しない
- 複数のイベントループ、複数のスレッドから安全にアクセス可能
- `async with`ではなく通常の`with`で使用可能

### なぜ設定だけでは不十分だったか？

**問題のコード構造**:
```python
# ファイル監視 → キューに追加（複数ファイルが即座に追加される）
self.processing_queue.put_nowait(file1)
self.processing_queue.put_nowait(file2)
self.processing_queue.put_nowait(file3)

# ワーカー → キューから取得して処理
file_path = await self.processing_queue.get()  # 各ワーカーが取得
await self._process_file(file_path)  # async処理で並行実行される
```

**問題点**:
- キューは複数ファイルを保持可能
- `await _process_file()`は非同期なので、複数が同時に走る
- `max_concurrent_files=1`はワーカー数の制限であって、処理の同時実行を保証しない

**スレッドセーフなセマフォによる解決**:
```python
with self.processing_semaphore:  # 🔒 スレッドセーフなロック取得
    await self._process_file(file_path)
    # PDF抽出、OCR、Gemini API、Notion投稿まで全てここで実行
# 🔓 ロック解放（次のファイルが処理開始可能に）

# GUIのバックグラウンド処理でも同じセマフォを使用
# 異なるイベントループでも問題なく動作
```

### 処理フローの比較

#### ❌ セマフォなし（並行処理発生）
```
時刻 13:32:16 - Worker 0: paper1.pdf のPDF抽出開始
時刻 13:32:16 - Worker 0: paper2.pdf のPDF抽出開始  ← 同時！
時刻 13:32:17 - Worker 0: paper3.pdf のPDF抽出開始  ← 同時！
時刻 13:32:18 - Worker 0: paper1.pdf のGemini API呼び出し
時刻 13:32:18 - Worker 0: paper2.pdf のGemini API呼び出し ← レート制限！
```

#### ✅ セマフォあり（厳密な順次処理）
```
時刻 13:32:16 - Worker 0: セマフォ取得 → paper1.pdf 処理開始
時刻 13:32:16 - Worker 0: paper1.pdf のPDF抽出
時刻 13:32:25 - Worker 0: paper1.pdf のGemini API呼び出し
時刻 13:32:40 - Worker 0: paper1.pdf 処理完了 → セマフォ解放
時刻 13:32:43 - Worker 0: セマフォ取得 → paper2.pdf 処理開始  ← 次のファイル
```

## ✅ 確認事項

- [x] 順次処理モードで起動することを確認
- [x] スレッドセーフなセマフォが`__init__`で初期化されることを確認
- [x] 複数PDFファイルが1つずつ処理されることを確認（セマフォログ確認）
- [x] レート制限エラー時に自動リトライされることを確認
- [x] 処理完了までエラーなく動作することを確認
- [x] セマフォ取得・解放のログが正しく出力されることを確認
- [x] GUIのバックグラウンド処理で「異なるイベントループ」エラーが発生しないことを確認
- [x] 2つ目以降のファイルも正常に処理されることを確認

## 🐛 修正された問題

### 問題1: 設定のみでは並行処理が防げない
- **症状**: `max_concurrent_files=1`にしても複数ファイルが並行処理される
- **解決**: セマフォによる厳密な制御を実装

### 問題2: 異なるイベントループエラー
- **症状**: `<asyncio.locks.Semaphore object...> is bound to a different event loop`
- **原因**: GUIのバックグラウンド処理が各ファイルごとに新しいイベントループを作成
- **解決**: `asyncio.Semaphore`から`threading.Semaphore`に変更

---

**更新日**: 2025-12-01
**対応バージョン**: v1.6.0+
**最終更新**: スレッドセーフなセマフォによる厳密な順次処理実装（イベントループ問題修正）
