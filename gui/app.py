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
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import config
from app.main import PaperManager
from app.models.paper import ProcessingResult
from app.utils.logger import get_logger

# ページコンポーネントをインポート
from pages.dashboard import render_dashboard
from pages.settings import render_settings
from pages.file_processor import render_file_processor
from pages.logs import render_logs

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
                    return data.get('processed_files', [])
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
            
            # 非同期でシステム開始
            await self.paper_manager.start()
            
        except Exception as e:
            logger.error(f"システム開始エラー: {e}")
            st.error(f"システム開始に失敗しました: {e}")
    
    def _stop_system(self):
        """システム停止"""
        try:
            if self.paper_manager:
                # 停止処理をバックグラウンドで実行
                asyncio.create_task(self.paper_manager.stop())
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
            for file_info in st.session_state.recent_files:
                status_icon = "✅" if file_info.get('success') else "❌"
                file_name = Path(file_info.get('file_path', '')).name
                processed_time = file_info.get('processed_at', '')
                
                if processed_time:
                    try:
                        dt = datetime.fromisoformat(processed_time)
                        time_str = dt.strftime("%H:%M")
                    except:
                        time_str = "不明"
                else:
                    time_str = "不明"
                
                st.markdown(f"{status_icon} **{file_name[:20]}...**")
                st.caption(f"処理時刻: {time_str}")
            
            # 更新ボタン
            if st.button("🔄 データ更新"):
                self._update_stats()
                st.rerun()
    
    def run(self):
        """メインアプリケーション実行"""
        # ヘッダー表示
        self.render_header()
        
        # サイドバー表示
        self.render_sidebar()
        
        # メインコンテンツ
        tab1, tab2, tab3, tab4 = st.tabs(["📊 ダッシュボード", "📄 ファイル処理", "⚙️ 設定", "📋 ログ"])
        
        with tab1:
            render_dashboard()
        
        with tab2:
            render_file_processor()
        
        with tab3:
            render_settings()
        
        with tab4:
            render_logs()
        
        # 定期更新（統計データ）
        if st.session_state.system_running:
            # 30秒ごとに自動更新
            time.sleep(0.1)  # 小さな遅延で負荷軽減

def main():
    """メイン関数"""
    gui = StreamlitGUI()
    gui.run()

if __name__ == "__main__":
    main()