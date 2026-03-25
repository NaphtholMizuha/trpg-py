from __future__ import annotations

import os
from typing import Any, Literal, Protocol, cast

import requests
from fastembed import SparseTextEmbedding
from langchain_core.tools import BaseTool
from openai import OpenAI
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.models import Fusion, FusionQuery, Prefetch, SparseVector


class DenseEmbedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class SparseEmbedder(Protocol):
    def embed(self, texts: list[str]) -> list[Any]: ...


class Reranker(Protocol):
    def rerank(self, query: str, documents: list[str], top_n: int) -> list[dict[str, Any]]: ...


class SearchError(BaseModel):
    type: str
    message: str


class SearchHit(BaseModel):
    rank: int
    score: float
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    parent_text: str | None = None


class SearchResult(BaseModel):
    status: Literal["ok", "no_match", "error"]
    hits: list[SearchHit] = Field(default_factory=list)
    error: SearchError | None = None


class SearchInput(BaseModel):
    query: str = Field(
        min_length=1,
        description=(
            "用于检索规则原文的自然语言查询。"
            "优先用完整问题或具体场景描述，而不是只写零散关键词。"
        ),
    )
    limit: int = Field(default=3, ge=1, le=20, description="最终返回的命中数量")
    fetch_k: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="混合召回阶段抓取的候选数量；为空时使用搜索器默认值。",
    )


