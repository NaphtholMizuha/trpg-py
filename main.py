from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from trpg_py import FixedDiceRoller, execute_task


ROOT = Path(__file__).parent


@dataclass(frozen=True)
class DemoDefinition:
    task_file: str
    state_builder: Callable[[], dict[str, Any]]
    roller_builder: Callable[[], FixedDiceRoller]


def _fixed_roller(values: list[int]) -> Callable[[], FixedDiceRoller]:
    return lambda: FixedDiceRoller(values)


def _build_goblin_attack_state() -> dict[str, Any]:
    return {
        "actors": {
            "goblin_1": {
                "id": "goblin_1",
                "side": "enemy",
                "alive": True,
                "position": {"x": 1, "y": 1},
                "hp": {"current": 7},
                "attacks": {"scimitar": {"to_hit": 4}},
            },
            "hero_1": {
                "id": "hero_1",
                "side": "player",
                "alive": True,
                "position": {"x": 1, "y": 2},
                "ac": 16,
                "hp": {"current": 20},
                "effects": [],
                "saves": {"dex": 2},
            },
        }
    }


def _build_healing_word_cap_state() -> dict[str, Any]:
    return {
        "actors": {
            "cleric_1": {
                "id": "cleric_1",
                "side": "player",
                "alive": True,
                "position": {"x": 2, "y": 2},
                "hp": {"current": 12, "max": 12},
                "effects": [],
                "resources": {"spell_slots": {"1": 1}},
            },
            "patient_1": {
                "id": "patient_1",
                "side": "player",
                "alive": True,
                "position": {"x": 2, "y": 3},
                "hp": {"current": 7, "max": 10},
                "effects": [],
            },
        }
    }


def _build_insufficient_spell_slot_state() -> dict[str, Any]:
    return {
        "actors": {
            "wizard_1": {
                "id": "wizard_1",
                "side": "player",
                "alive": True,
                "position": {"x": 5, "y": 5},
                "hp": {"current": 9, "max": 9},
                "resources": {"spell_slots": {"1": 0}},
            }
        }
    }


def _build_fireball_state() -> dict[str, Any]:
    return {
        "actors": {
            "wizard_1": {
                "id": "wizard_1",
                "side": "player",
                "alive": True,
                "position": {"x": 10, "y": 12},
                "spell_dc": 15,
                "hp": {"current": 22},
                "effects": [],
                "resources": {"spell_slots": {"3": 1}},
            },
            "goblin_1": {
                "id": "goblin_1",
                "side": "enemy",
                "alive": True,
                "position": {"x": 12, "y": 12},
                "hp": {"current": 18},
                "saves": {"dex": 2},
                "effects": [],
            },
            "goblin_2": {
                "id": "goblin_2",
                "side": "enemy",
                "alive": True,
                "position": {"x": 16, "y": 12},
                "hp": {"current": 18},
                "saves": {"dex": 0},
                "effects": [],
            },
            "ally_1": {
                "id": "ally_1",
                "side": "player",
                "alive": True,
                "position": {"x": 11, "y": 10},
                "hp": {"current": 11},
                "saves": {"dex": 1},
                "effects": [],
            },
        }
    }


def _build_far_goblin_attack_state() -> dict[str, Any]:
    state = _build_goblin_attack_state()
    state["actors"]["hero_1"]["position"] = {"x": 1, "y": 8}
    return state


def _build_fireball_empty_state() -> dict[str, Any]:
    state = _build_fireball_state()
    state["actors"]["goblin_1"]["position"] = {"x": 40, "y": 40}
    state["actors"]["goblin_2"]["position"] = {"x": 45, "y": 42}
    state["actors"]["ally_1"]["position"] = {"x": 42, "y": 41}
    return state


def _build_fireball_out_of_range_state() -> dict[str, Any]:
    return _build_fireball_state()


def _build_custom_layout_state() -> dict[str, Any]:
    return {
        "combatants": {
            "wizard_custom": {
                "meta": {"id": "wizard_custom"},
                "team": {"side": "player"},
                "status": {"alive": True},
                "traits": {"tags": ["caster", "humanoid"]},
                "space": {"grid": {"col": 10, "row": 12}},
                "numbers": {"magic": {"dc": 15}},
                "tracks": {"health": {"value": 22}},
                "status_lists": {"active_effects": []},
                "resources": {"spell_slots": {"3": 1}},
            },
            "goblin_custom_1": {
                "meta": {"id": "goblin_custom_1"},
                "team": {"side": "enemy"},
                "status": {"alive": True},
                "traits": {"tags": ["goblin"]},
                "space": {"grid": {"col": 12, "row": 12}},
                "numbers": {"saves": {"dexterity": 2}},
                "tracks": {"health": {"value": 18}},
                "status_lists": {"active_effects": []},
            },
            "goblin_custom_2": {
                "meta": {"id": "goblin_custom_2"},
                "team": {"side": "enemy"},
                "status": {"alive": True},
                "traits": {"tags": ["goblin"]},
                "space": {"grid": {"col": 16, "row": 12}},
                "numbers": {"saves": {"dexterity": 0}},
                "tracks": {"health": {"value": 18}},
                "status_lists": {"active_effects": []},
            },
            "ally_custom_1": {
                "meta": {"id": "ally_custom_1"},
                "team": {"side": "player"},
                "status": {"alive": True},
                "traits": {"tags": ["ally"]},
                "space": {"grid": {"col": 11, "row": 10}},
                "numbers": {"saves": {"dexterity": 1}},
                "tracks": {"health": {"value": 11}},
                "status_lists": {"active_effects": []},
            },
        }
    }


