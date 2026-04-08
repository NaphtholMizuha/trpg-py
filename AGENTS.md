# TRPG Planner Runtime — AGENTS.md

## Project Layout

```
src/augury/        Main package — agent orchestration, engine, planner, RAG, store
config/            Runtime configuration (config.toml)
examples/evals/    End-to-end test fixtures (planner_e2e/)
openspec/          Spec-driven development workflow
```

## Core Architecture

**Delegated multi-agent pipeline:**

```
Main Agent → Context Agent → Resolution Agent
```

- **Main Agent** (`src/augury/agent/runtime.py`): Entry point, orchestrates flow
- **Context Agent**: Gathers situational context, resolves ambiguities
- **Resolution Agent**: Generates, validates, and executes TaskDocument

**TaskDocument DSL** — declarative action specification:
- `$ref` paths use `state.` prefix (e.g., `state.actors.goblin_1.hp.current`)
- Step types: `select`, `check`, `damage`, `heal`, `resource`, `effect`, `state`
- No `formula` strings in check/damage steps — use structured `dice` + `bonus`
- Planner generates tasks; never executes them

## Key Entry Points

**Python API:**
```python
from augury import create_planner
planner = create_planner(state=state)
result = planner.invoke("Aldera用长剑攻击goblin_1")
```

**CLI eval:**
```bash
python src/eval/context_agent_eval.py --intent "Aldera用长剑攻击goblin_1"
```

**RAG hybrid search:**
```python
from augury.rag import build_default_retriever
retriever = build_default_retriever(config)
results = retriever.query("goblin ambush tactics")
```

## Conventions

- **Python 3.12**, `from __future__ import annotations` everywhere
- **Lowercase generics**: `dict[str, int]` not `Dict[str, int]`
- **Pydantic v2** for validation, **dataclasses with `@dataclass(slots=True)`** for data containers
- **Logging**: `loguru.logger` — no `logging` module
- **Testing**: `unittest` only, no pytest
- **Config**: TOML via `config/config.toml`, loaded through `augury.config`
- No linting/formatting tools configured (no ruff, black, mypy)

## Critical Anti-Patterns

| Anti-pattern | Correct |
|---|---|
| `state.` prefix in tool paths | Tool paths: bare (`actors.goblin_1.ac`); `$ref` only uses `state.` |
| `formula: "2d6+3"` in check/damage | Use structured `dice: "2d6"` + `bonus: 3` |
| Executing tasks inside planner | Planner generates; ResolutionAgent executes |
| `Dict[str]`, `List[int]` from typing | `dict[str]`, `list[int]` |
| `import logging; logging.info()` | `from loguru import logger; logger.info()` |

## Cross-References

- **Agent orchestration details**: `src/augury/agent/AGENTS.md`
- **TRPG rules engine**: `src/augury/engine/AGENTS.md`
- **OpenSpec workflow**: `openspec/AGENTS.md`
