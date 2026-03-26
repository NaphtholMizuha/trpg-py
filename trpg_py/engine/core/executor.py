from __future__ import annotations

from copy import deepcopy
from typing import Any

from trpg_py.engine.combat.operations import (
    SUPPORTED_CHECK_TAGS,
    SUPPORTED_KINDS,
    SUPPORTED_TYPES,
    dispatch_step,
)
from trpg_py.engine.core.dice import DiceRoller, RandomDiceRoller, parse_dice_spec
from trpg_py.engine.core.models import (
    AppliedChange,
    ExecutionReport,
    OperationResult,
    StepReport,
    TaskDocument,
    TaskStep,
)
from trpg_py.engine.core.refs import collect_refs, resolve_value
from trpg_py.errors import DiceError, ExecutionError, ValidationError
from trpg_py.store import read, write
from trpg_py.store.compat import has_path


ALLOWED_FIELD_MAP_KEYS = {"id", "side", "alive", "tags", "position.x", "position.y"}


def validate_task_document(document: dict[str, Any]) -> TaskDocument:
    if not isinstance(document, dict):
        raise ValidationError("Task document must be a dictionary")
    for required in ("task_id", "version", "steps"):
        if required not in document:
            raise ValidationError(f"Task document is missing required field {required!r}")
    if not isinstance(document["steps"], list):
        raise ValidationError("Task document field 'steps' must be a list")

    context = document.get("context", {})
    policy = document.get("policy", {})
    if not isinstance(context, dict) or not isinstance(policy, dict):
        raise ValidationError("Task document 'context' and 'policy' must be objects")

    steps: list[TaskStep] = []
    seen_ids: set[str] = set()
    prior_ids: set[str] = set()
    for raw_step in document["steps"]:
        if not isinstance(raw_step, dict):
            raise ValidationError("Every step must be an object")
        for required in ("id", "type", "kind", "args"):
            if required not in raw_step:
                raise ValidationError(f"Step is missing required field {required!r}")
        step_id = raw_step["id"]
        step_type = raw_step["type"]
        kind = raw_step["kind"]
        args = raw_step["args"]
        tags = raw_step.get("tags", [])
        when = raw_step.get("when")
        if not isinstance(step_id, str):
            raise ValidationError("Step id must be a string")
        if step_id in seen_ids:
            raise ValidationError(f"Duplicate step id {step_id!r}")
        if step_type not in SUPPORTED_TYPES:
            raise ValidationError(f"Unsupported step type {step_type!r}")
        if kind not in SUPPORTED_KINDS[step_type]:
            raise ValidationError(f"Unsupported kind {kind!r} for type {step_type!r}")
        if not isinstance(args, dict):
            raise ValidationError(f"Step {step_id!r} args must be an object")
        if tags and not isinstance(tags, list):
            raise ValidationError(f"Step {step_id!r} tags must be a list")
        _validate_refs(step_id, args, prior_ids)
        _validate_refs(step_id, when, prior_ids)
        _validate_step_semantics(step_id, step_type, kind, args, tags)
        seen_ids.add(step_id)
        prior_ids.add(step_id)
        steps.append(TaskStep(id=step_id, type=step_type, kind=kind, args=args, tags=list(tags), when=when))

    return TaskDocument(
        task_id=document["task_id"],
        version=int(document["version"]),
        policy=policy,
        context=context,
        steps=steps,
    )


