from __future__ import annotations

"""
fetch_keys 功能演示脚本

使用方式:
  python test_fetch_keys.py
  python test_fetch_keys.py --prefix actors.goblin_1
  python test_fetch_keys.py --json
  python test_fetch_keys.py --state-file ./examples/fetch_keys_state.json --prefix actors.hero_1
"""

import argparse
import json
from pathlib import Path
from typing import Any

from trpg_py.agent.tools import create_fetch_keys_tool


DEFAULT_STATE: dict[str, Any] = {
    "actors": {
        "goblin_1": {"hp": {"current": 7, "max": 7}, "ac": 13, "tags": ["enemy", "small"]},
        "hero_1": {"hp": {"current": 20, "max": 24}, "ac": 16},
    },
    "round": 3,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="演示 fetch_keys 的全量与按范围枚举能力")
    parser.add_argument("--prefix", default=None, help="路径前缀过滤，例如 actors.goblin_1")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON 结果")
    parser.add_argument(
        "--state-file",
        default=None,
        help="可选 JSON 文件路径；提供后用该文件替代内置演示 state",
    )
    return parser


def load_state(path: str | None) -> dict[str, Any]:
    if path is None:
        return DEFAULT_STATE
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("state-file must contain a JSON object")
    return data


def main() -> int:
    args = build_parser().parse_args()
    state = load_state(args.state_file)
    tool = create_fetch_keys_tool(state=state)

    result_all = tool.invoke({})
    result_prefix = tool.invoke({"prefix": args.prefix}) if args.prefix else None
    result_no_match = tool.invoke({"prefix": "not.exists.prefix"})

    if args.json:
        payload = {
            "all": result_all,
            "prefix": result_prefix,
            "no_match": result_no_match,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("=" * 72)
    print("TRPG Agent Fetch Keys Smoke Test")
    print("=" * 72)
    print("全量枚举:")
    print_human_result(result_all)

    if args.prefix:
        print("-" * 72)
        print(f"按范围枚举: prefix={args.prefix}")
        print_human_result(result_prefix or {"status": "unknown", "items": []})

    print("-" * 72)
    print("无命中演示: prefix=not.exists.prefix")
    print_human_result(result_no_match)
    return 0


def print_human_result(result: dict[str, Any]) -> None:
    status = result.get("status", "unknown")
    print(f"status: {status}")
    if status == "error":
        error = result.get("error", {})
        print(f"error : {error.get('type', 'unknown')} - {error.get('message', '')}")
        return
    items = result.get("items", [])
    if not items:
        print("items : (none)")
        return
    print(f"items : {len(items)}")
    for item in items:
        print(f"- {item}")


if __name__ == "__main__":
    raise SystemExit(main())
