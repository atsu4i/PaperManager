"""
ログ表示ページ
システムログとエラーログの表示
"""

import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
import re
import sys
import os

# アプリケーションモジュールをインポート
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__)

def read_log_file(log_path: Path, max_lines: int = 1000) -> List[str]:
    """ログファイルを読み込み"""
    try:
        if not log_path.exists():
            return ["ログファイルが見つかりません"]
        
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 最新のN行を返す
        return lines[-max_lines:] if len(lines) > max_lines else lines
    
    except Exception as e:
        logger.error(f"ログファイル読み込みエラー: {e}")
        return [f"ログ読み込みエラー: {e}"]

def parse_log_line(line: str) -> Dict:
    """ログ行を解析してレベル等を抽出"""
    # ログフォーマット: "YYYY-MM-DD HH:MM:SS - module - LEVEL - message"
    pattern = r'(\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}) - ([^-]+) - ([^-]+) - (.+)'
    match = re.match(pattern, line.strip())
    
    if match:
        return {
            'timestamp': match.group(1),
            'module': match.group(2).strip(),
            'level': match.group(3).strip(),
            'message': match.group(4).strip(),
            'raw': line.strip()
        }
    else:
        return {
            'timestamp': '',
            'module': '',
            'level': 'UNKNOWN',
            'message': line.strip(),
            'raw': line.strip()
        }

def get_log_level_color(level: str) -> str:
    """ログレベルに応じた色を返す"""
    colors = {
        'DEBUG': '#6c757d',    # グレー
        'INFO': '#17a2b8',     # 青
        'WARNING': '#ffc107',  # 黄
        'ERROR': '#dc3545',    # 赤
        'CRITICAL': '#6f42c1'  # 紫
    }
    return colors.get(level.upper(), '#000000')

def filter_logs_by_level(logs: List[Dict], selected_levels: List[str]) -> List[Dict]:
    """ログレベルでフィルタリング"""
    if not selected_levels:
        return logs
    
    return [log for log in logs if log['level'].upper() in [l.upper() for l in selected_levels]]

def filter_logs_by_timeframe(logs: List[Dict], hours: int) -> List[Dict]:
    """時間範囲でフィルタリング"""
    if hours <= 0:
        return logs
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    filtered_logs = []
    
    for log in logs:
        try:
            if log['timestamp']:
                log_time = datetime.strptime(log['timestamp'], '%Y-%m-%d %H:%M:%S')
                if log_time >= cutoff_time:
                    filtered_logs.append(log)
            else:
                # タイムスタンプがない場合は含める
                filtered_logs.append(log)
        except ValueError:
            # パース失敗時は含める
            filtered_logs.append(log)
    
    return filtered_logs

def search_logs(logs: List[Dict], search_term: str) -> List[Dict]:
    """ログを検索"""
    if not search_term:
        return logs
    
    search_term = search_term.lower()
    return [
        log for log in logs 
        if search_term in log['message'].lower() or search_term in log['module'].lower()
    ]