def _build_lightning_bolt_state() -> dict[str, Any]:
    return {
        "actors": {
            "wizard_line": {
                "id": "wizard_line",
                "side": "player",
                "alive": True,
                "position": {"x": 0, "y": 0},
                "spell_dc": 15,
                "hp": {"current": 22},
                "effects": [],
                "resources": {"spell_slots": {"3": 1}},
            },
            "goblin_line_1": {
                "id": "goblin_line_1",
                "side": "enemy",
                "alive": True,
                "position": {"x": 5, "y": 0},
                "hp": {"current": 18},
                "saves": {"dex": 2},
                "effects": [],
            },
            "goblin_line_2": {
                "id": "goblin_line_2",
                "side": "enemy",
                "alive": True,
                "position": {"x": 8, "y": 2},
                "hp": {"current": 18},
                "saves": {"dex": 0},
                "effects": [],
            },
            "goblin_line_3": {
                "id": "goblin_line_3",
                "side": "enemy",
                "alive": True,
                "position": {"x": 3, "y": 4},
                "hp": {"current": 18},
                "saves": {"dex": 1},
                "effects": [],
            },
            "ally_line_1": {
                "id": "ally_line_1",
                "side": "player",
                "alive": True,
                "position": {"x": 6, "y": 0},
                "hp": {"current": 14},
                "saves": {"dex": 1},
                "effects": [],
            },
        }
    }


def _build_burning_hands_state() -> dict[str, Any]:
    return {
        "actors": {
            "wizard_cone": {
                "id": "wizard_cone",
                "side": "player",
                "alive": True,
                "position": {"x": 0, "y": 0},
                "spell_dc": 15,
                "hp": {"current": 18},
                "effects": [],
                "resources": {"spell_slots": {"1": 1}},
            },
            "goblin_cone_1": {
                "id": "goblin_cone_1",
                "side": "enemy",
                "alive": True,
                "position": {"x": 6, "y": 0},
                "hp": {"current": 14},
                "saves": {"dex": 1},
                "effects": [],
            },
            "goblin_cone_2": {
                "id": "goblin_cone_2",
                "side": "enemy",
                "alive": True,
                "position": {"x": 6, "y": 3},
                "hp": {"current": 14},
                "saves": {"dex": 4},
                "effects": [],
            },
            "goblin_cone_3": {
                "id": "goblin_cone_3",
                "side": "enemy",
                "alive": True,
                "position": {"x": 6, "y": 5},
                "hp": {"current": 14},
                "saves": {"dex": 2},
                "effects": [],
            },
        }
    }


DEMO_REGISTRY: dict[str, DemoDefinition] = {
    "goblin_scimitar_attack": DemoDefinition(
        task_file="goblin_scimitar_attack",
        state_builder=_build_goblin_attack_state,
        roller_builder=_fixed_roller([15, 4]),
    ),
    "goblin_scimitar_attack_out_of_range": DemoDefinition(
        task_file="goblin_scimitar_attack",
        state_builder=_build_far_goblin_attack_state,
        roller_builder=_fixed_roller([15, 4]),
    ),
    "goblin_scimitar_attack_crit": DemoDefinition(
        task_file="goblin_scimitar_attack",
        state_builder=_build_goblin_attack_state,
        roller_builder=_fixed_roller([20, 6, 4]),
    ),
    "goblin_scimitar_attack_miss": DemoDefinition(
        task_file="goblin_scimitar_attack",
        state_builder=_build_goblin_attack_state,
        roller_builder=_fixed_roller([2]),
    ),
    "healing_word_cap": DemoDefinition(
        task_file="healing_word_cap",
        state_builder=_build_healing_word_cap_state,
        roller_builder=_fixed_roller([]),
    ),
    "insufficient_spell_slot": DemoDefinition(
        task_file="insufficient_spell_slot",
        state_builder=_build_insufficient_spell_slot_state,
        roller_builder=_fixed_roller([]),
    ),
    "fireball": DemoDefinition(
        task_file="fireball",
        state_builder=_build_fireball_state,
        roller_builder=_fixed_roller([12, 18, 3, 3, 3, 3, 2, 2, 1, 1]),
    ),
    "fireball_empty": DemoDefinition(
        task_file="fireball_empty",
        state_builder=_build_fireball_empty_state,
        roller_builder=_fixed_roller([]),
    ),
    "fireball_out_of_range": DemoDefinition(
        task_file="fireball_out_of_range",
        state_builder=_build_fireball_out_of_range_state,
        roller_builder=_fixed_roller([]),
    ),
    "lightning_bolt_line": DemoDefinition(
        task_file="lightning_bolt_line",
        state_builder=_build_lightning_bolt_state,
        roller_builder=_fixed_roller([12, 18, 3, 3, 3, 3, 2, 2, 1, 1]),
    ),
    "burning_hands_cone": DemoDefinition(
        task_file="burning_hands_cone",
        state_builder=_build_burning_hands_state,
        roller_builder=_fixed_roller([12, 18, 4, 3, 2]),
    ),
    "custom_layout_fireburst": DemoDefinition(
        task_file="custom_layout_fireburst",
        state_builder=_build_custom_layout_state,
        roller_builder=_fixed_roller([12, 18, 3, 3, 3, 3, 2, 2, 1, 1]),
    ),
}