def execute_task(
    document: dict[str, Any],
    state: dict[str, Any],
    roller: DiceRoller | None = None,
) -> ExecutionReport:
    try:
        task = validate_task_document(document)
    except ValidationError as exc:
        return ExecutionReport(
            task_id=document.get("task_id", "<invalid>"),
            status="validation_failed",
            error=str(exc),
        )

    roller = roller or RandomDiceRoller()
    results: dict[str, Any] = {}
    step_reports: list[StepReport] = []
    applied_changes: list[AppliedChange] = []

    for step in task.steps:
        try:
            if step.when is not None:
                should_run = resolve_value(step.when, state, task.context, results)
                if not bool(should_run):
                    step_reports.append(
                        StepReport(id=step.id, type=step.type, kind=step.kind, status="skipped")
                    )
                    continue

            resolved_args = resolve_value(step.args, state, task.context, results)
            if isinstance(resolved_args, dict) and step.type == "check":
                resolved_args.setdefault("tags", step.tags)
            op_result = dispatch_step(step, resolved_args, state, task, results, roller)
            step_changes = _commit_changes(state, op_result)
            results[step.id] = deepcopy(op_result.outputs)
            applied_changes.extend(step_changes)
            step_reports.append(
                StepReport(
                    id=step.id,
                    type=step.type,
                    kind=step.kind,
                    status="success",
                    outputs=deepcopy(op_result.outputs),
                    changes=step_changes,
                    events=deepcopy(op_result.events),
                )
            )
        except (ValidationError, ExecutionError, ValueError) as exc:
            step_reports.append(
                StepReport(
                    id=step.id,
                    type=step.type,
                    kind=step.kind,
                    status="failed",
                    error=str(exc),
                    error_code=getattr(exc, "error_code", None),
                )
            )
            return ExecutionReport(
                task_id=task.task_id,
                status="failed",
                step_reports=step_reports,
                results=results,
                applied_changes=applied_changes,
                error=str(exc),
            )

    return ExecutionReport(
        task_id=task.task_id,
        status="success",
        step_reports=step_reports,
        results=results,
        applied_changes=applied_changes,
    )


def _commit_changes(state: dict[str, Any], op_result: OperationResult) -> list[AppliedChange]:
    applied: list[AppliedChange] = []
    for change in op_result.changes:
        old_value = deepcopy(read(state, change.path)) if has_path(state, change.path) else None
        write(state, change.path, change.value)
        applied.append(
            AppliedChange(
                path=change.path,
                old_value=old_value,
                new_value=deepcopy(change.value),
                mode=change.mode,
            )
        )
    return applied


def _validate_refs(step_id: str, value: Any, prior_ids: set[str]) -> None:
    if value is None:
        return
    for ref in collect_refs(value):
        namespace, _, remainder = ref.partition(".")
        if namespace not in {"context", "state", "result"}:
            raise ValidationError(f"Step {step_id!r} uses unsupported ref namespace in {ref!r}")
        if namespace == "result":
            result_step, _, _ = remainder.partition(".")
            if result_step not in prior_ids:
                raise ValidationError(
                    f"Step {step_id!r} references result of unknown or future step {result_step!r}"
                )


