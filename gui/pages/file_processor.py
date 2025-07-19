"""
ファイル処理ページ
PDFファイルのドラッグ&ドロップ処理と単一ファイル処理
"""

import streamlit as st
import asyncio
import threading
import time
from pathlib import Path
from typing import Optional, List
import tempfile
import sys
import os

# アプリケーションモジュールをインポート
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.main import PaperManager
from app.models.paper import ProcessingResult
from app.utils.logger import get_logger

logger = get_logger(__name__)

class FileProcessor:
    """ファイル処理クラス"""
    
    def __init__(self):
        self.paper_manager = PaperManager()
        self.processing_results: List[ProcessingResult] = []
    
    async def process_single_file(self, file_path: str) -> ProcessingResult:
        """単一ファイルを処理"""
        try:
            return await self.paper_manager.process_single_file(file_path)
        except Exception as e:
            logger.error(f"ファイル処理エラー: {e}")
            return ProcessingResult(
                success=False,
                error_message=str(e),
                processing_time=0.0
            )

def process_uploaded_file(uploaded_file, progress_bar, status_text):
    """アップロードされたファイルを処理"""
    processor = FileProcessor()
    
    try:
        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            temp_path = tmp_file.name
        
        status_text.text("ファイル処理を開始しています...")
        progress_bar.progress(0.1)
        
        # 非同期処理を同期的に実行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        progress_bar.progress(0.3)
        status_text.text("PDF解析中...")
        
        result = loop.run_until_complete(processor.process_single_file(temp_path))
        
        progress_bar.progress(1.0)
        
        # 一時ファイルを削除
        try:
            os.unlink(temp_path)
        except:
            pass
        
        return result
        
    except Exception as e:
        logger.error(f"アップロードファイル処理エラー: {e}")
        status_text.text(f"エラー: {e}")
        return ProcessingResult(
            success=False,
            error_message=str(e),
            processing_time=0.0
        )