def get_demo_definition(example_name: str) -> DemoDefinition:
    if example_name not in DEMO_REGISTRY:
        raise SystemExit(f"Unknown demo example: {example_name}")
    return DEMO_REGISTRY[example_name]


def load_demo_task(task_file: str) -> dict[str, Any]:
    return json.loads((ROOT / "examples" / f"{task_file}.json").read_text())


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TRPG resolution demo examples")
    parser.add_argument(
        "example",
        nargs="?",
        default="goblin_scimitar_attack",
        help="Example name to run, or 'all' to run every registered demo",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print the raw JSON payload instead of the human-readable summary",
    )
    return parser.parse_args(argv)


def format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def format_roll_list(values: list[Any]) -> str:
    return "[" + ", ".join(format_value(value) for value in values) + "]"


def format_signed(value: Any) -> str:
    number = float(value)
    if number.is_integer():
        integer = int(number)
        return f"+{integer}" if integer >= 0 else str(integer)
    return f"+{format_value(number)}" if number >= 0 else format_value(number)


def summarize_step(step_report: dict[str, Any]) -> list[str]:
    outputs = step_report.get("outputs", {})
    step_type = step_report["type"]
    kind = step_report["kind"]
    status = step_report["status"]
    lines = [f"- {step_report['id']} [{step_type}.{kind}] -> {status}"]
    if status != "success":
        if step_report.get("error_code"):
            lines.append(f"  reason: {step_report['error_code']}")
        if step_report.get("error"):
            lines.append(f"  error: {step_report['error']}")
        return lines

    if step_type == "select":
        target_ids = outputs.get("target_ids", [])
        lines.append(f"  targets: {', '.join(target_ids) if target_ids else '(none)'}")
    elif step_type == "check":
        target_results = outputs.get("target_results")
        target_ids = outputs.get("target_ids", [])
        if target_results:
            for target_id, result in target_results.items():
                lines.append(
                    "  "
                    + f"{target_id}: outcome={result.get('outcome')} total={result.get('total')}"
                    + f" natural={result.get('natural')} mode={result.get('roll_mode')}"
                )
                rolls = result.get("rolls", [])
                if rolls:
                    lines.append(f"    rolls: {format_roll_list(rolls)}")
                lines.append(
                    "    "
                    + f"calc: {result.get('chosen')} {format_signed(result.get('modifier', 0))}"
                    + f" = {result.get('total')}"
                    + f" vs {result.get('threshold')}"
                )
        elif not target_ids:
            lines.append("  no targets")
        else:
            lines.append(
                "  "
                + f"outcome={outputs.get('outcome')} total={outputs.get('total')}"
                + f" natural={outputs.get('natural')} mode={outputs.get('roll_mode')}"
            )
            rolls = outputs.get("rolls", [])
            if rolls:
                lines.append(f"    rolls: {format_roll_list(rolls)}")
            lines.append(
                "    "
                + f"calc: {outputs.get('chosen')} {format_signed(outputs.get('modifier', 0))}"
                + f" = {outputs.get('total')}"
                + f" vs {outputs.get('threshold')}"
            )
    elif step_type == "damage":
        per_target = outputs.get("per_target", {})
        if per_target:
            for target_id, result in per_target.items():
                lines.append(
                    "  "
                    + f"{target_id}: amount={result.get('final_total')} multiplier={format_value(result.get('multiplier', 1))}"
                )
                components = result.get("components", [])
                for component in components:
                    rolls = component.get("rolls", [])
                    dice = component.get("dice")
                    bonus = component.get("bonus", 0)
                    component_total = component.get("total")
                    calc = f"{format_roll_list(rolls)}"
                    if bonus:
                        calc += f" {format_signed(bonus)}"
                    calc += f" = {component_total}"
                    label = dice or "flat"
                    damage_type = component.get("damage_type")
                    if damage_type:
                        label += f" {damage_type}"
                    lines.append(f"    {label}: {calc}")
                lines.append(
                    "    "
                    + f"final: floor({result.get('base_total')} * {format_value(result.get('multiplier', 1))})"
                    + f" = {result.get('final_total')}"
                )
        else:
            lines.append("  no targets")
    elif step_type == "heal":
        per_target = outputs.get("per_target", {})
        if per_target:
            for target_id, result in per_target.items():
                summary = f"{target_id}: healed={result.get('final_total')}"
                requested_total = result.get("requested_total")
                if requested_total is not None and requested_total != result.get("final_total"):
                    summary += f" requested={requested_total}"
                if result.get("max_hp") is not None:
                    summary += f" max_hp={result.get('max_hp')}"
                if result.get("capped"):
                    summary += " capped=yes"
                lines.append("  " + summary)
        else:
            lines.append("  no targets")
    elif step_type == "resource":
        lines.append(
            "  "
            + f"path={outputs.get('path')} cost={outputs.get('cost')} remaining={outputs.get('remaining')}"
        )
    elif step_type == "effect":
        lines.append(f"  targets: {', '.join(outputs.get('target_ids', []))}")
        if "effect" in outputs:
            lines.append(f"  effect: {format_value(outputs['effect'])}")
        if "removed_counts" in outputs:
            lines.append(f"  removed: {format_value(outputs['removed_counts'])}")
    elif step_type == "state":
        if "value" in outputs:
            lines.append(f"  set {outputs.get('path')} = {format_value(outputs.get('value'))}")
        if "delta" in outputs:
            lines.append(f"  adjust {outputs.get('path')} by {format_value(outputs.get('delta'))}")

    return lines


