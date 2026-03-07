"""D&D 5e SRD 混合检索器（Dense + BM25 + Rerank）"""

import os
import requests
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import SparseVector, Prefetch, FusionQuery, Fusion

from fastembed import SparseTextEmbedding


class Retriever:
    """D&D 5e SRD 混合检索器（Dense + BM25 + Rerank）"""

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        collection_name: str = "dnd_5e_srd_hybrid",
        api_key: str | None = None,
        embedding_model: str = "BAAI/bge-m3",
        rerank_model: str = "BAAI/bge-reranker-v2-m3",
    ):
        self.qdrant_url = qdrant_url
        self.collection_name = collection_name
        self.api_key = api_key or os.environ.get("SILICONFLOW_API_KEY", "")
        self.embedding_model = embedding_model
        self.rerank_model = rerank_model
        self.api_base = "https://api.siliconflow.cn/v1"

        # 懒加载属性
        self._qdrant_client: QdrantClient | None = None
        self._embedding_client: OpenAI | None = None
        self._bm25_model: SparseTextEmbedding | None = None

    @property
    def qdrant_client(self) -> QdrantClient:
        """获取 Qdrant 客户端（懒加载）"""
        if self._qdrant_client is None:
            self._qdrant_client = QdrantClient(url=self.qdrant_url)
        return self._qdrant_client

    @property
    def embedding_client(self) -> OpenAI:
        """获取 SiliconFlow Embedding 客户端（懒加载）"""
        if self._embedding_client is None:
            self._embedding_client = OpenAI(base_url=self.api_base, api_key=self.api_key)
        return self._embedding_client

    @property
    def bm25_model(self) -> SparseTextEmbedding:
        """获取 BM25 模型（懒加载）"""
        if self._bm25_model is None:
            print("正在加载本地 BM25 词频统计引擎...")
            self._bm25_model = SparseTextEmbedding(model_name="Qdrant/bm25")
            print("BM25 加载完毕。")
        return self._bm25_model

    # ============================================
    # 公共方法（供入库和检索复用）
    # ============================================
    def get_dense_embeddings(self, texts: list[str]) -> list[list[float]]:
        """生成密集向量"""
        if not texts:
            return []
        response = self.embedding_client.embeddings.create(input=texts, model=self.embedding_model)
        return [item.embedding for item in response.data]

    def get_sparse_embeddings(self, texts: list[str]) -> list:
        """生成 BM25 稀疏向量"""
        if not texts:
            return []
        return list(self.bm25_model.embed(texts))

    def call_reranker(self, query: str, documents: list[str], top_n: int) -> list[dict]:
        """调用 SiliconFlow Rerank API"""
        url = f"{self.api_base}/rerank"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.rerank_model,
            "query": query,
            "documents": documents,
            "top_n": top_n,
            "return_documents": False
        }

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            print(f"❌ Rerank API 调用失败 [{response.status_code}]: {response.text}")
            response.raise_for_status()

        return response.json().get("results", [])

    # ============================================
    # 检索方法
    # ============================================
    def search(self, query: str, limit: int = 5, fetch_k: int = 20) -> list[dict]:
        """
        执行混合检索（Dense + BM25 + Rerank）

        Args:
            query: 查询文本
            limit: 最终返回的结果数量
            fetch_k: 初次召回的候选数量

        Returns:
            排序后的结果列表，每个元素包含：
            - score: Rerank 相关性得分
            - content: 文档内容
            - metadata: 元数据（file, title, level, path, type 等）
            - parent_content: 父块上下文（如果有）
        """
        # --- 阶段一：RRF 混合召回 ---
        # Dense 向量
        dense_query_vec = self.get_dense_embeddings([query])[0]
        # BM25 稀疏向量
        sparse_query_result = self.get_sparse_embeddings([query])[0]
        sparse_query_vec = SparseVector(
            indices=sparse_query_result.indices.tolist(),
            values=sparse_query_result.values.tolist()
        )

        # Qdrant RRF 混合召回
        raw_results = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                Prefetch(query=dense_query_vec, using="dense", limit=fetch_k),
                Prefetch(query=sparse_query_vec, using="sparse", limit=fetch_k)
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=fetch_k,
            with_payload=True,
        )

        points = raw_results.points
        if not points:
            return []

        # --- 阶段二：Rerank 重排 ---
        documents = [point.payload['content'] for point in points if point.payload]
        reranked_results = self.call_reranker(query, documents, top_n=limit)

        if not reranked_results:
            reranked_results = [{"index": i, "relevance_score": 0} for i in range(min(limit, len(points)))]

        # --- 阶段三：构建返回结果 ---
        results = []
        for ranked_item in reranked_results:
            original_index = ranked_item.get("index")
            score = ranked_item.get("relevance_score", 0)

            if original_index is None or original_index >= len(points):
                continue

            original_point = points[original_index]
            payload = original_point.payload

            if payload is None:
                continue

            results.append({
                "score": score,
                "content": payload.get("content", ""),
                "metadata": {
                    "file": payload.get("file", ""),
                    "title": payload.get("title", ""),
                    "level": payload.get("level", 0),
                    "path": payload.get("path", []),
                    "type": payload.get("type", ""),
                },
                "parent_content": payload.get("parent_content"),
            })

        return results

    def search_verbose(self, query: str, limit: int = 3, fetch_k: int = 20) -> None:
        """
        执行混合检索并打印格式化结果

        Args:
            query: 查询文本
            limit: 最终返回的结果数量
            fetch_k: 初次召回的候选数量
        """
        print(f"\n🔍 [用户提问]: '{query}'")
        print(f"⏳ [阶段一] Qdrant 正在执行 RRF 混合召回 (召回 {fetch_k} 条)...")
        print(f"⏳ [阶段二] 正在调用 SiliconFlow {self.rerank_model} 模型进行精细重排...")

        results = self.search(query, limit=limit, fetch_k=fetch_k)

        if not results:
            print("没有找到相关结果。")
            return

        print(f"✨ 重排完成！以下是最精准的 Top {len(results)}：\n")

        for i, result in enumerate(results, 1):
            metadata = result["metadata"]
            score = result["score"]
            content = result["content"]

            print(f"🥇 第 {i} 名: [{metadata.get('type', '未知').upper()}] {metadata.get('title', '无标题')}")
            print(f"   📂 来源: {metadata.get('file', '未知')} | 🗺️ 路径: {' > '.join(metadata.get('path', []))}")
            print(f"   🎯 Rerank 相关性得分: {score:.4f}")

            preview = content[:100].replace('\n', ' ') + "..."
            print(f"   📖 内容预览: {preview}")

            parent_content = result.get("parent_content")
            if parent_content:
                parent_preview = parent_content[:150].replace('\n', ' ') + "..."
                print(f"   📦 父块上下文: {parent_preview}")

            print("-" * 60)