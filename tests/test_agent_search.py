from __future__ import annotations

import unittest
from types import SimpleNamespace

from trpg_py.agent.tools import HybridRuleSearcher, SearchResult, create_search_tool


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
    def __init__(self, *, points: list[SimpleNamespace] | None = None, error: Exception | None = None) -> None:
        self.points = points or []
        self.error = error
        self.calls: list[dict] = []

    def query_points(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(points=self.points)


def make_point(
    *,
    point_id: str,
    content: str,
    title: str,
    file: str,
    parent_content: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=point_id,
        score=0.1,
        payload={
            "content": content,
            "title": title,
            "file": file,
            "parent_content": parent_content,
            "locator": f"{file}#1",
        },
    )


class HybridRuleSearcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dense = FakeDenseEmbedder()
        self.sparse = FakeSparseEmbedder()

    def test_search_returns_reranked_hits_and_metadata(self) -> None:
        qdrant = FakeQdrantClient(
            points=[
                make_point(point_id="a", content="Magic Missile text", title="Magic Missile", file="phb"),
                make_point(
                    point_id="b",
                    content="Fireball text",
                    title="Fireball",
                    file="phb",
                    parent_content="Spellcasting chapter",
                ),
            ]
        )
        reranker = FakeReranker(
            results=[
                {"index": 1, "relevance_score": 0.93},
                {"index": 0, "relevance_score": 0.51},
            ]
        )
        searcher = HybridRuleSearcher(
            collection_name="rules",
            qdrant_client=qdrant,
            dense_embedder=self.dense,
            sparse_embedder=self.sparse,
            reranker=reranker,
        )

        result = searcher.search("fireball", limit=2, fetch_k=4)

        self.assertEqual("ok", result.status)
        self.assertEqual("Fireball text", result.hits[0].text)
        self.assertEqual("Magic Missile text", result.hits[1].text)
        self.assertEqual("Fireball", result.hits[0].metadata["title"])
        self.assertEqual("Spellcasting chapter", result.hits[0].parent_text)
        self.assertEqual([["fireball"]], self.dense.calls)
        self.assertEqual([["fireball"]], self.sparse.calls)
        self.assertEqual(4, qdrant.calls[0]["limit"])
        self.assertEqual(2, len(qdrant.calls[0]["prefetch"]))
        self.assertEqual(
            ("fireball", ["Magic Missile text", "Fireball text"], 2),
            reranker.calls[0],
        )

    def test_search_returns_no_match_when_qdrant_returns_no_points(self) -> None:
        searcher = HybridRuleSearcher(
            collection_name="rules",
            qdrant_client=FakeQdrantClient(points=[]),
            dense_embedder=self.dense,
            sparse_embedder=self.sparse,
            reranker=FakeReranker(results=[]),
        )

        result = searcher.search("shield")

        self.assertEqual("no_match", result.status)
        self.assertEqual([], result.hits)
        self.assertIsNone(result.error)

    def test_search_returns_error_when_qdrant_fails(self) -> None:
        searcher = HybridRuleSearcher(
            collection_name="rules",
            qdrant_client=FakeQdrantClient(error=RuntimeError("qdrant unavailable")),
            dense_embedder=self.dense,
            sparse_embedder=self.sparse,
            reranker=FakeReranker(results=[]),
        )

        result = searcher.search("counterspell")

        self.assertEqual("error", result.status)
        self.assertEqual("RuntimeError", result.error.type)
        self.assertIn("qdrant unavailable", result.error.message)

    def test_search_returns_error_when_reranker_fails(self) -> None:
        searcher = HybridRuleSearcher(
            collection_name="rules",
            qdrant_client=FakeQdrantClient(points=[make_point(point_id="a", content="Shield text", title="Shield", file="phb")]),
            dense_embedder=self.dense,
            sparse_embedder=self.sparse,
            reranker=FakeReranker(error=RuntimeError("rerank unavailable")),
        )

        result = searcher.search("shield")

        self.assertEqual("error", result.status)
        self.assertEqual("RuntimeError", result.error.type)
        self.assertIn("rerank unavailable", result.error.message)


class SearchToolWrapperTests(unittest.TestCase):
    def test_langchain_tool_reuses_searcher_result(self) -> None:
        dense = FakeDenseEmbedder()
        sparse = FakeSparseEmbedder()
        qdrant = FakeQdrantClient(
            points=[make_point(point_id="a", content="Fireball text", title="Fireball", file="phb")]
        )
        reranker = FakeReranker(results=[{"index": 0, "relevance_score": 0.88}])
        searcher = HybridRuleSearcher(
            collection_name="rules",
            qdrant_client=qdrant,
            dense_embedder=dense,
            sparse_embedder=sparse,
            reranker=reranker,
        )
        tool = create_search_tool(searcher=searcher)

        output = tool.invoke({"query": "fireball", "limit": 2, "fetch_k": 5})

        self.assertEqual("ok", output["status"])
        self.assertEqual("Fireball text", output["hits"][0]["text"])
        self.assertEqual(1, len(qdrant.calls))
        self.assertEqual(5, qdrant.calls[0]["limit"])
        self.assertEqual(("fireball", ["Fireball text"], 1), reranker.calls[0])


if __name__ == "__main__":
    unittest.main()
