"""
Paper Manager - Streamlit GUI Application
医学論文管理システムのWebベースGUI
"""

import streamlit as st
import asyncio
import threading
import time
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# アプリケーションコンポーネントをインポート
import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from app.config import config
    from app.main import PaperManager
    from app.models.paper import ProcessingResult
    from app.utils.logger import get_logger
except ImportError as e:
    st.error(f"アプリケーションモジュールのインポートに失敗しました: {e}")
    st.error(f"プロジェクトルート: {project_root}")
    st.error(f"現在のパス: {sys.path}")
    st.stop()

# コンポーネントをインポート
try:
    from gui.components_internal.dashboard import render_dashboard
    from gui.components_internal.settings import render_settings
    from gui.components_internal.file_processor import render_file_processor
    from gui.components_internal.logs import render_logs
except ImportError as e:
    st.error(f"GUIコンポーネントのインポートに失敗しました: {e}")
    st.stop()

logger = get_logger(__name__)

# Streamlit設定
st.set_page_config(
    page_title="Paper Manager",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        color: #1f77b4;
        border-bottom: 2px solid #1f77b4;
        margin-bottom: 2rem;
    }
    .status-success {
        color: #28a745;
        font-weight: bold;
    }
    .status-error {
        color: #dc3545;
        font-weight: bold;
    }
    .status-warning {
        color: #ffc107;
        font-weight: bold;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
        margin: 0.5rem 0;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
    }
