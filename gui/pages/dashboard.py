"""
ダッシュボードページ
システム状態の可視化と統計情報の表示
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
import sys
import os

# アプリケーションモジュールをインポート
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__)

def load_processing_history() -> List[Dict]:
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

def create_success_rate_chart(history: List[Dict]) -> go.Figure:
    """成功率のチャート作成"""
    if not history:
        fig = go.Figure()
        fig.add_annotation(
            text="データがありません",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            title="処理成功率",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        return fig
    
    successful = len([f for f in history if f.get('success', False)])
    failed = len(history) - successful
    
    labels = ['成功', '失敗']
    values = [successful, failed]
    colors = ['#28a745', '#dc3545']
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        marker_colors=colors,
        textinfo='label+percent+value',
        textfont_size=12
    )])
    
    fig.update_layout(
        title="処理成功率",
        font=dict(size=14),
        showlegend=True,
        height=400
    )
    
    return fig

def create_daily_processing_chart(history: List[Dict]) -> go.Figure:
    """日別処理数のチャート作成"""
    if not history:
        fig = go.Figure()
        fig.add_annotation(
            text="データがありません",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            title="日別処理数",
            xaxis_title="日付",
            yaxis_title="処理数"
        )
        return fig
    
    # 過去30日のデータを準備
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=29)
    
    # 日付別に集計
    daily_counts = {}
    for i in range(30):
        date = start_date + timedelta(days=i)
        daily_counts[date] = {'successful': 0, 'failed': 0}
    
    for file_info in history:
        try:
            processed_date = datetime.fromisoformat(file_info.get('processed_at', '1970-01-01')).date()
            if start_date <= processed_date <= end_date:
                if file_info.get('success', False):
                    daily_counts[processed_date]['successful'] += 1
                else:
                    daily_counts[processed_date]['failed'] += 1
        except:
            continue
    
    # データフレーム作成
    dates = list(daily_counts.keys())
    successful_counts = [daily_counts[date]['successful'] for date in dates]
    failed_counts = [daily_counts[date]['failed'] for date in dates]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=dates,
        y=successful_counts,
        name='成功',
        marker_color='#28a745'
    ))
    
    fig.add_trace(go.Bar(
        x=dates,
        y=failed_counts,
        name='失敗',
        marker_color='#dc3545'
    ))
    
    fig.update_layout(
        title="日別処理数（過去30日）",
        xaxis_title="日付",
        yaxis_title="処理数",
        barmode='stack',
        height=400,
        showlegend=True
    )
    
    return fig

def create_processing_time_chart(history: List[Dict]) -> go.Figure:
    """処理時間の分布チャート作成"""
    processing_times = [
        f.get('processing_time', 0) for f in history 
        if f.get('processing_time') and f.get('processing_time') > 0
    ]
    
    if not processing_times:
        fig = go.Figure()
        fig.add_annotation(
            text="データがありません",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            title="処理時間分布",
            xaxis_title="処理時間（秒）",
            yaxis_title="件数"
        )
        return fig
    
    fig = go.Figure(data=[go.Histogram(
        x=processing_times,
        nbinsx=20,
        marker_color='#1f77b4',
        opacity=0.7
    )])
    
    fig.update_layout(
        title="処理時間分布",
        xaxis_title="処理時間（秒）",
        yaxis_title="件数",
        height=400
    )
    
    return fig

def render_dashboard():
    """ダッシュボードページをレンダリング"""
    st.markdown("## 📊 システムダッシュボード")
    
    # データ読み込み
    history = load_processing_history()
    
    # 統計サマリー
    st.markdown("### 📈 処理統計")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_files = len(history)
    successful_files = len([f for f in history if f.get('success', False)])
    failed_files = total_files - successful_files
    success_rate = (successful_files / total_files * 100) if total_files > 0 else 0
    
    with col1:
        st.metric(
            label="総処理ファイル数",
            value=total_files,
            delta=None
        )
    
    with col2:
        st.metric(
            label="成功数",
            value=successful_files,
            delta=None
        )
    
    with col3:
        st.metric(
            label="失敗数",
            value=failed_files,
            delta=None
        )
    
    with col4:
        st.metric(
            label="成功率",
            value=f"{success_rate:.1f}%",
            delta=None
        )
    
    # 今日の統計
    today = datetime.now().date()
    today_files = [
        f for f in history 
        if datetime.fromisoformat(f.get('processed_at', '1970-01-01')).date() == today
    ]
    
    if today_files:
        st.markdown("### 📅 今日の処理状況")
        col1, col2, col3 = st.columns(3)
        
        today_total = len(today_files)
        today_successful = len([f for f in today_files if f.get('success', False)])
        today_failed = today_total - today_successful
        
        with col1:
            st.metric("今日の処理数", today_total)
        with col2:
            st.metric("今日の成功数", today_successful)
        with col3:
            st.metric("今日の失敗数", today_failed)
    
    # チャート表示
    st.markdown("### 📊 詳細グラフ")
    
    col1, col2 = st.columns(2)
    
    with col1:
        success_chart = create_success_rate_chart(history)
        st.plotly_chart(success_chart, use_container_width=True)
    
    with col2:
        time_chart = create_processing_time_chart(history)
        st.plotly_chart(time_chart, use_container_width=True)
    
    # 日別処理数チャート
    daily_chart = create_daily_processing_chart(history)
    st.plotly_chart(daily_chart, use_container_width=True)
    
    # 最近の処理ファイル詳細
    st.markdown("### 📄 最近の処理ファイル（詳細）")
    
    if history:
        # 最新10件を表示
        recent_files = sorted(history, key=lambda x: x.get('processed_at', ''), reverse=True)[:10]
        
        # データフレーム作成
        df_data = []
        for file_info in recent_files:
            try:
                processed_time = datetime.fromisoformat(file_info.get('processed_at', '1970-01-01'))
                time_str = processed_time.strftime("%Y-%m-%d %H:%M:%S")
            except:
                time_str = "不明"
            
            df_data.append({
                'ファイル名': Path(file_info.get('file_path', '')).name,
                '処理結果': '✅ 成功' if file_info.get('success') else '❌ 失敗',
                '処理時間': f"{file_info.get('processing_time', 0):.1f}秒",
                '処理日時': time_str,
                'NotionページID': file_info.get('notion_page_id', 'N/A')
            })
        
        if df_data:
            df = pd.DataFrame(df_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("表示する処理履歴がありません")
    else:
        st.info("まだ処理されたファイルがありません。PDFファイルを処理してデータを確認してください。")
    
    # 自動更新オプション
    st.markdown("### 🔄 表示オプション")
    auto_refresh = st.checkbox("30秒ごとに自動更新", value=False)
    
    if auto_refresh:
        # 自動更新を実行
        import time
        time.sleep(30)
        st.rerun()