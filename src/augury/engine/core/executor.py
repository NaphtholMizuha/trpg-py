from __future__ import annotations

from copy import deepcopy
from typing import Any

from augury.engine.combat.operations import (
    SUPPORTED_CHECK_TAGS,
    SUPPORTED_KINDS,
    SUPPORTED_TYPES,
    dispatch_step,
)
from augury.engine.core.dice import DiceRoller, RandomDiceRoller, parse_dice_spec
from augury.engine.core.models import (
    AppliedChange,
    ExecutionReport,
    OperationResult,
    StepReport,
    TaskDocument,
    TaskStep,
)
from augury.engine.core.refs import collect_refs, resolve_value
from augury.errors import DiceError, ExecutionError, ValidationError
from augury.store import read, write
from augury.store.compat import has_path


ALLOWED_FIELD_MAP_KEYS = {"id", "side", "alive", "tags", "position.x", "position.y"}
ValidationIssue = dict[str, str | None]


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
    issues: list[ValidationIssue] = []
    for index, raw_step in enumerate(document["steps"]):
        step_issues, validated_step = _validate_step_definition(
            raw_step=raw_step,
            index=index,
            seen_ids=seen_ids,
            prior_ids=prior_ids,
        )
        issues.extend(step_issues)
        if validated_step is None:
            continue
        step_id = validated_step.id
        seen_ids.add(step_id)
        prior_ids.add(step_id)
        steps.append(validated_step)

    if issues:
        raise _build_validation_error(issues)

    return TaskDocument(
        task_id=document["task_id"],
        version=int(document["version"]),
        policy=policy,
        context=context,
        steps=steps,
    )


def _validate_step_definition(
    *,
    raw_step: Any,
    index: int,
    seen_ids: set[str],
    prior_ids: set[str],
) -> tuple[list[ValidationIssue], TaskStep | None]:
    issues: list[ValidationIssue] = []
    step_path = f"steps.{index}"
    if not isinstance(raw_step, dict):
        issues.append(_issue(step_path, "Every step must be an object"))
        return issues, None

    missing_required = [required for required in ("id", "type", "kind", "args") if required not in raw_step]
    for required in missing_required:
        issues.append(_issue(f"{step_path}.{required}", f"Field required", code="missing"))
    if missing_required:
        return issues, None

    step_id = raw_step["id"]
    step_type = raw_step["type"]
    kind = raw_step["kind"]
    args = raw_step["args"]
    tags = raw_step.get("tags", [])
    when = raw_step.get("when")

    if not isinstance(step_id, str):
        issues.append(_issue(f"{step_path}.id", "Step id must be a string"))
    if isinstance(step_id, str) and step_id in seen_ids:
        issues.append(_issue(f"{step_path}.id", f"Duplicate step id {step_id!r}"))
    if not isinstance(step_type, str):
        issues.append(_issue(f"{step_path}.type", "Step type must be a string"))
    elif step_type not in SUPPORTED_TYPES:
        issues.append(_issue(f"{step_path}.type", f"Unsupported step type {step_type!r}"))
    if not isinstance(kind, str):
        issues.append(_issue(f"{step_path}.kind", "Step kind must be a string"))
    elif isinstance(step_type, str) and step_type in SUPPORTED_TYPES and kind not in SUPPORTED_KINDS[step_type]:
        issues.append(_issue(f"{step_path}.kind", f"Unsupported kind {kind!r} for type {step_type!r}"))
    if not isinstance(args, dict):
        issues.append(_issue(f"{step_path}.args", f"Step {step_id!r} args must be an object"))
    if tags and not isinstance(tags, list):
        issues.append(_issue(f"{step_path}.tags", f"Step {step_id!r} tags must be a list"))

    if issues:
        return issues, None

    assert isinstance(step_id, str)
    assert isinstance(step_type, str)
    assert isinstance(kind, str)
    assert isinstance(args, dict)
    assert isinstance(tags, list)

    _collect_validation_issue(issues, step_path, "args", lambda: _validate_refs(step_id, args, prior_ids))
    _collect_validation_issue(issues, step_path, "when", lambda: _validate_refs(step_id, when, prior_ids))
    _collect_validation_issue(
        issues,
        step_path,
        "",
        lambda: _validate_step_semantics(step_id, step_type, kind, args, tags),
    )

    if issues:
        return issues, None

    return issues, TaskStep(id=step_id, type=step_type, kind=kind, args=args, tags=list(tags), when=when)


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
    if step_type == "resource":
        if "path" not in args:
            raise ValidationError(f"Resource step {step_id!r} must define a path")
        _validate_direct_state_path(step_id, "path", args.get("path"))
    if step_type == "state":
        if "path" not in args:
            raise ValidationError(f"State step {step_id!r} must define a path")
        _validate_direct_state_path(step_id, "path", args.get("path"))


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
        if isinstance(value, str):
            _validate_direct_state_path(step_id, key, value)
            continue
        if isinstance(value, dict):
            continue
        raise ValidationError(f"Step {step_id!r} {key!r} must be a string or object mapping")


def _validate_dice_spec(step_id: str, field_name: str, spec: Any) -> None:
    if not isinstance(spec, str):
        raise ValidationError(f"Step {step_id!r} {field_name} must be a dice string")
    try:
        parse_dice_spec(spec)
    except DiceError as exc:
        raise ValidationError(f"Step {step_id!r} {field_name} has invalid dice spec {spec!r}") from exc


def _validate_direct_state_path(step_id: str, field_name: str, value: Any) -> None:
    if not isinstance(value, str):
        raise ValidationError(f"Step {step_id!r} {field_name!r} must be a string path")
    for prefix in ("state.", "context.", "result."):
        if value.startswith(prefix):
            raise ValidationError(
                f"Step {step_id!r} {field_name!r} must use a raw state path without the {prefix[:-1]!r} namespace prefix"
            )


def _collect_validation_issue(
    issues: list[ValidationIssue],
    step_path: str,
    default_suffix: str,
    validator: Any,
) -> None:
    try:
        validator()
    except ValidationError as exc:
        suffix, message, code = _extract_issue_details(exc, default_suffix=default_suffix)
        path = step_path if not suffix else f"{step_path}.{suffix}"
        issues.append(_issue(path, message, code=code))


def _extract_issue_details(exc: ValidationError, *, default_suffix: str) -> tuple[str, str, str]:
    if exc.issues:
        first_issue = exc.issues[0]
        raw_path = first_issue.get("path") or default_suffix
        message = first_issue.get("message") or str(exc)
        code = first_issue.get("code") or exc.__class__.__name__
        return str(raw_path), str(message), str(code)
    return default_suffix, str(exc), exc.__class__.__name__


def _issue(path: str, message: str, *, code: str | None = None) -> ValidationIssue:
    return {"path": path, "message": message, "code": code or "ValidationError"}


def _build_validation_error(issues: list[ValidationIssue]) -> ValidationError:
    summary = "; ".join(
        f"{issue['path']}: {issue['message']}" if issue["path"] else str(issue["message"])
        for issue in issues
    )
    return ValidationError(
        f"Task document validation failed with {len(issues)} issue(s): {summary}",
        issues=issues,
    )
