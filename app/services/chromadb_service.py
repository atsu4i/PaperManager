"""
ChromaDB Vector Database Service

Gemini Embedding APIを使用した論文のベクトル化とChromaDBへの保存・検索を管理します。
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
import google.generativeai as genai

from app.config import config
from app.utils.logger import get_logger
from app.models.paper import PaperMetadata
from app.services.gemma_service import gemma_service

logger = get_logger(__name__)


class ChromaDBService:
    """ChromaDBサービスクラス"""

    def __init__(self):
        """初期化"""
        # プロジェクトルートを取得
        project_root = Path(__file__).parent.parent.parent
        self.db_path = project_root / "data" / "chroma_db"
        self.db_path.mkdir(parents=True, exist_ok=True)

        # ChromaDB クライアントの初期化
        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # コレクション取得または作成
        self.collection = self.client.get_or_create_collection(
            name="papers",
            metadata={"description": "Medical papers vector store"}
        )

        # Gemini API の初期化
        genai.configure(api_key=config.gemini_api_key)
        self.embedding_model = "models/embedding-001"

        logger.info(f"ChromaDB initialized at {self.db_path}")
        logger.info(f"Collection 'papers' ready (count: {self.collection.count()})")

    def _generate_embedding(self, text: str) -> List[float]:
        """
        Gemini Embedding APIを使ってテキストをベクトル化

        Args:
            text: ベクトル化するテキスト

        Returns:
            ベクトル (List[float])
        """
        try:
            result = genai.embed_content(
                model=self.embedding_model,
                content=text,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    def _generate_query_embedding(self, query: str) -> List[float]:
        """
        検索クエリ用のベクトル生成

        Args:
            query: 検索クエリ

        Returns:
            ベクトル (List[float])
        """
        try:
            result = genai.embed_content(
                model=self.embedding_model,
                content=query,
                task_type="retrieval_query"
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Query embedding generation failed: {e}")
            raise

    async def add_paper(
        self,
        paper: PaperMetadata,
        notion_page_id: str,
        notion_url: Optional[str] = None,
        obsidian_path: Optional[str] = None
    ) -> bool:
        """
        論文をベクトル化してChromaDBに追加

        Args:
            paper: 論文メタデータ
            notion_page_id: Notion ページID
            notion_url: Notion URL (オプション)
            obsidian_path: Obsidian ファイルパス (オプション)

        Returns:
            成功したらTrue
        """
        try:
            # タイトル + 要約をベクトル化
            text_to_embed = f"{paper.title}\n\n{paper.summary_japanese}"
            embedding = self._generate_embedding(text_to_embed)

            # メタデータ準備
            metadata = {
                "title": paper.title,
                "authors": ", ".join(paper.authors) if paper.authors else "",
                "journal": paper.journal or "",
                "year": paper.publication_year or "",
                "doi": paper.doi or "",
                "pmid": paper.pmid or "",
                "keywords": ", ".join(paper.keywords) if paper.keywords else "",
                "summary": paper.summary_japanese,  # 全文保存
                "notion_page_id": notion_page_id,
                "notion_url": notion_url or "",
                "obsidian_path": obsidian_path or ""
            }

            # ChromaDBに追加
            self.collection.add(
                embeddings=[embedding],
                documents=[text_to_embed],
                metadatas=[metadata],
                ids=[notion_page_id]
            )

            logger.info(f"Paper added to ChromaDB: {paper.title} (ID: {notion_page_id})")
            return True

        except Exception as e:
            logger.error(f"Failed to add paper to ChromaDB: {e}")
            return False

    def _generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        複数のテキストを一度にベクトル化（バッチ処理）

        Args:
            texts: ベクトル化するテキストのリスト（最大100件）

        Returns:
            ベクトルのリスト
        """
        try:
            if len(texts) > 100:
                raise ValueError(f"Batch size {len(texts)} exceeds maximum of 100")

            result = genai.embed_content(
                model=self.embedding_model,
                content=texts,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            raise

    async def add_papers_batch(
        self,
        papers_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        複数論文をバッチでベクトル化してChromaDBに追加

        Args:
            papers_data: 論文データのリスト
                各要素は以下のキーを持つ辞書:
                - paper: PaperMetadata
                - notion_page_id: str
                - notion_url: Optional[str]
                - obsidian_path: Optional[str]

        Returns:
            結果の辞書 {"success": int, "failed": int, "failed_ids": List[str]}
        """
        try:
            if not papers_data:
                return {"success": 0, "failed": 0, "failed_ids": []}

            if len(papers_data) > 100:
                raise ValueError(f"Batch size {len(papers_data)} exceeds maximum of 100")

            # テキストとメタデータを準備
            texts_to_embed = []
            metadatas = []
            ids = []
            documents = []

            for data in papers_data:
                paper = data["paper"]
                notion_page_id = data["notion_page_id"]
                notion_url = data.get("notion_url", "")
                obsidian_path = data.get("obsidian_path", "")

                # タイトル + 要約
                text_to_embed = f"{paper.title}\n\n{paper.summary_japanese}"
                texts_to_embed.append(text_to_embed)
                documents.append(text_to_embed)
                ids.append(notion_page_id)

                # メタデータ
                metadata = {
                    "title": paper.title,
                    "authors": ", ".join(paper.authors) if paper.authors else "",
                    "journal": paper.journal or "",
                    "year": paper.publication_year or "",
                    "doi": paper.doi or "",
                    "pmid": paper.pmid or "",
                    "keywords": ", ".join(paper.keywords) if paper.keywords else "",
                    "summary": paper.summary_japanese,  # 全文保存
                    "notion_page_id": notion_page_id,
                    "notion_url": notion_url,
                    "obsidian_path": obsidian_path
                }
                metadatas.append(metadata)

            # バッチでベクトル化
            logger.info(f"Batch embedding generation for {len(texts_to_embed)} papers...")
            embeddings = self._generate_embeddings_batch(texts_to_embed)

            # ChromaDBに一括追加
            self.collection.add(
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )

            logger.info(f"Batch added {len(papers_data)} papers to ChromaDB")
            return {
                "success": len(papers_data),
                "failed": 0,
                "failed_ids": []
            }

        except Exception as e:
            logger.error(f"Failed to add papers batch to ChromaDB: {e}")
            # エラー時は個別に処理
            return await self._fallback_individual_add(papers_data)

    async def _fallback_individual_add(
        self,
        papers_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        バッチ処理失敗時のフォールバック: 個別に追加

        Args:
            papers_data: 論文データのリスト

        Returns:
            結果の辞書
        """
        logger.warning(f"Falling back to individual add for {len(papers_data)} papers")
        success_count = 0
        failed_count = 0
        failed_ids = []

        for data in papers_data:
            try:
                result = await self.add_paper(
                    data["paper"],
                    data["notion_page_id"],
                    data.get("notion_url"),
                    data.get("obsidian_path")
                )
                if result:
                    success_count += 1
                else:
                    failed_count += 1
                    failed_ids.append(data["notion_page_id"])
            except Exception as e:
                logger.error(f"Individual add failed for {data['notion_page_id']}: {e}")
                failed_count += 1
                failed_ids.append(data["notion_page_id"])

        return {
            "success": success_count,
            "failed": failed_count,
            "failed_ids": failed_ids
        }

    def search(
        self,
        query: str,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        セマンティック検索を実行

        Args:
            query: 検索クエリ
            n_results: 取得する結果数
            where: メタデータフィルタ (オプション)

        Returns:
            検索結果のリスト
        """
        try:
            # クエリをベクトル化
            query_embedding = self._generate_query_embedding(query)

            # ChromaDBで検索
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=["metadatas", "documents", "distances"]
            )

            # 結果を整形
            formatted_results = []
            if results and results['ids'] and len(results['ids'][0]) > 0:
                for i in range(len(results['ids'][0])):
                    result = {
                        "id": results['ids'][0][i],
                        "metadata": results['metadatas'][0][i],
                        "document": results['documents'][0][i],
                        "distance": results['distances'][0][i],
                        "similarity": 1 - results['distances'][0][i]  # 類似度スコア
                    }
                    formatted_results.append(result)

            logger.info(f"Search completed: {len(formatted_results)} results for '{query}'")
            return formatted_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get_paper(self, notion_page_id: str) -> Optional[Dict[str, Any]]:
        """
        Notion IDで論文を取得

        Args:
            notion_page_id: Notion ページID

        Returns:
            論文データ (見つからない場合はNone)
        """
        try:
            result = self.collection.get(
                ids=[notion_page_id],
                include=["metadatas", "documents"]
            )

            if result and result['ids']:
                return {
                    "id": result['ids'][0],
                    "metadata": result['metadatas'][0],
                    "document": result['documents'][0]
                }
            return None

        except Exception as e:
            logger.error(f"Failed to get paper: {e}")
            return None

    async def update_paper(
        self,
        notion_page_id: str,
        paper: PaperMetadata,
        notion_url: Optional[str] = None,
        obsidian_path: Optional[str] = None
    ) -> bool:
        """
        既存論文のデータを更新

        Args:
            notion_page_id: Notion ページID
            paper: 更新後の論文メタデータ
            notion_url: Notion URL (オプション)
            obsidian_path: Obsidian ファイルパス (オプション)

        Returns:
            成功したらTrue
        """
        try:
            # 既存データを削除
            self.collection.delete(ids=[notion_page_id])

            # 新しいデータを追加
            return await self.add_paper(paper, notion_page_id, notion_url, obsidian_path)

        except Exception as e:
            logger.error(f"Failed to update paper: {e}")
            return False

    def delete_paper(self, notion_page_id: str) -> bool:
        """
        論文をChromaDBから削除

        Args:
            notion_page_id: Notion ページID

        Returns:
            成功したらTrue
        """
        try:
            self.collection.delete(ids=[notion_page_id])
            logger.info(f"Paper deleted from ChromaDB: {notion_page_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete paper: {e}")
            return False

    def get_count(self) -> int:
        """
        登録されている論文の総数を取得

        Returns:
            論文数
        """
        return self.collection.count()

    def deep_search(
        self,
        query: str,
        n_results: int = 10,
        broad_retrieval_size: int = 30,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Deep Search（HyDE + Reranking）による高精度検索

        3段階プロセス:
        1. HyDE（Query Expansion）: LLMで架空の論文要約を生成
        2. Broad Retrieval: ベクトル検索でTop 30を取得
        3. Reranking: LLMで精査してTop N に絞る

        Args:
            query: ユーザーの検索クエリ
            n_results: 最終的に返す結果数（デフォルト10）
            broad_retrieval_size: 中間検索で取得する件数（デフォルト30）
            where: メタデータフィルタ (オプション)

        Returns:
            検索結果の辞書 {
                "results": List[Dict],
                "hyde_query": str,
                "stats": Dict
            }
        """
        try:
            stats = {
                "original_query": query,
                "hyde_query": "",
                "broad_retrieval_count": 0,
                "final_count": 0
            }

            # Step 1: HyDE（Query Expansion）
            logger.info(f"Step 1: HyDE query expansion for '{query}'")
            hyde_query = gemma_service.generate_hyde_query(query)
            stats["hyde_query"] = hyde_query

            # Step 2: Broad Retrieval（ベクトル検索でTop 30）
            logger.info(f"Step 2: Broad retrieval (Top {broad_retrieval_size})")
            broad_results = self.search(
                hyde_query,
                n_results=broad_retrieval_size,
                where=where
            )
            stats["broad_retrieval_count"] = len(broad_results)

            if not broad_results:
                logger.warning("No results from broad retrieval")
                return {
                    "results": [],
                    "hyde_query": hyde_query,
                    "stats": stats
                }

            # Step 3: Reranking（LLMで精査してTop N）
            logger.info(f"Step 3: Reranking to Top {n_results}")
            final_results = gemma_service.rerank_results(
                query,  # 元の質問を使用
                broad_results,
                top_k=n_results
            )
            stats["final_count"] = len(final_results)

            logger.info(f"Deep search completed: {stats['final_count']} results")

            return {
                "results": final_results,
                "hyde_query": hyde_query,
                "stats": stats
            }

        except Exception as e:
            logger.error(f"Deep search failed: {e}")
            # フォールバック: 通常のsearchを実行
            logger.warning("Falling back to normal search")
            return {
                "results": self.search(query, n_results=n_results, where=where),
                "hyde_query": query,
                "stats": {
                    "original_query": query,
                    "hyde_query": query,
                    "broad_retrieval_count": 0,
                    "final_count": n_results,
                    "error": str(e)
                }
            }


# シングルトンインスタンス
chromadb_service = ChromaDBService()
