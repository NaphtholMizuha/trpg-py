# Agent Orchestration Layer

## Module Boundaries

- **__init__.py** — stable public facade for planner APIs and selected eval helpers
- **orchestrate.py** — `PlannerAgent` entry, `AgentSkillRegistry`, skill loading and delegation wiring
- **models.py** — shared structured contracts such as `PlannerRequest`, `PlannerResult`, `ContextBundle`, `AskRequest`
- **subagents/** — `context_agent` / `resolution_agent` execution logic
- **tools/** — agent-facing tool implementations such as `ask`, `execute`, `grep`, `search`, `lint`
- **utils/** — helper implementations for CLI ask, focused evals, state loading, and runtime guard stubs

## Package Layout Rules

- Keep long-term orchestration truth in `orchestrate.py`.
- Keep shared data contracts in `models.py`.
- Expose stable public APIs from `augury.agent.__init__`, not via extra root shim modules.
- Put support helpers in `utils/`; do not reintroduce root-level forwarding files for them.

## Agent Lifecycle

```
create_planner(state=state) -> PlannerAgent.invoke(instruction)
  1. load_skills(["context_agent", "resolution_agent"])
  2. delegate -> context_agent.run(payload)
  3. delegate -> resolution_agent.run(payload)   # only if context_bundle.status != "blocked"
```

`PlannerDependencies` injects tools and subagents for testing. `AgentSkillRegistry` manages lazy-loaded skills with `register_agent`, `load_skills`, and `delegate`.

## Tool Registry Surface

- `create_ask_tool(responder)` — triggers `AskInterrupt` when `responder` returns `None`
- `create_execute_tool(state_provider, roller)` — executes a `TaskDocument` against state
- `create_delegate_tool(registry)` — routes `{target, payload}` to a loaded skill
- `create_list_skills_tool(registry)` / `create_load_skills_tool(registry)` — skill discovery and loading
- `create_grep_tool(...)` / `create_search_tool(...)` / `create_lint_tool(...)` — evidence and validation tools used by subagents

## Key Files

1. `orchestrate.py` — planner orchestration flow and context payload construction
2. `subagents/context_agent.py` — evidence gathering, ask loop, context bundle assembly
3. `subagents/resolution_agent.py` — task-document creation, lint, execute
4. `utils/context_eval.py` and `utils/evals.py` — focused eval and regression helpers
