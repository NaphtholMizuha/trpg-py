from __future__ import annotations

import argparse
import sys
from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from augury.agent import (  # noqa: E402
    DEFAULT_CONTEXT_AGENT_EVAL_INTENT,
    mark_cli_ask_interaction_skipped,
    render_context_agent_eval,
    run_context_agent_eval,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a focused eval against the Context Agent.")
    parser.add_argument(
        "--intent",
        default=DEFAULT_CONTEXT_AGENT_EVAL_INTENT,
        help="Raw user intent that the main agent should turn into a Context Agent fact-collection task.",
    )
    parser.add_argument(
        "--instruction",
        dest="intent_alias",
        help="Deprecated alias for --intent.",
    )
    parser.add_argument(
        "--state-file",
        help="Optional TOML world-state file. Defaults to the versioned planner eval fixture.",
    )
    parser.add_argument(
        "--config",
        dest="config_path",
        help="Optional project config path used when constructing the planner runtime.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the full structured payload and bundle as JSON.",
    )
    args = parser.parse_args(argv)

    result = run_context_agent_eval(
        intent=args.intent_alias or args.intent,
        state_file=args.state_file,
        config_path=args.config_path,
        sync_ask=not args.json and sys.stdin.isatty(),
    )
    if not args.json and sys.stdin.isatty():
        pass
    elif result.bundle.ask_requests:
        skip_reason = (
            "Ask interaction was skipped because --json was requested."
            if args.json
            else "Ask interaction was skipped because stdin is not an interactive TTY."
        )
        result = mark_cli_ask_interaction_skipped(result, reason=skip_reason)
    print(render_context_agent_eval(result, output_format="json" if args.json else "human"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