class OpenAIEmbedder:
    def __init__(
        self,
        *,
        model: str = "BAAI/bge-m3",
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("SILICONFLOW_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url or os.environ.get("SILICONFLOW_BASE_URL") or "https://api.siliconflow.cn/v1"
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(input=texts, model=self.model)
        return [list(item.embedding) for item in response.data]


class FastEmbedSparseEmbedder:
    def __init__(self, *, model_name: str = "Qdrant/bm25") -> None:
        self.model_name = model_name
        self._model: SparseTextEmbedding | None = None

    @property
    def model(self) -> SparseTextEmbedding:
        if self._model is None:
            self._model = SparseTextEmbedding(model_name=self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[Any]:
        if not texts:
            return []
        return list(self.model.embed(texts))


class HTTPReranker:
    def __init__(
        self,
        *,
        model: str = "BAAI/bge-reranker-v2-m3",
        api_key: str | None = None,
        base_url: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("SILICONFLOW_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url or os.environ.get("SILICONFLOW_BASE_URL") or "https://api.siliconflow.cn/v1"
        self.session = session or requests.Session()

    def rerank(self, query: str, documents: list[str], top_n: int) -> list[dict[str, Any]]:
        if not documents:
            return []
        response = self.session.post(
            f"{self.base_url.rstrip('/')}/rerank",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "query": query,
                "documents": documents,
                "top_n": top_n,
                "return_documents": False,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        return cast(list[dict[str, Any]], payload.get("results", []))


class HybridRuleSearcher:
    def __init__(
        self,
        *,
        collection_name: str,
        qdrant_client: QdrantClient | None = None,
        qdrant_url: str = "http://localhost:6333",
        dense_embedder: DenseEmbedder | None = None,
        sparse_embedder: SparseEmbedder | None = None,
        reranker: Reranker | None = None,
        dense_vector_name: str = "dense",
        sparse_vector_name: str = "sparse",
        default_limit: int = 3,
        default_fetch_k: int = 20,
    ) -> None:
        self.collection_name = collection_name
        self._qdrant_client = qdrant_client
        self.qdrant_url = qdrant_url
        self.dense_embedder = dense_embedder or OpenAIEmbedder()
        self.sparse_embedder = sparse_embedder or FastEmbedSparseEmbedder()
        self.reranker = reranker or HTTPReranker()
        self.dense_vector_name = dense_vector_name
        self.sparse_vector_name = sparse_vector_name
        self.default_limit = default_limit
        self.default_fetch_k = default_fetch_k

    @property
    def qdrant_client(self) -> QdrantClient:
        if self._qdrant_client is None:
            self._qdrant_client = QdrantClient(url=self.qdrant_url)
        return self._qdrant_client

    def search(self, query: str, *, limit: int | None = None, fetch_k: int | None = None) -> SearchResult:
        normalized_query = query.strip()
        if not normalized_query:
            return SearchResult(
                status="error",
                error=SearchError(type="invalid_query", message="query must not be empty"),
            )

        result_limit = limit or self.default_limit
        candidate_limit = max(fetch_k or self.default_fetch_k, result_limit)

        try:
            points = self._query_points(normalized_query, candidate_limit)
            if not points:
                return SearchResult(status="no_match")

            ranked_hits = self._rerank_points(normalized_query, points, result_limit)
            if not ranked_hits:
                return SearchResult(status="no_match")
            return SearchResult(status="ok", hits=ranked_hits)
        except Exception as exc:
            return SearchResult(
                status="error",
                error=SearchError(type=exc.__class__.__name__, message=str(exc)),
            )

    def _query_points(self, query: str, fetch_k: int) -> list[Any]:
        dense_vectors = self.dense_embedder.embed([query])
        sparse_vectors = self.sparse_embedder.embed([query])
        if not dense_vectors:
            raise RuntimeError("Dense embedder returned no vectors")
        if not sparse_vectors:
            raise RuntimeError("Sparse embedder returned no vectors")

        dense_query = dense_vectors[0]
        sparse_query = _coerce_sparse_vector(sparse_vectors[0])

        response = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                Prefetch(query=dense_query, using=self.dense_vector_name, limit=fetch_k),
                Prefetch(query=sparse_query, using=self.sparse_vector_name, limit=fetch_k),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=fetch_k,
            with_payload=True,
        )
        return list(getattr(response, "points", []) or [])

    def _rerank_points(self, query: str, points: list[Any], limit: int) -> list[SearchHit]:
        documents = [_extract_text(point.payload) for point in points if getattr(point, "payload", None)]
        if not documents:
            return []
        reranked_items = self.reranker.rerank(query, documents, top_n=min(limit, len(documents)))
        if not reranked_items:
            raise RuntimeError("Reranker returned no ranking results")

        hits: list[SearchHit] = []
        for rank, reranked_item in enumerate(reranked_items, start=1):
            index = int(reranked_item.get("index", -1))
            if index < 0 or index >= len(points):
                continue
            score = float(reranked_item.get("relevance_score", 0.0))
            hits.append(_point_to_hit(points[index], rank=rank, score=score))
        return hits


class SearchTool(BaseTool):
    name: str = "search"
    description: str = (
        "检索规则原文证据。工具会执行 dense + sparse 混合召回并使用 reranker 重排，"
        "返回原始命中文本和必要元数据，不会替你做规则结论。"
    )
    args_schema: type[BaseModel] = SearchInput

    searcher: HybridRuleSearcher = Field(exclude=True)

    def _run(self, query: str, limit: int = 3, fetch_k: int | None = None) -> dict[str, Any]:
        return self.searcher.search(query=query, limit=limit, fetch_k=fetch_k).model_dump(
            exclude_none=True
        )


def build_default_searcher(
    *,
    collection_name: str | None = None,
    qdrant_url: str | None = None,
    dense_vector_name: str = "dense",
    sparse_vector_name: str = "sparse",
    default_limit: int = 3,
    default_fetch_k: int = 20,
) -> HybridRuleSearcher:
    return HybridRuleSearcher(
        collection_name=collection_name or os.environ.get("QDRANT_COLLECTION", "dnd_5e_srd_hybrid"),
        qdrant_url=qdrant_url or os.environ.get("QDRANT_URL", "http://localhost:6333"),
        dense_vector_name=dense_vector_name,
        sparse_vector_name=sparse_vector_name,
        default_limit=default_limit,
        default_fetch_k=default_fetch_k,
    )


def create_search_tool(
    *,
    searcher: HybridRuleSearcher | None = None,
    collection_name: str | None = None,
    qdrant_url: str | None = None,
) -> SearchTool:
    return SearchTool(
        searcher=searcher or build_default_searcher(collection_name=collection_name, qdrant_url=qdrant_url)
    )


def _coerce_sparse_vector(value: Any) -> SparseVector:
    indices = getattr(value, "indices", None)
    values = getattr(value, "values", None)
    if indices is None or values is None:
        if isinstance(value, dict):
            indices = value.get("indices")
            values = value.get("values")
    if indices is None or values is None:
        raise TypeError("Sparse embedder output must expose indices and values")
    if hasattr(indices, "tolist"):
        indices = indices.tolist()
    if hasattr(values, "tolist"):
        values = values.tolist()
    return SparseVector(indices=list(indices), values=list(values))


def _extract_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    text = payload.get("content")
    if text is None:
        text = payload.get("text", "")
    return str(text)


def _point_to_hit(point: Any, *, rank: int, score: float) -> SearchHit:
    payload = getattr(point, "payload", None) or {}
    if not isinstance(payload, dict):
        payload = {}
    metadata = {key: value for key, value in payload.items() if key not in {"content", "text", "parent_content"}}
    point_id = getattr(point, "id", None)
    if point_id is not None:
        metadata.setdefault("point_id", str(point_id))
    return SearchHit(
        rank=rank,
        score=score,
        text=_extract_text(payload),
        metadata=metadata,
        parent_text=payload.get("parent_content"),
    )
