"""
Paper Searcher - 医学論文セマンティック検索アプリ

ChromaDBに登録された論文をセマンティック検索で検索・表示します。
"""

import sys
from pathlib import Path
import streamlit as st

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.chromadb_service import chromadb_service
from app.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ページ設定
st.set_page_config(
    page_title="Paper Searcher",
    page_icon="🔍",
    layout="wide",  # PCでは広く表示
    initial_sidebar_state="collapsed"
)

# カスタムCSS（レスポンシブ対応）
st.markdown("""
<style>
    /* 基本レイアウト（PC） */
    .main-header {
        text-align: center;
        padding: 1rem 0 2rem 0;
    }
    .search-box {
        max-width: 900px;
        margin: 0 auto 3rem auto;
        padding: 0 1rem;
    }
    .result-card {
        background-color: #f8f9fa;
        border-left: 4px solid #007bff;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        border-radius: 0.25rem;
    }
    .result-title {
        font-size: 1.3rem;
        font-weight: 600;
        color: #1a1a1a;
        margin-bottom: 0.5rem;
        line-height: 1.4;
    }
    .result-meta {
        color: #6c757d;
        font-size: 0.9rem;
        margin-bottom: 0.75rem;
        line-height: 1.5;
    }
    .result-summary {
        color: #495057;
        line-height: 1.6;
        margin-bottom: 0.75rem;
    }
    .result-links {
        margin-top: 0.75rem;
    }
    .similarity-badge {
        display: inline-block;
        background-color: #28a745;
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.85rem;
        font-weight: 500;
        margin-right: 0.5rem;
    }

    /* タブレット対応 */
    @media (max-width: 1024px) {
        .main .block-container {
            max-width: 100% !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
        .search-box {
            max-width: 700px;
        }
    }

    /* モバイル対応（スマホ） */
    @media (max-width: 768px) {
        .main .block-container {
            max-width: 100% !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        .main-header {
            padding: 0.5rem 0 1rem 0;
        }
        .main-header h1 {
            font-size: 1.8rem !important;
        }
        .main-header p {
            font-size: 0.9rem !important;
        }
        .search-box {
            max-width: 100%;
            padding: 0 0.5rem;
            margin-bottom: 1.5rem;
        }
        .result-card {
            padding: 1rem;
            margin-bottom: 1rem;
        }
        .result-title {
            font-size: 1.05rem;
            line-height: 1.3;
        }
        .result-meta {
            font-size: 0.8rem;
        }
        .similarity-badge {
            font-size: 0.75rem;
            padding: 0.2rem 0.6rem;
        }
        /* タッチ操作に適したボタンサイズ */
        .stButton button {
            min-height: 3rem !important;
            font-size: 1rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)


def format_authors(authors_str: str, max_display: int = 3) -> str:
    """
    著者リストを整形して表示

    Args:
        authors_str: カンマ区切りの著者リスト
        max_display: 最大表示人数

    Returns:
        整形された著者リスト
    """
    if not authors_str:
        return "著者不明"

    authors = [a.strip() for a in authors_str.split(",")]
    if len(authors) <= max_display:
        return ", ".join(authors)
    else:
        return f"{', '.join(authors[:max_display])}, et al."


def display_search_result(result: dict, index: int):
    """
    検索結果を表示

    Args:
        result: 検索結果ディクショナリ
        index: 結果のインデックス
    """
    metadata = result["metadata"]
    similarity = result["similarity"]

    # 類似度スコアの色分け
    if similarity >= 0.8:
        badge_color = "#28a745"  # 緑
    elif similarity >= 0.6:
        badge_color = "#ffc107"  # 黄
    else:
        badge_color = "#6c757d"  # グレー

    # カード表示
    st.markdown(f"""
    <div class="result-card">
        <div class="result-title">
            {index}. {metadata.get('title', '(タイトルなし)')}
        </div>
        <div class="result-meta">
            <strong>{format_authors(metadata.get('authors', ''))}</strong>
            {' | ' + metadata.get('journal', '') if metadata.get('journal') else ''}
            {' (' + metadata.get('year', '') + ')' if metadata.get('year') else ''}
        </div>
        <div style="margin-bottom: 0.75rem;">
            <span class="similarity-badge" style="background-color: {badge_color};">
                関連度: {similarity:.1%}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 要約を展開可能に
    with st.expander("📄 要約を表示"):
        # documentフィールドから要約全文を取得
        # documentは「タイトル\n\n要約」の形式なので、要約部分を抽出
        document = result.get('document', '')
        if document and '\n\n' in document:
            # タイトル部分をスキップして要約のみ取得
            summary = document.split('\n\n', 1)[1].strip()
        else:
            # フォールバック: metadataのsummaryを使用
            summary = metadata.get('summary', '').strip()

        if summary:
            st.write(summary)
        else:
            st.info("要約がありません")

    # リンク表示（モバイルで見やすく）
    links = []
    if metadata.get('notion_url'):
        links.append(f"[📝 Notion]({metadata['notion_url']})")
    if metadata.get('doi'):
        links.append(f"[📄 DOI]({metadata['doi']})")
    if metadata.get('pmid'):
        pmid = metadata['pmid']
        links.append(f"[🔬 PubMed](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)")

    if links:
        st.markdown("**🔗 リンク:** " + " · ".join(links))
    else:
        st.caption("🔗 リンクなし")

    st.markdown("---")


def main():
    """メイン処理"""
    # ヘッダー
    st.markdown("""
    <div class="main-header">
        <h1>🔍 Paper Searcher</h1>
        <p style="color: #6c757d; font-size: 1.1rem;">Notion論文データベース検索</p>
    </div>
    """, unsafe_allow_html=True)

    # セッションステート初期化
    if 'search_results' not in st.session_state:
        st.session_state.search_results = None
    if 'last_query' not in st.session_state:
        st.session_state.last_query = ""
    if 'search_stats' not in st.session_state:
        st.session_state.search_stats = None
    if 'hyde_query' not in st.session_state:
        st.session_state.hyde_query = None

    # ChromaDB登録数表示
    try:
        db_count = chromadb_service.get_count()
        st.sidebar.success(f"📦 登録論文数: {db_count:,}件")
    except Exception as e:
        st.sidebar.error(f"ChromaDB接続エラー: {e}")
        logger.error(f"ChromaDB connection error: {e}")
        return

    # サイドバー設定（モバイルではエクスパンダーに格納）
    with st.sidebar:
        st.markdown("### ⚙️ 検索設定")

        # 検索モード選択
        search_mode = st.radio(
            "検索モード",
            options=["Deep Search（HyDE + Rerank）", "Fast Search（通常ベクトル検索）"],
            index=0,
            help="Deep Searchは精度重視、Fast Searchは速度重視"
        )

        n_results = st.slider(
            "表示件数",
            min_value=5,
            max_value=50,
            value=10,
            step=5
        )

        # Deep Search詳細設定
        if search_mode == "Deep Search（HyDE + Rerank）":
            st.markdown("#### Deep Search設定")
            broad_retrieval_size = st.slider(
                "中間検索件数",
                min_value=20,
                max_value=50,
                value=30,
                step=10,
                help="ベクトル検索で取得する候補数（多いほど網羅的、遅い）"
            )
        else:
            broad_retrieval_size = 30  # デフォルト値

    # 検索ボックス
    st.markdown('<div class="search-box">', unsafe_allow_html=True)

    query = st.text_input(
        "検索キーワードを入力してください",
        placeholder="例: 小児ALLの維持療法",
        label_visibility="collapsed",
        key="search_input"
    )

    search_button = st.button("🔍 検索", type="primary", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # 検索実行
    if search_button and query:
        if search_mode == "Deep Search（HyDE + Rerank）":
            # Deep Search（HyDE + Reranking）
            status_container = st.empty()

            try:
                # Step 1: HyDE
                status_container.info("🤖 Step 1/3: Geminiが関連用語を思考中...")
                import time
                time.sleep(0.5)  # UI表示用の短い待機

                # Step 2: Vector Search
                status_container.info("🔍 Step 2/3: 論文データベースを検索中...")
                time.sleep(0.5)

                # Step 3: Reranking
                status_container.info("🎯 Step 3/3: Geminiが論文を精査中...")

                # Deep Search実行
                search_result = chromadb_service.deep_search(
                    query,
                    n_results=n_results,
                    broad_retrieval_size=broad_retrieval_size
                )

                status_container.success("✅ Deep Search完了!")
                time.sleep(1)
                status_container.empty()

                # 結果を保存
                st.session_state.search_results = search_result["results"]
                st.session_state.last_query = query
                st.session_state.search_stats = search_result["stats"]
                st.session_state.hyde_query = search_result["hyde_query"]

            except Exception as e:
                status_container.error(f"検索エラー: {e}")
                logger.error(f"Deep search error: {e}")
                return

        else:
            # Fast Search（通常ベクトル検索）
            with st.spinner("🔍 検索中..."):
                try:
                    results = chromadb_service.search(query, n_results=n_results)
                    st.session_state.search_results = results
                    st.session_state.last_query = query
                    st.session_state.search_stats = None
                    st.session_state.hyde_query = None
                except Exception as e:
                    st.error(f"検索エラー: {e}")
                    logger.error(f"Search error: {e}")
                    return

    # 検索結果表示
    if st.session_state.search_results is not None:
        results = st.session_state.search_results

        if not results:
            st.info("🔍 検索結果が見つかりませんでした。別のキーワードで試してください。")
        else:
            # 結果ヘッダー
            st.markdown(f"""
            <div style="margin: 2rem 0 1.5rem 0;">
                <h3>検索結果: <code>{st.session_state.last_query}</code></h3>
                <p style="color: #6c757d;">見つかった論文: {len(results)}件</p>
            </div>
            """, unsafe_allow_html=True)

            # Deep Search統計情報を表示
            if hasattr(st.session_state, 'search_stats') and st.session_state.search_stats:
                stats = st.session_state.search_stats
                with st.expander("📊 Deep Search統計情報", expanded=False):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.metric("候補取得数", f"{stats.get('broad_retrieval_count', 0)}件")

                    with col2:
                        st.metric("最終選出数", f"{stats.get('final_count', 0)}件")

                    with col3:
                        rerank_ratio = (
                            stats.get('final_count', 0) / stats.get('broad_retrieval_count', 1) * 100
                            if stats.get('broad_retrieval_count', 0) > 0 else 0
                        )
                        st.metric("選出率", f"{rerank_ratio:.1f}%")

                    # HyDEクエリを表示
                    if hasattr(st.session_state, 'hyde_query') and st.session_state.hyde_query:
                        st.markdown("**🤖 生成された検索クエリ（HyDE）:**")
                        st.text_area(
                            "HyDE Query",
                            value=st.session_state.hyde_query,
                            height=150,
                            label_visibility="collapsed"
                        )

            # 各結果を表示
            for idx, result in enumerate(results, 1):
                display_search_result(result, idx)

    # フッター
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #6c757d; padding: 0.5rem 0;">
        <p style="font-size: 0.85rem; margin: 0;">Paper Searcher v1.8</p>
        <p style="font-size: 0.75rem; margin: 0.25rem 0 0 0;">Gemini Embedding + gemma-3-27b-it + ChromaDB</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"アプリケーションエラー: {e}")
        logger.error(f"Application error: {e}")
