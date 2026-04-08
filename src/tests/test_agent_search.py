from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from loguru import logger

try:
    from augury.agent.planner_runtime_guards import activate_planner_runtime_guard
except ModuleNotFoundError:  # pragma: no cover - compatibility fallback for src-layout test runs
    def activate_planner_runtime_guard():  # type: ignore[no-redef]
        return nullcontext()
from tests.config_helpers import write_project_config
from augury.agent.tools import HybridRuleSearcher, SearchResult, build_default_searcher, create_search_tool
from augury.config import clear_project_config_cache
from augury.rag import OpenAIEmbedder, Retriever


class FakeDenseEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeSparseEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[SimpleNamespace]:
        self.calls.append(texts)
        return [SimpleNamespace(indices=[1, 2], values=[0.4, 0.6]) for _ in texts]


class FakeReranker:
    def __init__(self, results: list[dict] | None = None, error: Exception | None = None) -> None:
        self.results = results or []
        self.error = error
        self.calls: list[tuple[str, list[str], int]] = []

    def rerank(self, query: str, documents: list[str], top_n: int) -> list[dict]:
        self.calls.append((query, documents, top_n))
        if self.error is not None:
            raise self.error
        return self.results


class FakeQdrantClient:
    def __init__(
        self,
        *,
        points: list[SimpleNamespace] | None = None,
        parents: dict[str, SimpleNamespace] | None = None,
        error: Exception | None = None,
        retrieve_error: Exception | None = None,
    ) -> None:
        self.points = points or []
        self.parents = parents or {}
        self.error = error
        self.retrieve_error = retrieve_error
        self.calls: list[dict] = []
        self.retrieve_calls: list[dict] = []

    def query_points(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(points=self.points)

    def retrieve(self, **kwargs: object) -> list[SimpleNamespace]:
        self.retrieve_calls.append(kwargs)
        if self.retrieve_error is not None:
            raise self.retrieve_error
        ids = kwargs.get("ids", [])
        return [self.parents[str(parent_id)] for parent_id in ids if str(parent_id) in self.parents]


def make_point(
    *,
    point_id: str,
    text: str,
    title: str,
    book: str = "玩家手册2024",
    path: str = "/rules/example",
    doc_type: str = "rule_article",
    section_titles: list[str] | None = None,
    parent_id: str | None = None,
) -> SimpleNamespace:
    payload = {
        "text": text,
        "title": title,
        "book": book,
        "path": path,
        "doc_type": doc_type,
    }
    if section_titles is not None:
        payload["section_titles"] = section_titles
    if parent_id is not None:
        payload["parent_id"] = parent_id
    return SimpleNamespace(id=point_id, score=0.1, payload=payload)


class RetrieverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dense = FakeDenseEmbedder()
        self.sparse = FakeSparseEmbedder()
        self.env_patcher = patch.dict(
            os.environ,
            {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
            clear=False,
        )
        self.env_patcher.start()

    def tearDown(self) -> None:
        self.env_patcher.stop()
        clear_project_config_cache()

    def test_retriever_returns_reranked_hits_with_schema_metadata_and_parent_text(self) -> None:
        qdrant = FakeQdrantClient(
            points=[
                make_point(
                    point_id="spell-magic-missile",
                    text="Magic Missile text",
                    title="Magic Missile",
                    path="/phb/spells/magic-missile",
                    doc_type="spell",
                    section_titles=["法术"],
                ),
                make_point(
                    point_id="spell-fireball-effect",
                    text="Fireball text",
                    title="Fireball",
                    path="/phb/spells/fireball/effect",
                    doc_type="spell",
                    section_titles=["法术", "塑能"],
                    parent_id="spell-fireball",
                ),
            ],
            parents={
                "spell-fireball": make_point(
                    point_id="spell-fireball",
                    text="Fireball full parent text",
                    title="Fireball",
                    path="/phb/spells/fireball",
                    doc_type="spell",
                    section_titles=["法术"],
                )
            },
        )
        reranker = FakeReranker(
            results=[
                {"index": 1, "relevance_score": 0.93},
                {"index": 0, "relevance_score": 0.51},
            ]
        )
        retriever = Retriever(
            collection_name="trpg_knowledge",
            qdrant_client=qdrant,
            dense_embedder=self.dense,
            sparse_embedder=self.sparse,
            reranker=reranker,
        )

        result = retriever.retrieve("fireball", limit=2, fetch_k=4)

        self.assertEqual("Fireball text", result[0].text)
        self.assertEqual("Magic Missile text", result[1].text)
        self.assertEqual("Fireball", result[0].metadata["title"])
        self.assertEqual("spell", result[0].metadata["doc_type"])
        self.assertEqual("/phb/spells/fireball/effect", result[0].metadata["path"])
        self.assertEqual(["法术", "塑能"], result[0].metadata["section_titles"])
        self.assertEqual("spell-fireball", result[0].metadata["parent_id"])
        self.assertEqual("Fireball full parent text", result[0].parent_text)
        self.assertEqual([["fireball"]], self.dense.calls)
        self.assertEqual([["fireball"]], self.sparse.calls)
        self.assertEqual(4, qdrant.calls[0]["limit"])
        self.assertEqual(2, len(qdrant.calls[0]["prefetch"]))
        self.assertEqual(["spell-fireball"], qdrant.retrieve_calls[0]["ids"])
        self.assertEqual("fireball", reranker.calls[0][0])
        self.assertEqual(2, reranker.calls[0][2])
        self.assertIn("Fireball", reranker.calls[0][1][1])
        self.assertIn("Fireball text", reranker.calls[0][1][1])

    def test_retriever_accepts_mode_without_changing_core_flow(self) -> None:
        qdrant = FakeQdrantClient(
            points=[
                make_point(
                    point_id="spell-fireball",
                    text="Fireball text",
                    title="Fireball",
                    path="/phb/spells/fireball",
                    doc_type="spell",
                )
            ]
        )
        retriever = Retriever(
            collection_name="trpg_knowledge",
            qdrant_client=qdrant,
            dense_embedder=self.dense,
            sparse_embedder=self.sparse,
            reranker=FakeReranker(results=[{"index": 0, "relevance_score": 0.88}]),
        )

        result = retriever.retrieve("Fireball", mode="term")

        self.assertEqual(1, len(result))
        self.assertEqual("Fireball text", result[0].text)

    def test_retriever_parent_fetch_failure_does_not_drop_hit(self) -> None:
        retriever = Retriever(
            collection_name="trpg_knowledge",
            qdrant_client=FakeQdrantClient(
                points=[
                    make_point(
                        point_id="spell-shield-effect",
                        text="Shield text",
                        title="Shield",
                        path="/phb/spells/shield/effect",
                        doc_type="spell",
                        section_titles=["法术"],
                        parent_id="spell-shield",
                    )
                ],
                retrieve_error=RuntimeError("parent fetch unavailable"),
            ),
            dense_embedder=self.dense,
            sparse_embedder=self.sparse,
            reranker=FakeReranker(results=[{"index": 0, "relevance_score": 0.88}]),
        )

        result = retriever.retrieve("shield")

        self.assertEqual(1, len(result))
        self.assertEqual("Shield text", result[0].text)
        self.assertIsNone(result[0].parent_text)


class HybridRuleSearcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dense = FakeDenseEmbedder()
        self.sparse = FakeSparseEmbedder()
        self.log_output = io.StringIO()
        self.log_handler_id = logger.add(self.log_output, format="{message}")
        self.env_patcher = patch.dict(
            os.environ,
            {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
            clear=False,
        )
        self.env_patcher.start()

    def tearDown(self) -> None:
        self.env_patcher.stop()
        logger.remove(self.log_handler_id)
        clear_project_config_cache()

    def test_search_returns_no_match_when_qdrant_returns_no_points(self) -> None:
        searcher = HybridRuleSearcher(
            collection_name="trpg_knowledge",
            qdrant_client=FakeQdrantClient(points=[]),
            dense_embedder=self.dense,
            sparse_embedder=self.sparse,
            reranker=FakeReranker(results=[]),
        )

        result = searcher.search("shield")

        self.assertEqual("no_match", result.status)
        self.assertEqual([], result.hits)
        self.assertIsNone(result.error)
        logs = self.log_output.getvalue()
        self.assertIn("mode=balanced", logs)
        self.assertIn("tool_output tool=search status=no_match hits=0", logs)

    def test_search_records_explicit_mode_in_logs(self) -> None:
        searcher = HybridRuleSearcher(
            collection_name="trpg_knowledge",
            qdrant_client=FakeQdrantClient(points=[]),
            dense_embedder=self.dense,
            sparse_embedder=self.sparse,
            reranker=FakeReranker(results=[]),
        )

        searcher.search("火球术 Fireball", mode="term")

        logs = self.log_output.getvalue()
        self.assertIn("mode=term", logs)

    def test_search_short_circuits_repeated_query_with_runtime_guard(self) -> None:
        searcher = HybridRuleSearcher(
            collection_name="trpg_knowledge",
            qdrant_client=FakeQdrantClient(points=[]),
            dense_embedder=self.dense,
            sparse_embedder=self.sparse,
            reranker=FakeReranker(results=[]),
        )

        with activate_planner_runtime_guard():
            first = searcher.search("shield")
            second = searcher.search("shield")

        self.assertEqual(first, second)
        logs = self.log_output.getvalue()
        if "tool_guard tool=search kind=repeated_theme" in logs:
            self.assertIn("tool_guard tool=search kind=repeated_theme", logs)
        else:
            self.assertEqual(2, logs.count("tool_input tool=search"))

    def test_search_returns_error_when_qdrant_fails(self) -> None:
        searcher = HybridRuleSearcher(
            collection_name="trpg_knowledge",
            qdrant_client=FakeQdrantClient(error=RuntimeError("qdrant unavailable")),
            dense_embedder=self.dense,
            sparse_embedder=self.sparse,
            reranker=FakeReranker(results=[]),
        )

        result = searcher.search("counterspell")

        self.assertEqual("error", result.status)
        self.assertEqual("RuntimeError", result.error.type)
        self.assertIn("qdrant unavailable", result.error.message)
        logs = self.log_output.getvalue()
        self.assertIn("tool_output tool=search status=error", logs)
        self.assertIn("error_type=RuntimeError", logs)

    def test_search_returns_error_when_reranker_fails(self) -> None:
        searcher = HybridRuleSearcher(
            collection_name="trpg_knowledge",
            qdrant_client=FakeQdrantClient(
                points=[
                    make_point(
                        point_id="spell-shield",
                        text="Shield text",
                        title="Shield",
                        path="/phb/spells/shield",
                        doc_type="spell",
                    )
                ]
            ),
            dense_embedder=self.dense,
            sparse_embedder=self.sparse,
            reranker=FakeReranker(error=RuntimeError("rerank unavailable")),
        )

        result = searcher.search("shield")

        self.assertEqual("error", result.status)
        self.assertEqual("RuntimeError", result.error.type)
        self.assertIn("rerank unavailable", result.error.message)

    def test_build_default_searcher_uses_project_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")
            searcher = build_default_searcher(config_path=str(config_path))

        self.assertEqual("rules", searcher.collection_name)
        self.assertEqual("http://qdrant.example:6333", searcher.qdrant_url)
        self.assertEqual("dense_vec", searcher.dense_vector_name)
        self.assertEqual("sparse_vec", searcher.sparse_vector_name)
        self.assertEqual(4, searcher.default_limit)
        self.assertEqual(11, searcher.default_fetch_k)
        self.assertIsInstance(searcher.dense_embedder, OpenAIEmbedder)
        self.assertEqual("dense-model", searcher.dense_embedder.model)
        self.assertEqual("https://search.example/v1", searcher.dense_embedder.base_url)

    def test_explicit_searcher_dependencies_do_not_require_project_config(self) -> None:
        searcher = HybridRuleSearcher(
            collection_name="explicit-rules",
            qdrant_url="http://explicit-qdrant:6333",
            dense_vector_name="dense",
            sparse_vector_name="sparse",
            default_limit=2,
            default_fetch_k=5,
            dense_embedder=self.dense,
            sparse_embedder=self.sparse,
            reranker=FakeReranker(results=[]),
            config_path="/tmp/definitely-missing-config.toml",
        )

        self.assertEqual("explicit-rules", searcher.collection_name)
        self.assertEqual("http://explicit-qdrant:6333", searcher.qdrant_url)


class SearchToolWrapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patcher = patch.dict(
            os.environ,
            {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
            clear=False,
        )
        self.env_patcher.start()

    def tearDown(self) -> None:
        self.env_patcher.stop()
        clear_project_config_cache()

    def test_langchain_tool_reuses_retriever_result(self) -> None:
        dense = FakeDenseEmbedder()
        sparse = FakeSparseEmbedder()
        qdrant = FakeQdrantClient(
            points=[
                make_point(
                    point_id="spell-fireball",
                    text="Fireball text",
                    title="Fireball",
                    path="/phb/spells/fireball",
                    doc_type="spell",
                )
            ]
        )
        reranker = FakeReranker(results=[{"index": 0, "relevance_score": 0.88}])
        retriever = Retriever(
            collection_name="trpg_knowledge",
            qdrant_client=qdrant,
            dense_embedder=dense,
            sparse_embedder=sparse,
            reranker=reranker,
        )
        tool = create_search_tool(retriever=retriever)

        output = tool.invoke({"query": "fireball", "mode": "term", "limit": 2, "fetch_k": 5})

        self.assertEqual("ok", output["status"])
        self.assertEqual("Fireball text", output["hits"][0]["text"])
        self.assertEqual(1, len(qdrant.calls))
        self.assertEqual(5, qdrant.calls[0]["limit"])
        self.assertEqual(("fireball", ["Fireball\n\nFireball text"], 1), reranker.calls[0])
        self.assertIs(tool.retriever, retriever)
        self.assertIs(tool.searcher.retriever, retriever)

    def test_search_input_defaults_mode_to_balanced(self) -> None:
        payload = create_search_tool(
            retriever=Retriever(
                collection_name="trpg_knowledge",
                qdrant_client=FakeQdrantClient(
                    points=[
                        make_point(
                            point_id="spell-fireball",
                            text="Fireball text",
                            title="Fireball",
                            path="/phb/spells/fireball",
                            doc_type="spell",
                        )
                    ]
                ),
                dense_embedder=FakeDenseEmbedder(),
                sparse_embedder=FakeSparseEmbedder(),
                reranker=FakeReranker(results=[{"index": 0, "relevance_score": 0.88}]),
            )
        ).invoke({"query": "fireball"})

        self.assertEqual("ok", payload["status"])

    def test_create_search_tool_builds_default_searcher_from_project_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")
            tool = create_search_tool(config_path=str(config_path))

        self.assertEqual("rules", tool.searcher.collection_name)
        self.assertEqual("http://qdrant.example:6333", tool.searcher.qdrant_url)
        self.assertEqual(4, tool.searcher.default_limit)


if __name__ == "__main__":
    unittest.main()