def render_summary(example_name: str, report_payload: dict[str, Any]) -> str:
    report = report_payload["report"]
    lines = [
        f"Task: {example_name}",
        f"Status: {report['status']}",
    ]
    if report.get("error"):
        lines.append(f"Error: {report['error']}")

    lines.append("")
    lines.append("Steps:")
    for step_report in report["step_reports"]:
        lines.extend(summarize_step(step_report))

    lines.append("")
    lines.append("Applied Changes:")
    changes = report.get("applied_changes", [])
    if not changes:
        lines.append("- (none)")
    else:
        for change in changes:
            lines.append(
                "- "
                + f"{change['path']}: {format_value(change['old_value'])} -> {format_value(change['new_value'])}"
            )

    return "\n".join(lines)


def run_demo(example_name: str) -> dict[str, Any]:
    definition = get_demo_definition(example_name)
    task = load_demo_task(definition.task_file)
    state = definition.state_builder()
    initial_state = deepcopy(state)
    report = execute_task(task, state, roller=definition.roller_builder())
    return {
        "demo": example_name,
        "task": task["task_id"],
        "initial_state": initial_state,
        "final_state": state,
        "report": report.to_dict(),
    }


def run_all_demos() -> dict[str, Any]:
    runs = [run_demo(name) for name in DEMO_REGISTRY]
    success_count = sum(1 for run in runs if run["report"]["status"] == "success")
    failed_count = sum(1 for run in runs if run["report"]["status"] != "success")
    return {
        "runs": runs,
        "summary": {
            "total": len(runs),
            "success": success_count,
            "failed": failed_count,
            "status": "success" if failed_count == 0 else "failed",
        },
    }


def render_all_summaries(batch_payload: dict[str, Any]) -> str:
    lines: list[str] = []
    for index, run in enumerate(batch_payload["runs"]):
        if index:
            lines.append("")
        lines.append(f"=== Demo: {run['demo']} ===")
        lines.extend(render_summary(run["demo"], run).splitlines())
    summary = batch_payload["summary"]
    lines.append("")
    lines.append("Overall Summary:")
    lines.append(f"- total demos: {summary['total']}")
    lines.append(f"- success: {summary['success']}")
    lines.append(f"- failed: {summary['failed']}")
    lines.append(f"- overall status: {summary['status']}")
    return "\n".join(lines)


def main() -> None:
    args = parse_args(sys.argv[1:])
    example_name = args.example
    if example_name == "all":
        payload = run_all_demos()
        if args.as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return
        print(render_all_summaries(payload))
        return

    payload = run_demo(example_name)
    if args.as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    print(render_summary(example_name, payload))


if __name__ == "__main__":
    main()
