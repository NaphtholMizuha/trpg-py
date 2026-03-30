from __future__ import annotations

"""
lint 工具演示脚本

使用方式:
  python src/smoke/test_linter.py
  python src/smoke/test_linter.py --json
  python src/smoke/test_linter.py --document-file ./examples/goblin_scimitar_attack.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from augury.agent.tools import create_lint_tool


DEFAULT_DOCUMENT_FILE = PROJECT_ROOT / "examples" / "goblin_scimitar_attack.json"
DEFAULT_INVALID_DOCUMENT = {
    "task_id": "broken_attack",
    "version": 1,
    "steps": [
        {
            "action": "attack",
            "actor": "goblin_1",
            "target": "hero_1",
        }
    ],
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="演示 lint 工具对候选 TaskDocument 的只读校验能力")
    parser.add_argument(
        "--document-file",
        default=str(DEFAULT_DOCUMENT_FILE),
        help="合法样例 JSON 文件路径，默认使用 examples/goblin_scimitar_attack.json",
    )
    parser.add_argument("--json", action="store_true", help="仅输出 JSON 结果")
    return parser


def load_document(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("document-file must contain a JSON object")
    return payload


def main() -> int:
    args = build_parser().parse_args()
    document_path = Path(args.document_file).expanduser().resolve()

    tool = create_lint_tool()
    valid_document = load_document(document_path)
    result_valid = tool.invoke({"task_document": valid_document})
    result_invalid = tool.invoke({"task_document": DEFAULT_INVALID_DOCUMENT})

    if args.json:
        payload = {
            "valid": result_valid,
            "invalid": result_invalid,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("=" * 72)
    print("TRPG Agent Lint Smoke Test")
    print("=" * 72)
    print(f"document   : {document_path}")
    print("valid demo :")
    print_human_result(result_valid)
    print("-" * 72)
    print("invalid demo:")
    print_human_result(result_invalid)
    return 0


def print_human_result(result: dict[str, Any]) -> None:
    status = result.get("status", "unknown")
    print(f"status     : {status}")
    summary = result.get("summary")
    if summary:
        print(f"summary    : {summary}")
    if status == "error":
        error = result.get("error", {})
        print(f"error      : {error.get('type', 'unknown')} - {error.get('message', '')}")
        return
    issues = result.get("issues", [])
    if not issues:
        print("issues     : (none)")
        return
    print(f"issues     : {len(issues)}")
    for issue in issues:
        path = issue.get("path", "")
        message = issue.get("message", "")
        code = issue.get("code")
        prefix = f"- {path}" if path else "-"
        suffix = f" ({code})" if code else ""
        print(f"{prefix}: {message}{suffix}")


if __name__ == "__main__":
    raise SystemExit(main())
