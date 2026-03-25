from __future__ import annotations

"""
真实向量库检索测试脚本

使用方式:
  python test_search.py "fireball spell"
  python test_search.py "goblin ranged attack in melee disadvantage" --limit 5 --fetch-k 25
  python test_search.py --tool "healing word spell"
  python test_search.py --json "counterspell reaction timing"

环境变量:
  QDRANT_URL           - Qdrant 地址，默认 http://localhost:6333
  QDRANT_COLLECTION    - 集合名，默认 dnd_5e_srd_hybrid
  SILICONFLOW_API_KEY  - dense embedding / reranker 默认 API key
  SILICONFLOW_BASE_URL - dense embedding / reranker 默认 base URL
  OPENAI_API_KEY       - 如果不用 SiliconFlow，可作为备选 API key
"""

import argparse
import json
import sys
from typing import Any

from trpg_py.agent.tools import build_default_searcher, create_search_tool

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


DEFAULT_QUERY = "fireball spell dexterity save 8d6 fire damage"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="测试真实 D&D 向量数据库检索")
    parser.add_argument(
        "query",
        nargs="?",
        default=DEFAULT_QUERY,
        help=f"检索问题或关键词，默认: {DEFAULT_QUERY!r}",
    )
    parser.add_argument("--limit", type=int, default=3, help="最终返回命中数")
    parser.add_argument("--fetch-k", type=int, default=20, help="混合召回候选数")
    parser.add_argument("--collection", default=None, help="Qdrant collection 名称")
    parser.add_argument("--qdrant-url", default=None, help="Qdrant 地址")
    parser.add_argument("--dense-vector-name", default="dense", help="Qdrant dense 向量名")
    parser.add_argument("--sparse-vector-name", default="sparse", help="Qdrant sparse 向量名")
    parser.add_argument(
        "--tool",
        action="store_true",
        help="通过 LangChain SearchTool.invoke() 调用，而不是直接调用 searcher.search()",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 形式打印完整结果")
    parser.add_argument(
        "--show-parent",
        action="store_true",
        help="打印 parent_text 预览（如果 payload 中存在）",
    )
    return parser


def main() -> int:
    if load_dotenv is not None:
        load_dotenv()

    args = build_parser().parse_args()

    searcher = build_default_searcher(
        collection_name=args.collection,
        qdrant_url=args.qdrant_url,
        dense_vector_name=args.dense_vector_name,
        sparse_vector_name=args.sparse_vector_name,
        default_limit=args.limit,
        default_fetch_k=args.fetch_k,
    )

    if args.tool:
        tool = create_search_tool(searcher=searcher)
        result: dict[str, Any] = tool.invoke(
            {"query": args.query, "limit": args.limit, "fetch_k": args.fetch_k}
        )
    else:
        result = searcher.search(args.query, limit=args.limit, fetch_k=args.fetch_k).model_dump(
            exclude_none=True
        )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    return print_human_readable(args.query, result, show_parent=args.show_parent)


def print_human_readable(query: str, result: dict[str, Any], *, show_parent: bool) -> int:
    status = result.get("status", "unknown")
    print("=" * 72)
    print("TRPG Agent Search Smoke Test")
    print("=" * 72)
    print(f"query : {query}")
    print(f"status: {status}")

    if status == "error":
        error = result.get("error", {})
        print(f"error : {error.get('type', 'unknown')} - {error.get('message', '')}")
        return 1

    hits = result.get("hits", [])
    if not hits:
        print("hits  : (none)")
        return 0

    print(f"hits  : {len(hits)}")
    for hit in hits:
        metadata = hit.get("metadata", {})
        print("-" * 72)
        print(
            f"[{hit.get('rank', '?')}] score={hit.get('score', 0):.4f} "
            f"title={metadata.get('title', '(untitled)')}"
        )
        if metadata:
            summary = ", ".join(
                f"{key}={value}"
                for key, value in metadata.items()
                if key in {"file", "section", "locator", "type", "point_id", "title"}
            )
            if summary:
                print(f"meta : {summary}")
        print("text :")
        print(indent_block(truncate(hit.get("text", ""), 1200)))
        if show_parent and hit.get("parent_text"):
            print("parent:")
            print(indent_block(truncate(hit["parent_text"], 500)))
    print("-" * 72)
    return 0


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...[truncated]"


def indent_block(text: str) -> str:
    return "\n".join(f"  {line}" for line in text.splitlines() or [""])


if __name__ == "__main__":
    raise SystemExit(main())