</style>
""", unsafe_allow_html=True)

class StreamlitGUI:
    """Streamlit GUI メインクラス"""
    
    def __init__(self):
        self.paper_manager = None
        self.monitoring_thread = None
        self.is_monitoring = False
        
        # セッション状態の初期化
        if 'system_running' not in st.session_state:
            st.session_state.system_running = False
        if 'processing_stats' not in st.session_state:
            st.session_state.processing_stats = self._get_initial_stats()
        if 'recent_files' not in st.session_state:
            st.session_state.recent_files = []
        if 'error_logs' not in st.session_state:
            st.session_state.error_logs = []
    
    def _get_initial_stats(self) -> Dict:
        """初期統計データを取得"""
        return {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'today_processed': 0,
            'avg_processing_time': 0.0
        }
    
    def _load_processing_history(self) -> List[Dict]:
        """処理履歴を読み込み"""
        try:
            history_file = Path(config.processed_files_db)
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # データベース構造に応じて処理
                    if isinstance(data, dict):
                        # 新しい構造: {ファイルパス: 処理情報}
                        history_list = []
                        for file_path, info in data.items():
                            if isinstance(info, dict):
                                # ファイルパスとファイル名を追加
                                info_copy = info.copy()
                                info_copy['file_path'] = file_path
                                info_copy['file_name'] = Path(file_path).name
                                
                                # processed_atがタイムスタンプの場合、ISO形式に変換
                                if 'processed_at' in info_copy and isinstance(info_copy['processed_at'], (int, float)):
                                    info_copy['processed_at'] = datetime.fromtimestamp(info_copy['processed_at']).isoformat()
                                
                                history_list.append(info_copy)
                        return history_list
                    elif isinstance(data, list):
                        # 古い構造: [処理情報...]
                        return data
                    else:
                        logger.warning(f"予期しないデータベース構造: {type(data)}")
                        return []
        except Exception as e:
            logger.error(f"履歴読み込みエラー: {e}")
        return []
    
    def _update_stats(self):
        """統計データを更新"""
        history = self._load_processing_history()
        
        total = len(history)
        successful = len([f for f in history if f.get('success', False)])
        failed = total - successful
        
        # 今日処理したファイル数
        today = datetime.now().date()
        today_files = [
            f for f in history 
            if datetime.fromisoformat(f.get('processed_at', '1970-01-01')).date() == today
        ]
        
        # 平均処理時間
        processing_times = [f.get('processing_time', 0) for f in history if f.get('processing_time')]
        avg_time = sum(processing_times) / len(processing_times) if processing_times else 0
        
        st.session_state.processing_stats = {
            'total_processed': total,
            'successful': successful,
            'failed': failed,
            'today_processed': len(today_files),
            'avg_processing_time': avg_time
        }
        
        # 最近のファイル（最新5件）
        recent = sorted(history, key=lambda x: x.get('processed_at', ''), reverse=True)[:5]
        st.session_state.recent_files = recent
    
    async def _start_system(self):
        """システム開始"""
        try:
            if not self.paper_manager:
                self.paper_manager = PaperManager()
            
            # GUI用に軽量なシステム開始（フォルダ監視のみ）
            await self.paper_manager._check_connections()
            
            # 処理キューを初期化
            self.paper_manager.processing_queue = asyncio.Queue(maxsize=config.file_processing.max_concurrent_files * 2)
            
            # ファイル監視の開始
            from app.services.file_watcher import FileWatcher
            self.paper_manager.file_watcher = FileWatcher(
                watch_folder=config.watch_folder,
                callback=self._on_new_file_gui
            )
            self.paper_manager.file_watcher.start()
            self.paper_manager.is_running = True
            
            logger.info("GUI向けシステムが開始されました（フォルダ監視有効）")
            
        except Exception as e:
            logger.error(f"システム開始エラー: {e}")
            st.error(f"システム開始に失敗しました: {e}")
    
    def _on_new_file_gui(self, file_path: str):
        """GUI向け新ファイル検出コールバック"""
        try:
            # ファイル監視システムで処理済みチェック
            if self.paper_manager.file_watcher and self.paper_manager.file_watcher.is_file_processed(file_path):
                logger.debug(f"処理済みファイルをスキップ: {Path(file_path).name}")
                return
            
            logger.info(f"新しいファイルを検出: {Path(file_path).name}")
            
            # バックグラウンドでファイル処理を実行
            def process_file_background():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(self.paper_manager.process_single_file(file_path))
                    
                    # ファイル監視システムに処理完了を通知
                    if self.paper_manager.file_watcher:
                        self.paper_manager.file_watcher.mark_file_processed(
                            file_path, 
                            result.success, 
                            result.notion_page_id
                        )
                    
                    # 統計を更新
                    self._update_stats()
                    
                    # Streamlitの統計表示も強制更新
                    if hasattr(st.session_state, 'last_stats_update'):
                        st.session_state.last_stats_update = time.time()
                    
                    logger.info(f"ファイル処理完了: {Path(file_path).name}, 成功: {result.success}")
                    
                except Exception as e:
                    logger.error(f"バックグラウンド処理エラー: {e}")
                    
                    # エラーの場合も処理済みとしてマーク（重複防止）
                    if self.paper_manager.file_watcher:
                        self.paper_manager.file_watcher.mark_file_processed(file_path, False)
            
            # 別スレッドで処理実行
            import threading
            thread = threading.Thread(target=process_file_background, daemon=True)
            thread.start()
            
        except Exception as e:
            logger.error(f"新ファイル処理エラー: {e}")
    
    def _stop_system(self):
        """システム停止"""
        try:
            if self.paper_manager:
                # ファイル監視停止
                if self.paper_manager.file_watcher:
                    self.paper_manager.file_watcher.stop()
                self.paper_manager.is_running = False
                self.paper_manager = None
            
            st.session_state.system_running = False
            st.success("システムを停止しました")
            
        except Exception as e:
            logger.error(f"システム停止エラー: {e}")
            st.error(f"システム停止に失敗しました: {e}")
    
    def _start_monitoring_thread(self):
        """監視スレッド開始"""
        if not self.is_monitoring:
            self.is_monitoring = True
            self.monitoring_thread = threading.Thread(target=self._monitor_system, daemon=True)
            self.monitoring_thread.start()
    
    def _monitor_system(self):
        """システム監視（バックグラウンド）"""
        while self.is_monitoring and st.session_state.system_running:
            try:
                self._update_stats()
                time.sleep(5)  # 5秒間隔で更新
            except Exception as e:
                logger.error(f"監視エラー: {e}")
                time.sleep(10)
    
    def render_header(self):
        """ヘッダー表示"""
        st.markdown('<h1 class="main-header">📚 Paper Manager</h1>', unsafe_allow_html=True)
        st.markdown("**医学論文自動管理システム** - AI解析・PubMed検索・Notion投稿を自動実行")
        
        # システム状態表示
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            if st.session_state.system_running:
                st.markdown('<p class="status-success">🟢 システム実行中</p>', unsafe_allow_html=True)
            else:
                st.markdown('<p class="status-error">🔴 システム停止中</p>', unsafe_allow_html=True)
        
        with col2:
            if st.button("🚀 システム開始", disabled=st.session_state.system_running):
                with st.spinner("システムを開始しています..."):
                    try:
                        # 非同期処理を同期的に実行
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self._start_system())
                        
                        st.session_state.system_running = True
                        self._start_monitoring_thread()
                        st.success("システムが正常に開始されました！")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"システム開始に失敗: {e}")
        
        with col3:
            if st.button("🛑 システム停止", disabled=not st.session_state.system_running):
                self._stop_system()
                self.is_monitoring = False
                st.rerun()
    
    def render_sidebar(self):
        """サイドバー表示"""
        with st.sidebar:
            st.markdown("## 📊 システム状態")
            
            # 統計情報
            stats = st.session_state.processing_stats
            
            st.metric("総処理ファイル数", stats['total_processed'])
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("成功", stats['successful'], delta=None)
            with col2:
                st.metric("失敗", stats['failed'], delta=None)
            
            st.metric("今日の処理数", stats['today_processed'])
            st.metric("平均処理時間", f"{stats['avg_processing_time']:.1f}秒")
            
            # 最近の処理ファイル
            st.markdown("## 📄 最近の処理")
            
            recent_files = st.session_state.get('recent_files', [])
            if recent_files:
                for file_info in recent_files[:5]:  # 最新5件のみ表示
                    status_icon = "✅" if file_info.get('success') else "❌"
                    file_path = file_info.get('file_path', '')
                    if file_path:
                        file_name = Path(file_path).name
                    else:
                        file_name = file_info.get('file_name', '不明なファイル')
                    
                    processed_time = file_info.get('processed_at', '')
                    
                    if processed_time:
                        try:
                            if isinstance(processed_time, (int, float)):
                                dt = datetime.fromtimestamp(processed_time)
                            else:
                                dt = datetime.fromisoformat(processed_time)
                            time_str = dt.strftime("%H:%M")
                        except:
                            time_str = "不明"
                    else:
                        time_str = "不明"
                    
                    # ファイル名を適切な長さで表示
                    display_name = file_name[:20] + "..." if len(file_name) > 20 else file_name
                    st.markdown(f"{status_icon} **{display_name}**")
                    st.caption(f"処理時刻: {time_str}")
            else:
                st.info("処理されたファイルはまだありません")
            
            # 更新ボタンと自動更新状態
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 手動更新"):
                    self._update_stats()
                    st.rerun()
            with col2:
                if st.session_state.system_running:
                    st.success("自動更新中")
                else:
                    st.warning("手動更新のみ")
    
    def run(self):
        """メインアプリケーション実行"""
        # ヘッダー表示
        self.render_header()
        
        # サイドバー表示
        self.render_sidebar()
        
        # メインコンテンツ
        tab1, tab2, tab3, tab4 = st.tabs(["📊 ダッシュボード", "📄 ファイル処理", "⚙️ 設定", "📋 ログ"])
        
        with tab1:
            try:
                render_dashboard()
            except Exception as e:
                st.error(f"ダッシュボード表示エラー: {e}")
                logger.error(f"ダッシュボード表示エラー: {e}")
        
        with tab2:
            try:
                render_file_processor()
            except Exception as e:
                st.error(f"ファイル処理ページ表示エラー: {e}")
                logger.error(f"ファイル処理ページ表示エラー: {e}")
        
        with tab3:
            try:
                render_settings()
            except Exception as e:
                st.error(f"設定ページ表示エラー: {e}")
                logger.error(f"設定ページ表示エラー: {e}")
        
        with tab4:
            try:
                render_logs()
            except Exception as e:
                st.error(f"ログページ表示エラー: {e}")
                logger.error(f"ログページ表示エラー: {e}")
        
        # 定期更新（統計データ）
        if st.session_state.system_running:
            # 統計の定期更新（10秒ごと）
            current_time = time.time()
            last_update = st.session_state.get('last_stats_update', 0)
            
            if current_time - last_update > 10:  # 10秒ごと
                self._update_stats()
                st.session_state.last_stats_update = current_time
                time.sleep(0.5)  # 短い遅延でUIを更新
                st.rerun()

def main():
    """メイン関数"""
    gui = StreamlitGUI()
    gui.run()

if __name__ == "__main__":
    main()