def _validate_step_semantics(
    step_id: str,
    step_type: str,
    kind: str,
    args: dict[str, Any],
    tags: list[Any],
) -> None:
    if step_type == "check":
        _validate_path_like_args(step_id, args, ("target_ac_path", "target_ac_path_template", "modifier_path", "modifier_path_template", "dc_path"))
        if not isinstance(tags, list):
            raise ValidationError(f"Step {step_id!r} tags must be a list")
        unsupported = {str(tag) for tag in tags if str(tag) not in SUPPORTED_CHECK_TAGS}
        if unsupported:
            raise ValidationError(f"Step {step_id!r} uses unsupported check tags: {sorted(unsupported)!r}")
        if "dice" not in args:
            raise ValidationError(f"Check step {step_id!r} must define a dice string")
        _validate_dice_spec(step_id, "dice", args["dice"])
        if "formula" in args:
            raise ValidationError(f"Check step {step_id!r} cannot use a formula string")
        if kind == "attack":
            if (
                "target_ac" not in args
                and "target_ac_path" not in args
                and "target_ac_path_template" not in args
                and "target_id" not in args
                and "targets" not in args
            ):
                raise ValidationError(f"Attack step {step_id!r} must define target_ac or target identity")
        if kind in {"save", "ability", "skill"} and "dc" not in args and "dc_path" not in args:
            raise ValidationError(f"Check step {step_id!r} kind {kind!r} must define dc")

    if step_type in {"damage", "heal"}:
        _validate_path_like_args(step_id, args, ("target_hp_path", "target_hp_path_template"))
        if "formula" in args:
            raise ValidationError(f"Step {step_id!r} cannot hide dice semantics in formula")
        key = "damage" if step_type == "damage" else "healing"
        if key in args:
            components = args[key]
            if isinstance(components, dict):
                components = [components]
            if not isinstance(components, list):
                raise ValidationError(f"Step {step_id!r} {key!r} must be a list or object")
            for component in components:
                if not isinstance(component, dict):
                    raise ValidationError(f"Step {step_id!r} {key!r} component must be an object")
                if "dice" in component and component["dice"] is not None:
                    _validate_dice_spec(step_id, f"{key} component dice", component["dice"])

    if step_type == "select":
        _validate_field_map(step_id, args)
        _validate_targeting(step_id, kind, args)
        if kind == "area" and ("shape" not in args or "origin" not in args):
            raise ValidationError(f"Area select step {step_id!r} must define shape and origin")
    if step_type == "effect":
        _validate_path_like_args(step_id, args, ("effects_path", "effects_path_template"))
    if step_type == "resource" and "path" not in args:
        raise ValidationError(f"Resource step {step_id!r} must define a path")
    if step_type == "state" and "path" not in args:
        raise ValidationError(f"State step {step_id!r} must define a path")


def _validate_field_map(step_id: str, args: dict[str, Any]) -> None:
    field_map = args.get("field_map")
    if field_map is None:
        return
    if not isinstance(field_map, dict):
        raise ValidationError(f"Step {step_id!r} field_map must be an object")
    invalid_keys = sorted(set(field_map) - ALLOWED_FIELD_MAP_KEYS)
    if invalid_keys:
        raise ValidationError(f"Step {step_id!r} field_map uses unsupported keys: {invalid_keys!r}")


def _validate_targeting(step_id: str, kind: str, args: dict[str, Any]) -> None:
    targeting = args.get("targeting")
    if targeting is None:
        return
    if kind not in {"target", "area"}:
        raise ValidationError(f"Step {step_id!r} targeting is only supported for select.target/select.area")
    if not isinstance(targeting, dict):
        raise ValidationError(f"Step {step_id!r} targeting must be an object")
    required_keys = {"source_position", "max_range", "range_metric"}
    missing_keys = [key for key in required_keys if key not in targeting]
    if missing_keys:
        raise ValidationError(f"Step {step_id!r} targeting is missing keys: {missing_keys!r}")
    if not isinstance(targeting["max_range"], (int, float)):
        raise ValidationError(f"Step {step_id!r} targeting.max_range must be numeric")
    if not isinstance(targeting["range_metric"], str):
        raise ValidationError(f"Step {step_id!r} targeting.range_metric must be a string")


def _validate_path_like_args(step_id: str, args: dict[str, Any], keys: tuple[str, ...]) -> None:
    for key in keys:
        if key not in args:
            continue
        value = args[key]
        if key.endswith("_template"):
            if not isinstance(value, str):
                raise ValidationError(f"Step {step_id!r} {key!r} must be a string template")
            continue
        if isinstance(value, (str, dict)):
            continue
        raise ValidationError(f"Step {step_id!r} {key!r} must be a string or object mapping")


def _validate_dice_spec(step_id: str, field_name: str, spec: Any) -> None:
    if not isinstance(spec, str):
        raise ValidationError(f"Step {step_id!r} {field_name} must be a dice string")
    try:
        parse_dice_spec(spec)
    except DiceError as exc:
        raise ValidationError(f"Step {step_id!r} {field_name} has invalid dice spec {spec!r}") from exc
