from __future__ import annotations

from typing import Any

from augury.engine.combat.check import SUPPORTED_CHECK_TAGS, run_check
from augury.engine.combat.resolution import run_damage, run_effect, run_heal, run_resource, run_state
from augury.engine.combat.select import DEFAULT_SELECT_FIELD_MAP, run_select
from augury.engine.core.dice import DiceRoller
from augury.engine.core.models import OperationResult, TaskDocument, TaskStep
from augury.errors import ValidationError


SUPPORTED_TYPES = {"select", "check", "damage", "heal", "resource", "effect", "state"}
SUPPORTED_KINDS = {
    "select": {"target", "area", "filtered"},
    "check": {"attack", "save", "ability", "skill"},
    "damage": {"apply"},
    "heal": {"apply"},
    "resource": {"consume"},
    "effect": {"add", "remove"},
    "state": {"set", "adjust"},
}


def dispatch_step(
    step: TaskStep,
    resolved_args: dict[str, Any],
    state: dict[str, Any],
    task: TaskDocument,
    results: dict[str, Any],
    roller: DiceRoller,
) -> OperationResult:
    if step.type == "select":
        return run_select(step, resolved_args, state)
    if step.type == "check":
        return run_check(step, resolved_args, state, results, roller)
    if step.type == "damage":
        return run_damage(step, resolved_args, state, results, roller)
    if step.type == "heal":
        return run_heal(resolved_args, state, roller)
    if step.type == "resource":
        return run_resource(resolved_args, state)
    if step.type == "effect":
        return run_effect(step, resolved_args, state)
    if step.type == "state":
        return run_state(resolved_args, state, step.kind)
    raise ValidationError(f"Unsupported step type: {step.type}")
