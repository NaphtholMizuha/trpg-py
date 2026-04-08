# Engine Layer — Execution Runtime

Scope: `src/augury/engine/` only. Covers TaskDocument validation, step dispatch, state mutation, and dice resolution.

## Module Boundaries

**core/** — Platform primitives. Dice rolling, $ref resolution, data models, the executor loop. No game logic lives here.

**combat/** — Game-domain step handlers. Each supported step type/kind pair has a `run_*` function that produces `OperationResult` (outputs + changes + events).

## Execution Pipeline

1. **Validate** — `validate_task_document()` runs structural checks (required fields, types), then semantic checks (dice specs, path prefixes, type/kind compatibility). Blocks on first error batch.
2. **Dispatch** — `execute_task()` iterates steps sequentially. Evaluates `when` conditionals, resolves `$ref` in args, calls `dispatch_step()`.
3. **Mutate** — Each step returns `OperationResult`. Changes are committed to state via `write()`, recorded as `AppliedChange` with before/after values.
4. **Report** — `ExecutionReport` captures per-step status, outputs, changes, and halts on first failure.

## Step Type/Kind Constraints

| type     | kinds                  | required args                          |
|----------|------------------------|----------------------------------------|
| select   | target, area, filtered | target: source or target_id; area: shape + origin |
| check    | attack, save, ability, skill | dice (always); dc or dc_path (non-attack); target identity (attack) |
| damage   | apply                  | damage components (list or dict), targets |
| heal     | apply                  | healing components or amount, targets  |
| resource | consume                | path, cost                             |
| effect   | add, remove            | effect object (add) or effect_id (remove), targets |
| state    | set, adjust            | path, value (set) or delta (adjust)    |

check.attack supports exactly one target. check.save/ability/skill require dc or dc_path.

## $ref Resolution

Namespaces: `context`, `state`, `result`.

- `context.*` — Read-only scenario metadata.
- `state.*` — Current mutable state (actors, hp, positions).
- `result.<step_id>.*` — Prior step outputs only. Forward references are validation errors.

$ref syntax: `{"$ref": "result.step_1.target_id"}`. Resolved recursively through nested dicts/lists before step dispatch.

## Dice System

Spec format: `NdS` (e.g., `2d6`, `1d20`). No modifiers in the string — bonuses are separate fields.

- `DiceRoller` — Abstract base.
- `RandomDiceRoller(seed)` — Production randomness, optional seed.
- `FixedDiceRoller(values)` — Test-only. Pops values sequentially. Use for deterministic tests.

`parse_dice_spec()` validates format. Raises `DiceError` on malformed input.

## Critical Anti-Patterns

- **No `formula` strings** in check or damage steps. Use explicit `dice` + `bonus` components.
- **check.attack is single-target only**. Multi-target attacks must split into separate steps.
- **State paths in step args must NOT use `state.` prefix**. Write `actors.goblin_1.hp.current`, not `state.actors.goblin_1.hp.current`. The `state.` prefix is only valid inside `$ref`.
- **$ref can only reference prior steps**. `result.future_step` is a validation error.
- **area select requires both shape and origin**. Missing either is a validation error.
- **check.save/ability/skill must define dc or dc_path**. No implicit DC.
- **Never bypass validation**. `validate_task_document()` is the gatekeeper. All steps must pass before execution begins.

## Key Files — Read Order

1. `core/executor.py` (416 LOC) — Validation hierarchy, execution loop, ALLOWED_FIELD_MAP_KEYS.
2. `combat/operations.py` (47 LOC) — Step dispatch table, supported type/kind pairs.
3. `combat/check.py` (171 LOC) — Attack rolls, saves, ability/skill checks, SUPPORTED_CHECK_TAGS = {nat, adv, disadv}.
4. `combat/select.py` (245 LOC) — Target selection, area templates (sphere, cube, line, cone), origin resolution.
5. `combat/resolution.py` (254 LOC) — Damage application, healing, saving throw resolution, critical hit mapping.
6. `core/dice.py` (58 LOC) — DiceSpec, rollers, spec parsing.
7. `core/refs.py` (56 LOC) — $ref collection and resolution.
8. `core/models.py` (71 LOC) — TaskStep, TaskDocument, OperationResult, ExecutionReport, AppliedChange.