def render_logs():
    """ログページをレンダリング"""
    st.markdown("## 📋 システムログ")
    
    # ログファイルパス
    log_file = Path(config.logging.file)
    
    # タブでログの種類を分類
    tab1, tab2, tab3 = st.tabs(["📄 システムログ", "🔍 ログ検索", "📊 ログ統計"])
    
    with tab1:
        st.markdown("### 📄 リアルタイムログ表示")
        
        # コントロールパネル
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        
        with col1:
            log_levels = st.multiselect(
                "表示レベル",
                options=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                default=['INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                help="表示するログレベルを選択"
            )
        
        with col2:
            time_filter = st.selectbox(
                "表示期間",
                options=[('全て', 0), ('過去1時間', 1), ('過去6時間', 6), ('過去24時間', 24), ('過去3日', 72)],
                index=3,  # デフォルトは過去24時間
                format_func=lambda x: x[0]
            )
        
        with col3:
            max_lines = st.selectbox(
                "最大表示行数",
                options=[100, 500, 1000, 2000],
                index=2,  # デフォルトは1000行
                help="表示する最大行数"
            )
        
        with col4:
            auto_refresh = st.checkbox("自動更新", value=False)
        
        # ログ読み込み
        log_lines = read_log_file(log_file, max_lines)
        
        if log_lines and log_lines[0] != "ログファイルが見つかりません":
            # ログを解析
            parsed_logs = [parse_log_line(line) for line in log_lines]
            
            # フィルタリング
            filtered_logs = filter_logs_by_level(parsed_logs, log_levels)
            filtered_logs = filter_logs_by_timeframe(filtered_logs, time_filter[1])
            
            # 統計情報
            st.markdown("#### 📊 ログサマリー")
            col1, col2, col3, col4 = st.columns(4)
            
            level_counts = {}
            for log in filtered_logs:
                level = log['level'].upper()
                level_counts[level] = level_counts.get(level, 0) + 1
            
            with col1:
                st.metric("総ログ数", len(filtered_logs))
            
            with col2:
                st.metric("エラー数", level_counts.get('ERROR', 0) + level_counts.get('CRITICAL', 0))
            
            with col3:
                st.metric("警告数", level_counts.get('WARNING', 0))
            
            with col4:
                st.metric("情報数", level_counts.get('INFO', 0))
            
            # ログ表示
            st.markdown("#### 📋 ログ詳細")
            
            if filtered_logs:
                # スクロール可能なログ表示エリア
                log_container = st.container()
                
                with log_container:
                    # 最新のログから表示（逆順）
                    for log in reversed(filtered_logs[-200:]):  # 最新200件のみ表示
                        level_color = get_log_level_color(log['level'])
                        
                        # ログレベルに応じてスタイリング
                        if log['level'].upper() in ['ERROR', 'CRITICAL']:
                            st.error(f"**[{log['timestamp']}] {log['level']}** - {log['module']}")
                            st.code(log['message'])
                        elif log['level'].upper() == 'WARNING':
                            st.warning(f"**[{log['timestamp']}] {log['level']}** - {log['module']}")
                            st.code(log['message'])
                        else:
                            st.info(f"**[{log['timestamp']}] {log['level']}** - {log['module']}")
                            st.text(log['message'])
                        
                        st.divider()
            else:
                st.info("選択された条件に該当するログがありません")
        
        else:
            st.warning("ログファイルが見つからないか、読み込めませんでした")
            st.info(f"ログファイルパス: {log_file}")
        
        # 自動更新
        if auto_refresh:
            import time
            time.sleep(10)
            st.rerun()
    
    with tab2:
        st.markdown("### 🔍 ログ検索・分析")
        
        # 検索フォーム
        search_term = st.text_input(
            "検索キーワード",
            placeholder="エラーメッセージやモジュール名で検索",
            help="ログメッセージまたはモジュール名を検索します"
        )
        
        if search_term:
            # ログを読み込み、検索
            log_lines = read_log_file(log_file, 2000)  # 検索のため多めに読み込み
            
            if log_lines and log_lines[0] != "ログファイルが見つかりません":
                parsed_logs = [parse_log_line(line) for line in log_lines]
                search_results = search_logs(parsed_logs, search_term)
                
                st.markdown(f"#### 📊 検索結果: {len(search_results)}件")
                
                if search_results:
                    # 検索結果の統計
                    col1, col2, col3 = st.columns(3)
                    
                    result_levels = {}
                    for log in search_results:
                        level = log['level'].upper()
                        result_levels[level] = result_levels.get(level, 0) + 1
                    
                    with col1:
                        st.metric("エラー", result_levels.get('ERROR', 0) + result_levels.get('CRITICAL', 0))
                    with col2:
                        st.metric("警告", result_levels.get('WARNING', 0))
                    with col3:
                        st.metric("情報", result_levels.get('INFO', 0))
                    
                    # 検索結果表示
                    for log in reversed(search_results[-50:]):  # 最新50件
                        with st.expander(f"[{log['timestamp']}] {log['level']} - {log['module']}"):
                            # 検索キーワードをハイライト
                            highlighted_message = log['message'].replace(
                                search_term, 
                                f"**{search_term}**"
                            )
                            st.markdown(highlighted_message)
                
                else:
                    st.info(f"'{search_term}' に該当するログが見つかりませんでした")
        
        # 頻出エラー分析
        st.markdown("### 📊 頻出エラー分析")
        
        if st.button("🔍 エラー分析を実行"):
            log_lines = read_log_file(log_file, 5000)  # 分析のため多めに読み込み
            
            if log_lines and log_lines[0] != "ログファイルが見つかりません":
                parsed_logs = [parse_log_line(line) for line in log_lines]
                error_logs = [log for log in parsed_logs if log['level'].upper() in ['ERROR', 'CRITICAL']]
                
                if error_logs:
                    # エラーメッセージを集計
                    error_counts = {}
                    for log in error_logs:
                        # エラーメッセージの最初の50文字で分類
                        error_key = log['message'][:50] + ("..." if len(log['message']) > 50 else "")
                        error_counts[error_key] = error_counts.get(error_key, 0) + 1
                    
                    # 上位10個のエラーを表示
                    sorted_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:10]
                    
                    st.markdown("#### 🔥 頻出エラー Top 10")
                    for i, (error_msg, count) in enumerate(sorted_errors, 1):
                        st.write(f"**{i}.** ({count}回) {error_msg}")
                else:
                    st.success("エラーログが見つかりませんでした（良好な状態です）")
    
    with tab3:
        st.markdown("### 📊 ログ統計")
        
        # 統計生成ボタン
        if st.button("📈 統計を生成", type="primary"):
            with st.spinner("統計を生成中..."):
                log_lines = read_log_file(log_file, 5000)
                
                if log_lines and log_lines[0] != "ログファイルが見つかりません":
                    parsed_logs = [parse_log_line(line) for line in log_lines]
                    
                    # 時間別統計
                    st.markdown("#### ⏰ 時間別ログ分布")
                    
                    hourly_stats = {}
                    for log in parsed_logs:
                        try:
                            if log['timestamp']:
                                hour = datetime.strptime(log['timestamp'], '%Y-%m-%d %H:%M:%S').hour
                                hourly_stats[hour] = hourly_stats.get(hour, 0) + 1
                        except ValueError:
                            continue
                    
                    if hourly_stats:
                        # Plotlyで時間別グラフ作成
                        import plotly.express as px
                        import pandas as pd
                        
                        df = pd.DataFrame([
                            {'時間': f"{hour:02d}:00", '件数': count}
                            for hour, count in sorted(hourly_stats.items())
                        ])
                        
                        fig = px.bar(df, x='時間', y='件数', title='時間別ログ分布')
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # レベル別統計
                    st.markdown("#### 📊 ログレベル別統計")
                    
                    level_stats = {}
                    for log in parsed_logs:
                        level = log['level'].upper()
                        level_stats[level] = level_stats.get(level, 0) + 1
                    
                    if level_stats:
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            for level, count in sorted(level_stats.items()):
                                percentage = (count / len(parsed_logs)) * 100
                                st.metric(level, f"{count} ({percentage:.1f}%)")
                        
                        with col2:
                            # 円グラフ
                            import plotly.graph_objects as go
                            
                            fig = go.Figure(data=[go.Pie(
                                labels=list(level_stats.keys()),
                                values=list(level_stats.values()),
                                hole=0.3
                            )])
                            fig.update_layout(title="ログレベル分布")
                            st.plotly_chart(fig, use_container_width=True)
                    
                    # モジュール別統計
                    st.markdown("#### 🧩 モジュール別統計")
                    
                    module_stats = {}
                    for log in parsed_logs:
                        module = log['module'].strip()
                        if module:
                            module_stats[module] = module_stats.get(module, 0) + 1
                    
                    if module_stats:
                        # 上位10モジュール
                        sorted_modules = sorted(module_stats.items(), key=lambda x: x[1], reverse=True)[:10]
                        
                        df = pd.DataFrame(sorted_modules, columns=['モジュール', 'ログ数'])
                        st.dataframe(df, use_container_width=True, hide_index=True)
                
                else:
                    st.error("ログファイルの読み込みに失敗しました")
        
        # ログファイル情報
        st.markdown("#### 📁 ログファイル情報")
        
        if log_file.exists():
            file_size = log_file.stat().st_size
            file_modified = datetime.fromtimestamp(log_file.stat().st_mtime)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("ファイルサイズ", f"{file_size / 1024:.1f} KB")
            with col2:
                st.metric("最終更新", file_modified.strftime("%Y-%m-%d %H:%M:%S"))
            
            st.info(f"ログファイルパス: {log_file}")
        else:
            st.warning("ログファイルが見つかりません")
    
    # フッター
    st.markdown("---")
    st.markdown("💡 **ヒント:** ログは自動的にローテーションされ、古いログは自動削除されます。")