def render_file_processor():
    """ファイル処理ページをレンダリング"""
    st.markdown("## 📄 ファイル処理")
    
    # タブで機能を分割
    tab1, tab2, tab3 = st.tabs(["📤 ファイルアップロード", "📁 フォルダ監視", "📊 処理状況"])
    
    with tab1:
        st.markdown("### 📤 PDFファイルアップロード")
        st.info("PDFファイルをドラッグ&ドロップまたは選択して、即座に処理を開始できます。")
        
        # ファイルアップローダー
        uploaded_file = st.file_uploader(
            "PDFファイルを選択してください",
            type=['pdf'],
            help="最大50MBまでのPDFファイルをアップロードできます"
        )
        
        if uploaded_file is not None:
            # ファイル情報表示
            st.success(f"✅ ファイルが選択されました: **{uploaded_file.name}**")
            
            file_details = {
                "ファイル名": uploaded_file.name,
                "ファイルサイズ": f"{uploaded_file.size / (1024*1024):.2f} MB",
                "ファイルタイプ": uploaded_file.type
            }
            
            col1, col2 = st.columns([1, 1])
            with col1:
                for key, value in file_details.items():
                    st.write(f"**{key}:** {value}")
            
            with col2:
                # ファイルサイズチェック
                max_size_mb = 50
                if uploaded_file.size > max_size_mb * 1024 * 1024:
                    st.error(f"❌ ファイルサイズが制限を超えています（最大: {max_size_mb}MB）")
                else:
                    st.success("✅ ファイルサイズは適切です")
            
            # 処理開始ボタン
            if st.button("🚀 処理を開始", type="primary", disabled=uploaded_file.size > max_size_mb * 1024 * 1024):
                
                # プログレスバーと状態表示
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 処理実行
                with st.spinner("論文を処理中..."):
                    result = process_uploaded_file(uploaded_file, progress_bar, status_text)
                
                # 結果表示
                if result.success:
                    st.success("🎉 処理が正常に完了しました！")
                    
                    # 結果詳細
                    if result.paper_metadata:
                        st.markdown("#### 📋 処理結果")
                        
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            st.write(f"**タイトル:** {result.paper_metadata.title}")
                            if result.paper_metadata.authors:
                                authors_str = ", ".join(result.paper_metadata.authors[:3])
                                if len(result.paper_metadata.authors) > 3:
                                    authors_str += f" 他{len(result.paper_metadata.authors) - 3}名"
                                st.write(f"**著者:** {authors_str}")
                            
                            if result.paper_metadata.journal:
                                st.write(f"**雑誌:** {result.paper_metadata.journal}")
                            
                            if result.paper_metadata.publication_year:
                                st.write(f"**出版年:** {result.paper_metadata.publication_year}")
                            
                            if result.paper_metadata.doi:
                                st.write(f"**DOI:** {result.paper_metadata.doi}")
                        
                        with col2:
                            st.metric("処理時間", f"{result.processing_time:.1f}秒")
                            
                            if result.notion_page_id:
                                notion_url = f"https://www.notion.so/{result.notion_page_id.replace('-', '')}"
                                st.markdown(f"[📄 Notionで開く]({notion_url})")
                            
                            if result.paper_metadata.pmid:
                                pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{result.paper_metadata.pmid}/"
                                st.markdown(f"[🔬 PubMedで開く]({pubmed_url})")
                        
                        # 要約表示（折りたたみ）
                        if result.paper_metadata.summary_japanese:
                            with st.expander("📝 日本語要約を表示"):
                                st.write(result.paper_metadata.summary_japanese)
                
                else:
                    st.error("❌ 処理に失敗しました")
                    
                    if result.error_message:
                        st.error(f"エラー詳細: {result.error_message}")
                    
                    st.markdown("#### 🔧 トラブルシューティング")
                    st.markdown("""
                    - PDFファイルが破損していないか確認してください
                    - ファイルサイズが50MB以下であることを確認してください
                    - API設定が正しく構成されているか「設定」タブで確認してください
                    - ログタブでより詳細なエラー情報を確認してください
                    """)
    
    with tab2:
        st.markdown("### 📁 フォルダ監視")
        st.info("指定したフォルダを監視し、新しいPDFファイルが追加されたら自動的に処理します。")
        
        # 現在の監視設定表示
        watch_folder = config.watch_folder
        processed_folder = config.processed_folder
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📂 監視フォルダ")
            st.code(watch_folder)
            
            if Path(watch_folder).exists():
                st.success("✅ フォルダが存在します")
                
                # フォルダ内のファイル数を表示
                try:
                    pdf_files = list(Path(watch_folder).glob("*.pdf"))
                    st.info(f"📄 PDFファイル数: {len(pdf_files)}件")
                    
                    if pdf_files:
                        st.markdown("**最近のファイル:**")
                        for pdf_file in pdf_files[-3:]:  # 最新3件
                            st.write(f"• {pdf_file.name}")
                
                except Exception as e:
                    st.warning(f"フォルダ情報取得エラー: {e}")
            else:
                st.error("❌ フォルダが存在しません")
                if st.button("📁 フォルダを作成"):
                    try:
                        Path(watch_folder).mkdir(parents=True, exist_ok=True)
                        st.success("フォルダを作成しました")
                        st.rerun()
                    except Exception as e:
                        st.error(f"フォルダ作成エラー: {e}")
        
        with col2:
            st.markdown("#### 📂 処理済みフォルダ")
            st.code(processed_folder)
            
            if Path(processed_folder).exists():
                st.success("✅ フォルダが存在します")
                
                # 処理済みファイル数を表示
                try:
                    success_folder = Path(processed_folder) / "success"
                    failed_folder = Path(processed_folder) / "failed"
                    
                    success_count = len(list(success_folder.glob("**/*.pdf"))) if success_folder.exists() else 0
                    failed_count = len(list(failed_folder.glob("**/*.pdf"))) if failed_folder.exists() else 0
                    
                    st.metric("成功", success_count)
                    st.metric("失敗", failed_count)
                
                except Exception as e:
                    st.warning(f"フォルダ情報取得エラー: {e}")
            else:
                st.error("❌ フォルダが存在しません")
        
        # システム状態
        st.markdown("#### 🔄 監視システム状態")
        
        if st.session_state.get('system_running', False):
            st.success("🟢 フォルダ監視が実行中です")
            st.info("新しいPDFファイルを監視フォルダに配置すると、自動的に処理が開始されます。")
        else:
            st.warning("🟡 フォルダ監視が停止中です")
            st.info("「システム開始」ボタンをクリックして監視を開始してください。")
        
        # 手動フォルダスキャン
        if st.button("🔍 フォルダを手動スキャン"):
            try:
                if Path(watch_folder).exists():
                    pdf_files = list(Path(watch_folder).glob("*.pdf"))
                    if pdf_files:
                        st.success(f"📄 {len(pdf_files)}個のPDFファイルが見つかりました")
                        
                        # ファイル一覧表示
                        for i, pdf_file in enumerate(pdf_files[:10]):  # 最大10件表示
                            st.write(f"{i+1}. {pdf_file.name} ({pdf_file.stat().st_size / (1024*1024):.1f} MB)")
                        
                        if len(pdf_files) > 10:
                            st.info(f"他に{len(pdf_files) - 10}個のファイルがあります")
                    else:
                        st.info("📄 PDFファイルが見つかりませんでした")
                else:
                    st.error("監視フォルダが存在しません")
            except Exception as e:
                st.error(f"スキャンエラー: {e}")
    
    with tab3:
        st.markdown("### 📊 リアルタイム処理状況")
        st.info("現在処理中のファイルや最近の処理状況をリアルタイムで確認できます。")
        
        # 処理中ファイル表示（仮想的な表示）
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🔄 処理中のファイル")
            
            # セッション状態から処理中ファイルを取得（実装簡略化）
            processing_files = st.session_state.get('processing_files', [])
            
            if processing_files:
                for file_info in processing_files:
                    st.write(f"🔄 {file_info['name']}")
                    st.progress(file_info.get('progress', 0.5))
            else:
                st.info("現在処理中のファイルはありません")
        
        with col2:
            st.markdown("#### ⏱️ 処理キュー")
            
            # 処理待ちファイル表示（仮想的）
            queue_files = st.session_state.get('queue_files', [])
            
            if queue_files:
                st.info(f"📄 {len(queue_files)}個のファイルが処理待ちです")
                for i, file_name in enumerate(queue_files[:5]):
                    st.write(f"{i+1}. {file_name}")
            else:
                st.success("処理待ちのファイルはありません")
        
        # リアルタイム統計
        st.markdown("#### 📈 リアルタイム統計")
        
        # 統計メトリクス
        stats = st.session_state.get('processing_stats', {})
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("今日の処理数", stats.get('today_processed', 0))
        
        with col2:
            st.metric("平均処理時間", f"{stats.get('avg_processing_time', 0):.1f}秒")
        
        with col3:
            current_success_rate = 0
            if stats.get('total_processed', 0) > 0:
                current_success_rate = (stats.get('successful', 0) / stats.get('total_processed', 1)) * 100
            st.metric("成功率", f"{current_success_rate:.1f}%")
        
        with col4:
            st.metric("総処理数", stats.get('total_processed', 0))
        
        # 自動更新オプション
        auto_refresh = st.checkbox("10秒ごとに自動更新", value=False)
        
        if auto_refresh:
            import time
            time.sleep(10)
            st.rerun()
        
        # 手動更新ボタン
        if st.button("🔄 表示を更新"):
            st.rerun()