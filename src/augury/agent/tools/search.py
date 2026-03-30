from __future__ import annotations

from typing import Any, Literal

from langchain_core.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field

from augury.config import ProjectConfig
from augury.rag.retriever import (
    FastEmbedSparseEmbedder,
    HTTPReranker,
    OpenAIEmbedder,
    Retriever,
    RetrievedDocument,
    build_default_retriever,
)


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


class HybridRuleSearcher:
    def __init__(
        self,
        *,
        retriever: Retriever | None = None,
        collection_name: str | None = None,
        qdrant_url: str | None = None,
        dense_embedder: Any | None = None,
        sparse_embedder: Any | None = None,
        reranker: Any | None = None,
        dense_vector_name: str | None = None,
        sparse_vector_name: str | None = None,
        default_limit: int | None = None,
        default_fetch_k: int | None = None,
        project_config: ProjectConfig | None = None,
        config_path: str | None = None,
        qdrant_client: Any | None = None,
    ) -> None:
        self.retriever = retriever or Retriever(
            collection_name=collection_name,
            qdrant_client=qdrant_client,
            qdrant_url=qdrant_url,
            dense_embedder=dense_embedder,
            sparse_embedder=sparse_embedder,
            reranker=reranker,
            dense_vector_name=dense_vector_name,
            sparse_vector_name=sparse_vector_name,
            default_limit=default_limit,
            default_fetch_k=default_fetch_k,
            project_config=project_config,
            config_path=config_path,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self.retriever, name)

    def search(self, query: str, *, limit: int | None = None, fetch_k: int | None = None) -> SearchResult:
        return run_search(self.retriever, query=query, limit=limit, fetch_k=fetch_k)


class SearchTool(BaseTool):
    name: str = "search"
    description: str = (
        "检索规则原文证据。工具会执行 dense + sparse 混合召回并使用 reranker 重排，"
        "返回原始命中文本和必要元数据，不会替你做规则结论。"
    )
    args_schema: type[BaseModel] = SearchInput

    retriever: Retriever = Field(exclude=True)
    searcher: HybridRuleSearcher = Field(exclude=True)

    def _run(self, query: str, limit: int = 3, fetch_k: int | None = None) -> dict[str, Any]:
        return run_search(
            self.retriever,
            query=query,
            limit=limit,
            fetch_k=fetch_k,
        ).model_dump(exclude_none=True)


def run_search(
    retriever: Retriever,
    *,
    query: str,
    limit: int | None = None,
    fetch_k: int | None = None,
) -> SearchResult:
    normalized_query = query.strip()
    result_limit = limit or retriever.default_limit
    candidate_limit = max(fetch_k or retriever.default_fetch_k, result_limit)
    _log_search_input(query=normalized_query, limit=result_limit, fetch_k=candidate_limit)
    if not normalized_query:
        result = SearchResult(
            status="error",
            error=SearchError(type="invalid_query", message="query must not be empty"),
        )
        _log_search_output(result)
        return result

    try:
        documents = retriever.retrieve(
            normalized_query,
            limit=result_limit,
            fetch_k=candidate_limit,
        )
        if not documents:
            result = SearchResult(status="no_match")
            _log_search_output(result)
            return result
        result = SearchResult(
            status="ok",
            hits=[
                _retrieved_document_to_search_hit(document, rank=rank)
                for rank, document in enumerate(documents, start=1)
            ],
        )
        _log_search_output(result)
        return result
    except Exception as exc:
        result = SearchResult(
            status="error",
            error=SearchError(type=exc.__class__.__name__, message=str(exc)),
        )
        _log_search_output(result)
        return result


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
    retriever = build_default_retriever(
        collection_name=collection_name,
        qdrant_url=qdrant_url,
        dense_vector_name=dense_vector_name,
        sparse_vector_name=sparse_vector_name,
        default_limit=default_limit,
        default_fetch_k=default_fetch_k,
        project_config=project_config,
        config_path=config_path,
    )
    return HybridRuleSearcher(retriever=retriever)


def create_search_tool(
    *,
    retriever: Retriever | None = None,
    searcher: HybridRuleSearcher | None = None,
    collection_name: str | None = None,
    qdrant_url: str | None = None,
    project_config: ProjectConfig | None = None,
    config_path: str | None = None,
) -> SearchTool:
    resolved_retriever = retriever
    if resolved_retriever is None and searcher is not None:
        resolved_retriever = searcher.retriever
    if resolved_retriever is None:
        resolved_retriever = build_default_retriever(
            collection_name=collection_name,
            qdrant_url=qdrant_url,
            project_config=project_config,
            config_path=config_path,
        )
    resolved_searcher = searcher or HybridRuleSearcher(retriever=resolved_retriever)
    return SearchTool(retriever=resolved_retriever, searcher=resolved_searcher)


def _retrieved_document_to_search_hit(document: RetrievedDocument, *, rank: int) -> SearchHit:
    return SearchHit(
        rank=rank,
        score=document.score,
        text=document.text,
        metadata=dict(document.metadata),
        parent_text=document.parent_text,
    )


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
