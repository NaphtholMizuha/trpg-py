from __future__ import annotations

from typing import Any, Literal, Protocol, cast

import requests
from fastembed import SparseTextEmbedding
from langchain_core.tools import BaseTool
from loguru import logger
from openai import OpenAI
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.models import Fusion, FusionQuery, Prefetch, SparseVector

from trpg_py.config import ProjectConfig, SearchConfig, load_project_config


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
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        project_config: ProjectConfig | None = None,
        config_path: str | None = None,
    ) -> None:
        search_config = None
        if model is None or api_key is None or base_url is None:
            search_config = _resolve_search_config(project_config=project_config, config_path=config_path)
        self.model = model or search_config.models.dense_embedding
        self.api_key = api_key or search_config.api.api_key
        self.base_url = base_url or search_config.api.base_url
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
    def __init__(
        self,
        *,
        model_name: str | None = None,
        project_config: ProjectConfig | None = None,
        config_path: str | None = None,
    ) -> None:
        search_config = None
        if model_name is None:
            search_config = _resolve_search_config(project_config=project_config, config_path=config_path)
        self.model_name = model_name or search_config.models.sparse_embedding
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
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        session: requests.Session | None = None,
        project_config: ProjectConfig | None = None,
        config_path: str | None = None,
    ) -> None:
        search_config = None
        if model is None or api_key is None or base_url is None or timeout is None:
            search_config = _resolve_search_config(project_config=project_config, config_path=config_path)
        self.model = model or search_config.models.reranker
        self.api_key = api_key or search_config.api.api_key
        self.base_url = base_url or search_config.api.base_url
        self.timeout = timeout or search_config.rerank_timeout
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
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return cast(list[dict[str, Any]], payload.get("results", []))


class HybridRuleSearcher:
    def __init__(
        self,
        *,
        collection_name: str | None = None,
        qdrant_client: QdrantClient | None = None,
        qdrant_url: str | None = None,
        dense_embedder: DenseEmbedder | None = None,
        sparse_embedder: SparseEmbedder | None = None,
        reranker: Reranker | None = None,
        dense_vector_name: str | None = None,
        sparse_vector_name: str | None = None,
        default_limit: int | None = None,
        default_fetch_k: int | None = None,
        project_config: ProjectConfig | None = None,
        config_path: str | None = None,
    ) -> None:
        search_config = None
        if (
            collection_name is None
            or qdrant_url is None
            or dense_vector_name is None
            or sparse_vector_name is None
            or default_limit is None
            or default_fetch_k is None
            or dense_embedder is None
            or sparse_embedder is None
            or reranker is None
        ):
            search_config = _resolve_search_config(project_config=project_config, config_path=config_path)
        self.collection_name = collection_name or search_config.qdrant.collection_name
        self._qdrant_client = qdrant_client
        self.qdrant_url = qdrant_url or search_config.qdrant.url
        self.dense_embedder = dense_embedder or OpenAIEmbedder(
            project_config=project_config,
            config_path=config_path,
        )
        self.sparse_embedder = sparse_embedder or FastEmbedSparseEmbedder(
            project_config=project_config,
            config_path=config_path,
        )
        self.reranker = reranker or HTTPReranker(
            project_config=project_config,
            config_path=config_path,
        )
        self.dense_vector_name = dense_vector_name or search_config.qdrant.dense_vector_name
        self.sparse_vector_name = sparse_vector_name or search_config.qdrant.sparse_vector_name
        self.default_limit = default_limit or search_config.default_limit
        self.default_fetch_k = default_fetch_k or search_config.default_fetch_k

    @property
    def qdrant_client(self) -> QdrantClient:
        if self._qdrant_client is None:
            self._qdrant_client = QdrantClient(url=self.qdrant_url)
        return self._qdrant_client

    def search(self, query: str, *, limit: int | None = None, fetch_k: int | None = None) -> SearchResult:
        normalized_query = query.strip()
        result_limit = limit or self.default_limit
        candidate_limit = max(fetch_k or self.default_fetch_k, result_limit)
        _log_search_input(query=normalized_query, limit=result_limit, fetch_k=candidate_limit)
        if not normalized_query:
            result = SearchResult(
                status="error",
                error=SearchError(type="invalid_query", message="query must not be empty"),
            )
            _log_search_output(result)
            return result

        try:
            points = self._query_points(normalized_query, candidate_limit)
            if not points:
                result = SearchResult(status="no_match")
                _log_search_output(result)
                return result

            ranked_hits = self._rerank_points(normalized_query, points, result_limit)
            if not ranked_hits:
                result = SearchResult(status="no_match")
                _log_search_output(result)
                return result
            result = SearchResult(status="ok", hits=ranked_hits)
            _log_search_output(result)
            return result
        except Exception as exc:
            result = SearchResult(
                status="error",
                error=SearchError(type=exc.__class__.__name__, message=str(exc)),
            )
            _log_search_output(result)
            return result

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
    dense_vector_name: str | None = None,
    sparse_vector_name: str | None = None,
    default_limit: int | None = None,
    default_fetch_k: int | None = None,
    project_config: ProjectConfig | None = None,
    config_path: str | None = None,
) -> HybridRuleSearcher:
    return HybridRuleSearcher(
        collection_name=collection_name,
        qdrant_url=qdrant_url,
        dense_vector_name=dense_vector_name,
        sparse_vector_name=sparse_vector_name,
        default_limit=default_limit,
        default_fetch_k=default_fetch_k,
        project_config=project_config,
        config_path=config_path,
    )


def create_search_tool(
    *,
    searcher: HybridRuleSearcher | None = None,
    collection_name: str | None = None,
    qdrant_url: str | None = None,
    project_config: ProjectConfig | None = None,
    config_path: str | None = None,
) -> SearchTool:
    return SearchTool(
        searcher=searcher
        or build_default_searcher(
            collection_name=collection_name,
            qdrant_url=qdrant_url,
            project_config=project_config,
            config_path=config_path,
        )
    )


def _resolve_search_config(
    *,
    project_config: ProjectConfig | None = None,
    config_path: str | None = None,
) -> SearchConfig:
    return (project_config or load_project_config(config_path)).search


def _log_search_input(*, query: str, limit: int, fetch_k: int) -> None:
    logger.info(
        "tool_input tool=search query={!r} limit={} fetch_k={}",
        query,
        limit,
        fetch_k,
    )


def _log_search_output(result: SearchResult) -> None:
    if result.status == "ok":
        sample_titles = [
            hit.metadata.get("title", "<unknown>")
            for hit in result.hits[:3]
            if isinstance(hit.metadata, dict)
        ]
        logger.info(
            "tool_output tool=search status=ok hits={} sample_titles={}",
            len(result.hits),
            sample_titles,
        )
        return
    if result.status == "no_match":
        logger.info("tool_output tool=search status=no_match hits=0")
        return
    logger.error(
        "tool_output tool=search status=error error_type={} error_message={!r}",
        result.error.type if result.error else "unknown",
        result.error.message if result.error else "",
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
