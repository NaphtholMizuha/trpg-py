from __future__ import annotations

from typing import Any, Protocol, cast

import requests
from fastembed import SparseTextEmbedding
from openai import OpenAI
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.models import Fusion, FusionQuery, Prefetch, SparseVector

from augury.config import ProjectConfig, SearchConfig, load_project_config


class DenseEmbedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class SparseEmbedder(Protocol):
    def embed(self, texts: list[str]) -> list[Any]: ...


class Reranker(Protocol):
    def rerank(self, query: str, documents: list[str], top_n: int) -> list[dict[str, Any]]: ...


class RetrievedDocument(BaseModel):
    score: float
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    parent_text: str | None = None


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


class Retriever:
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

    def retrieve(
        self,
        query: str,
        *,
        limit: int | None = None,
        fetch_k: int | None = None,
    ) -> list[RetrievedDocument]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")
        result_limit = limit or self.default_limit
        candidate_limit = max(fetch_k or self.default_fetch_k, result_limit)
        points = self._query_points(normalized_query, candidate_limit)
        if not points:
            return []
        hits = self._rerank_points(normalized_query, points, result_limit)
        self._attach_parent_context(hits)
        return hits

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

    def _rerank_points(self, query: str, points: list[Any], limit: int) -> list[RetrievedDocument]:
        candidate_points: list[Any] = []
        documents: list[str] = []
        for point in points:
            payload = getattr(point, "payload", None)
            document = _build_rerank_document(payload)
            text = _extract_text(payload)
            if not document or not text:
                continue
            candidate_points.append(point)
            documents.append(document)
        if not documents:
            return []

        reranked_items = self.reranker.rerank(query, documents, top_n=min(limit, len(documents)))
        if not reranked_items:
            raise RuntimeError("Reranker returned no ranking results")

        hits: list[RetrievedDocument] = []
        for reranked_item in reranked_items:
            index = int(reranked_item.get("index", -1))
            if index < 0 or index >= len(candidate_points):
                continue
            score = float(reranked_item.get("relevance_score", 0.0))
            hits.append(_point_to_retrieved_document(candidate_points[index], score=score))
        return hits

    def _attach_parent_context(self, hits: list[RetrievedDocument]) -> None:
        parent_ids: list[Any] = []
        seen_parent_ids: set[str] = set()
        for hit in hits:
            parent_id = hit.metadata.get("parent_id")
            if parent_id is None:
                continue
            normalized = str(parent_id)
            if normalized in seen_parent_ids:
                continue
            seen_parent_ids.add(normalized)
            parent_ids.append(parent_id)
        if not parent_ids:
            return

        parent_text_by_id = self._fetch_parent_texts(parent_ids)
        for hit in hits:
            parent_id = hit.metadata.get("parent_id")
            if parent_id is None:
                continue
            parent_text = parent_text_by_id.get(str(parent_id))
            if parent_text:
                hit.parent_text = parent_text

    def _fetch_parent_texts(self, parent_ids: list[Any]) -> dict[str, str]:
        retrieve = getattr(self.qdrant_client, "retrieve", None)
        if not callable(retrieve):
            return {}
        try:
            parent_points = retrieve(
                collection_name=self.collection_name,
                ids=parent_ids,
                with_payload=True,
            )
        except Exception:
            return {}

        parent_text_by_id: dict[str, str] = {}
        for point in parent_points or []:
            point_id = getattr(point, "id", None)
            if point_id is None:
                continue
            text = _extract_text(getattr(point, "payload", None))
            if text:
                parent_text_by_id[str(point_id)] = text
        return parent_text_by_id


def build_default_retriever(
    *,
    collection_name: str | None = None,
    qdrant_url: str | None = None,
    dense_vector_name: str | None = None,
    sparse_vector_name: str | None = None,
    default_limit: int | None = None,
    default_fetch_k: int | None = None,
    project_config: ProjectConfig | None = None,
    config_path: str | None = None,
) -> Retriever:
    return Retriever(
        collection_name=collection_name,
        qdrant_url=qdrant_url,
        dense_vector_name=dense_vector_name,
        sparse_vector_name=sparse_vector_name,
        default_limit=default_limit,
        default_fetch_k=default_fetch_k,
        project_config=project_config,
        config_path=config_path,
    )


def _resolve_search_config(
    *,
    project_config: ProjectConfig | None = None,
    config_path: str | None = None,
) -> SearchConfig:
    return (project_config or load_project_config(config_path)).search


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
    text = payload.get("text")
    if text is None:
        text = payload.get("content")
    if text is None:
        return ""
    return str(text)


def _build_rerank_document(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    parts: list[str] = []
    title = payload.get("title")
    if title:
        parts.append(str(title))
    section_titles = payload.get("section_titles")
    if isinstance(section_titles, list):
        rendered_sections = " > ".join(str(item) for item in section_titles if item)
        if rendered_sections:
            parts.append(rendered_sections)
    text = _extract_text(payload)
    if text:
        parts.append(text)
    return "\n\n".join(parts)


def _point_to_retrieved_document(point: Any, *, score: float) -> RetrievedDocument:
    payload = getattr(point, "payload", None) or {}
    if not isinstance(payload, dict):
        payload = {}
    metadata: dict[str, Any] = {}
    for key in ("book", "path", "doc_type", "title", "parent_id", "section_titles"):
        value = payload.get(key)
        if value is not None:
            metadata[key] = value
    point_id = getattr(point, "id", None)
    if point_id is not None:
        metadata.setdefault("point_id", str(point_id))
    return RetrievedDocument(
        score=score,
        text=_extract_text(payload),
        metadata=metadata,
    )
