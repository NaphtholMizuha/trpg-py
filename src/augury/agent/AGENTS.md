# Agent Orchestration Layer

## Module Boundaries

- **runtime.py** — `PlannerAgent` entry, `AgentSkillRegistry`, skill loading/delegation wiring
- **subagents/context_agent.py** — intent analysis, entity resolution, ask-interrupt loop, evidence collection
- **subagents/resolution_agent.py** — `TaskDocument` generation, lint, execution
- **models.py** — `ContextBundle`, `ResolutionBundle`, `PlannerRequest`/`PlannerResult`, `AskRequest`/`AskResponse`
- **tools/** — `ask`, `execute`, `orchestration` (delegate/list_skills/load_skills), `search_stub`

## Agent Lifecycle

```
create_planner(state=state) → PlannerAgent.invoke(instruction)
  1. load_skills(["context_agent", "resolution_agent"])
  2. delegate → context_agent.run(payload)
  3. delegate → resolution_agent.run(payload)   # only if context_bundle.status != "blocked"
```

`PlannerDependencies` dataclass injects tools/subagents for testing. `AgentSkillRegistry` manages lazy-loaded skills with `register_agent` / `load_skills` / `delegate`.

## Ask-Interrupt Protocol

ContextAgent runs `_resolve_analysis_with_ask` — a loop that calls `_analyze_intent`, then checks three ambiguity points in order:

1. **actor_identification** — no entity matched the intent
2. **target_disambiguation** / **target_identification** — multiple or zero target matches
3. **area_point** — area spell missing origin coordinates

Each check invokes `ask_tool` with `resume_response` for re-entrancy. Responses populate `response_map` keyed by `question_id`. The loop rebuilds `overrides` from the map and re-analyzes until all gaps close or an interrupt propagates as `PendingInterrupt`.

On interrupt, `ContextBundle.status = "needs_human"` with `pending_interrupt` set. Caller resumes by passing `ask_responses` back through `PlannerRequest.ask_responses`.

## Tool Registry Surface

`augury.agent.tools` re-exports `augury.planner.tools` (grep, search, lint, read) plus agent-specific factories:

- `create_ask_tool(responder)` — triggers `AskInterrupt` when `responder` returns None
- `create_execute_tool(state_provider, roller)` — runs `TaskDocument` against state
- `create_delegate_tool(registry)` — routes `{target, payload}` to a loaded skill
- `create_list_skills_tool(registry)` / `create_load_skills_tool(registry)`

Factory pattern: every tool is a class (`AskTool`, `ExecuteTool`, etc.) with `invoke(input_dict)` returning a typed result.

## Critical Anti-Patterns

- **Don't pass raw instruction/state/context as ContextAgent payload** — use `build_context_agent_payload(request)` from runtime, which wraps intent into `goal` + `requests` (natural-language fact acquisition)
- **Requests must be natural language**, not field names (`caster_id` ❌, "识别执行者实体" ✅)
- **Never execute in the planner** — execution belongs exclusively in `ResolutionAgent`
- **Don't re-lint without new evidence** — lint runs once per resolution pass; looping on the same document is wasted work
- **Action types are fixed**: `weapon_attack`, `spell_attack`, `area_spell`, `heal_spell`, `record_state`, `custom` (via `_identify_action`)

## Key Files (Read Order)

1. `runtime.py` — `PlannerAgent.invoke` flow, `build_context_agent_payload`
2. `subagents/context_agent.py` — `_resolve_analysis_with_ask` loop, `_analyze_intent`, `_identify_action`
3. `subagents/resolution_agent.py` — `build_candidate_task_document`, per-action document builders
