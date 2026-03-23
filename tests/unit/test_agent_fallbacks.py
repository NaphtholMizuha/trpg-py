from src.agents.base import _extract_json_payload
from src.agents.deep_planner import DeepPlannerAgent
from src.agents.executor import ExecutorAgent
from src.agents.resolver import ResolverAgent
from src.types import (
    DiscardedStateChange,
    ExecutionResult,
    Operation,
    ResolutionResult,
    ResolutionWindow,
    ResolutionWindowRun,
    TaskExecution,
)


def test_extract_json_payload_from_fenced_block():
    content = """```json
{
  "task_id": "task_123",
  "description": "马利克对艾尔德拉施放魔法飞弹",
  "context": "some context",
  "actor": "Malik",
  "target": "Aldera",
  "source": "dm",
  "task_category": "normal"
}
```"""

    payload = _extract_json_payload(content)

    assert payload is not None
    assert '"task_id": "task_123"' in payload
    assert payload.startswith("{")
    assert payload.endswith("}")


def test_executor_accepts_narration_only_result():
    agent = object.__new__(ExecutorAgent)
    result = ExecutionResult(
        task_id="task_123",
        success=True,
        field_changes=[],
        narration="艾尔德拉宣告护盾术，当前仅确认反应窗口已出现。",
        triggered_chains=[],
    )

    assert agent._is_actionable_result(result) is True


def test_planner_fills_missing_task_id():
    agent = object.__new__(DeepPlannerAgent)
    task = TaskExecution(
        description="马利克对艾尔德拉施放魔法飞弹",
        context="context",
        source="dm",
        task_category="normal",
    )

    filled = agent._ensure_task_id(task)

    assert filled.task_id.startswith("task_")


def test_execution_result_normalizes_loose_json_shapes():
    result = ExecutionResult.model_validate(
        {
            "task_id": "task_demo",
            "field_changes": {},
            "narration": None,
            "triggered_chains": {},
        }
    )

    assert result.success is False
    assert result.field_changes == []
    assert result.narration == ""
    assert result.triggered_chains == []


def test_execution_result_syncs_categorized_changes_into_field_changes():
    result = ExecutionResult.model_validate(
        {
            "task_id": "task_demo",
            "resource_costs": {
                "path": "Malik.spell_slots.1环",
                "old_value": "4/4",
                "new_value": "3/4",
                "operation": "MOD",
                "source": "task_demo",
            },
            "primary_effects": {
                "path": "Aldera.combat.HP",
                "old_value": "44/44",
                "new_value": "33/44",
                "operation": "MOD",
                "source": "task_demo",
            },
        }
    )

    assert len(result.field_changes) == 2
    assert result.resource_costs[0].path == "Malik.spell_slots.1环"
    assert result.primary_effects[0].path == "Aldera.combat.HP"


def test_executor_builds_explicit_key_hints():
    agent = object.__new__(ExecutorAgent)
    task = TaskExecution(
        task_id="task_demo",
        description="马利克对艾尔德拉施放魔法飞弹",
        context="context",
        actor="Malik",
        target="Aldera",
        source="dm",
        task_category="normal",
    )

    hints = agent._build_key_hints(task)

    assert "Malik.spell_slots" in hints
    assert "Aldera.combat" in hints
    assert "马利克.spell_slots" in hints
    assert "Eldra.combat" in hints


def test_planner_normalizes_actor_target_from_kv_context():
    agent = object.__new__(DeepPlannerAgent)
    task = TaskExecution(
        task_id="task_demo",
        description="马利克对艾尔德拉施放魔法飞弹",
        context=(
            "【可写状态】[KV Malik.spell_slots] 1环: 4/4\n"
            "【可写状态】[KV Aldera.combat] HP: 44/44 | AC: 18\n"
            "【状态】[KV Aldera.status] 艾尔德拉·银誓 | 高等精灵\n"
            "【状态】[KV Malik.status] 马利克·山本 | 人类\n"
        ),
        actor="马利克",
        target="艾尔德拉",
        source="dm",
        task_category="normal",
    )

    normalized = agent._normalize_task(task)

    assert normalized.actor == "Malik"
    assert normalized.target == "Aldera"


def test_planner_backfills_actor_spell_slot_write_target_for_spell_tasks():
    agent = object.__new__(DeepPlannerAgent)
    task = TaskExecution(
        task_id="task_demo",
        description="马利克对艾尔德拉施放魔法飞弹",
        context=(
            "【可写状态】[KV Malik.spell_slots] 1环: 4/4 | 2环: 3/3 | 3环: 2/2\n"
            "【可写状态】[KV Aldera.combat] HP: 44/44 | AC: 18\n"
        ),
        action_type="spell",
        execution_steps=["进行伤害掷骰", "更新艾尔德拉的 HP"],
        write_targets=["Aldera.combat.HP"],
        actor="Malik",
        target="Aldera",
        source="dm",
        task_category="normal",
    )

    normalized = agent._normalize_task(task)

    assert "Malik.spell_slots.1环" in normalized.write_targets
    assert "Aldera.combat.HP" in normalized.write_targets


def test_resolution_window_normalizes_loose_json_shapes():
    window = ResolutionWindow.model_validate(
        {
            "window_id": "window_demo",
            "root_task_id": "task_magic_missile",
            "root_description": "马利克对艾尔德拉施放魔法飞弹",
            "shared_context": "[KV Malik.combat] HP: 32/32",
            "runs": {
                "order": 0,
                "priority": 10,
                "task_id": "task_magic_missile",
                "description": "马利克对艾尔德拉施放魔法飞弹",
                "field_changes": {},
                "triggered_chains": {},
                "narration": None,
            },
        }
    )

    assert window.shared_context == ["[KV Malik.combat] HP: 32/32"]
    assert len(window.runs) == 1
    assert window.runs[0].field_changes == []
    assert window.runs[0].triggered_chains == []
    assert window.runs[0].narration == ""


def test_resolution_window_run_can_be_built_from_task_and_result():
    task = TaskExecution(
        task_id="task_shield",
        description="艾尔德拉施放护盾术",
        context="context",
        actor="Aldera",
        target="Aldera",
        source="dm",
        task_category="normal",
    )
    result = ExecutionResult(
        task_id="task_shield",
        success=True,
        narration="护盾术使魔法飞弹伤害无效。",
        field_changes=[],
        triggered_chains=[],
    )

    run = ResolutionWindowRun.from_task_and_result(task, result, order=1, priority=5)

    assert run.task_id == "task_shield"
    assert run.description == task.description
    assert run.actor == "Aldera"
    assert run.priority == 5


def test_resolution_result_normalizes_loose_json_shapes():
    result = ResolutionResult.model_validate(
        {
            "window_id": "window_demo",
            "final_field_changes": {
                "path": "Aldera.combat.HP",
                "old_value": "44/44",
                "new_value": "33/44",
                "operation": "MOD",
                "source": "resolver:window_demo",
            },
            "discarded_field_changes": {
                "path": "Aldera.spell_slots.1环",
                "old_value": "4/4",
                "new_value": "3/4",
                "operation": "MOD",
                "source": "task_shield",
                "reason": "护盾术被更高优先级的法术反制。",
            },
            "resolution_summary": None,
            "dm_suggestions": "若引发新的规则问题，请由 DM 决定是否开启下一窗口。",
        }
    )

    assert len(result.final_field_changes) == 1
    assert result.final_field_changes[0].operation == Operation.MOD
    assert len(result.discarded_field_changes) == 1
    assert result.discarded_field_changes[0].reason == "护盾术被更高优先级的法术反制。"
    assert result.resolution_summary == ""
    assert result.dm_suggestions == ["若引发新的规则问题，请由 DM 决定是否开启下一窗口。"]


def test_resolution_result_syncs_categorized_changes_into_flattened_views():
    result = ResolutionResult.model_validate(
        {
            "window_id": "window_demo",
            "final_resource_costs": {
                "path": "Malik.spell_slots.1环",
                "old_value": "4/4",
                "new_value": "3/4",
                "operation": "MOD",
                "source": "resolver:window_demo",
            },
            "final_primary_effects": {
                "path": "Aldera.combat.HP",
                "old_value": "44/44",
                "new_value": "33/44",
                "operation": "MOD",
                "source": "resolver:window_demo",
            },
        }
    )

    assert len(result.final_field_changes) == 2
    assert result.final_resource_costs[0].path == "Malik.spell_slots.1环"
    assert result.final_primary_effects[0].path == "Aldera.combat.HP"


def test_discarded_state_change_extends_state_change_contract():
    change = DiscardedStateChange(
        path="Aldera.spell_slots.1环",
        old_value="4/4",
        new_value="3/4",
        operation=Operation.MOD,
        source="task_shield",
        reason="护盾术未能成功生效。",
        discarded_by="resolver:window_demo",
    )

    assert change.discarded_by == "resolver:window_demo"
    assert change.reason == "护盾术未能成功生效。"


def test_resolver_builds_path_hints_from_window_changes():
    agent = object.__new__(ResolverAgent)
    window = ResolutionWindow(
        window_id="window_demo",
        root_task_id="task_magic_missile",
        root_description="马利克对艾尔德拉施放魔法飞弹",
        shared_context=[],
        runs=[
            ResolutionWindowRun(
                order=0,
                priority=10,
                task_id="task_magic_missile",
                description="马利克对艾尔德拉施放魔法飞弹",
                field_changes=[
                    {
                        "path": "Aldera.combat.HP",
                        "old_value": "44/44",
                        "new_value": "33/44",
                        "operation": "MOD",
                        "source": "task_magic_missile",
                    }
                ],
            )
        ],
    )

    hints = agent._build_path_hints(window)

    assert "Aldera.combat.HP" in hints


def test_resolver_sanitizes_unknown_paths_and_sets_resolver_metadata():
    agent = object.__new__(ResolverAgent)
    window = ResolutionWindow(
        window_id="window_demo",
        root_task_id="task_magic_missile",
        root_description="马利克对艾尔德拉施放魔法飞弹",
        shared_context=[],
        runs=[
            ResolutionWindowRun(
                order=0,
                priority=10,
                task_id="task_magic_missile",
                description="马利克对艾尔德拉施放魔法飞弹",
                field_changes=[
                    {
                        "path": "Aldera.combat.HP",
                        "old_value": "44/44",
                        "new_value": "33/44",
                        "operation": "MOD",
                        "source": "task_magic_missile",
                    }
                ],
            )
        ],
    )
    result = ResolutionResult(
        window_id="wrong_window",
        final_field_changes=[
            {
                "path": "Aldera.combat.HP",
                "old_value": "44/44",
                "new_value": "33/44",
                "operation": "MOD",
                "source": "",
            },
            {
                "path": "Unknown.path",
                "old_value": "x",
                "new_value": "y",
                "operation": "MOD",
                "source": "",
            },
        ],
        discarded_field_changes=[
            {
                "path": "Aldera.combat.HP",
                "old_value": "44/44",
                "new_value": "33/44",
                "operation": "MOD",
                "source": "task_magic_missile",
                "reason": "被护盾术覆盖。",
            }
        ],
        resolution_summary="",
        dm_suggestions=["", "请 DM 确认护盾术是否成功。"],
    )

    sanitized = agent._sanitize_result(result, window)

    assert sanitized.final_field_changes == []
    assert sanitized.discarded_field_changes[0].discarded_by == "resolver:window_demo"
    assert sanitized.resolution_summary == "resolver 完成了当前结算窗口的合并裁决。"
    assert sanitized.dm_suggestions == ["请 DM 确认护盾术是否成功。"]


def test_executor_backfills_missing_hp_change_even_when_resource_cost_exists():
    agent = object.__new__(ExecutorAgent)
    task = TaskExecution(
        task_id="task_magic_missile",
        description="马利克对艾尔德拉施放魔法飞弹",
        context=(
            "[KV Malik.spell_slots] 1环: 4/4\n"
            "[KV Aldera.combat] HP: 44/44 | AC: 18\n"
        ),
        write_targets=["Malik.spell_slots.1环", "Aldera.combat.HP"],
        actor="Malik",
        target="Aldera",
        source="dm",
        task_category="normal",
    )
    result = ExecutionResult(
        task_id="task_magic_missile",
        success=True,
        resource_costs=[
            {
                "path": "Malik.spell_slots.1环",
                "old_value": "4/4",
                "new_value": "3/4",
                "operation": "MOD",
                "source": "task_magic_missile",
            }
        ],
        narration="马利克施放了魔法飞弹，造成了 11 点伤害。",
    )

    backfilled = agent._backfill_missing_changes(result, task)

    assert any(change.path == "Aldera.combat.HP" for change in backfilled.field_changes)


def test_executor_dedupes_changes_across_buckets():
    agent = object.__new__(ExecutorAgent)
    result = ExecutionResult(
        task_id="task_demo",
        success=True,
        resource_costs=[
            {
                "path": "Malik.spell_slots.1环",
                "old_value": "4/4",
                "new_value": "3/4",
                "operation": "MOD",
                "source": "task_demo",
            }
        ],
        primary_effects=[
            {
                "path": "Malik.spell_slots.1环",
                "old_value": "4/4",
                "new_value": "3/4",
                "operation": "MOD",
                "source": "task_demo",
            }
        ],
    )

    agent._dedupe_change_buckets(result)

    assert len(result.field_changes) == 1
    assert result.field_changes[0].path == "Malik.spell_slots.1环"


def test_resolver_removes_final_change_when_same_path_is_discarded():
    agent = object.__new__(ResolverAgent)
    window = ResolutionWindow(
        window_id="window_demo",
        root_task_id="task_demo",
        root_description="护盾术被法术反制",
        shared_context=[],
        runs=[
            ResolutionWindowRun(
                order=0,
                priority=5,
                task_id="task_demo",
                description="艾尔德拉施放护盾术",
                field_changes=[
                    {
                        "path": "Aldera.spell_slots.1环",
                        "old_value": "4/4",
                        "new_value": "3/4",
                        "operation": "MOD",
                        "source": "task_demo",
                    }
                ],
            )
        ],
    )
    result = ResolutionResult(
        window_id="window_demo",
        final_field_changes=[
            {
                "path": "Aldera.spell_slots.1环",
                "old_value": "4/4",
                "new_value": "3/4",
                "operation": "MOD",
                "source": "",
            }
        ],
        discarded_field_changes=[
            {
                "path": "Aldera.spell_slots.1环",
                "old_value": "4/4",
                "new_value": "3/4",
                "operation": "MOD",
                "source": "task_demo",
                "reason": "护盾术被法术反制。",
            }
        ],
    )

    sanitized = agent._sanitize_result(result, window)

    assert sanitized.final_field_changes == []
    assert len(sanitized.discarded_field_changes) == 1


def test_resolver_promotes_cancelled_resource_costs_to_discarded():
    agent = object.__new__(ResolverAgent)
    window = ResolutionWindow(
        window_id="window_demo",
        root_task_id="task_shield",
        root_description="护盾术被法术反制",
        shared_context=[],
        runs=[
            ResolutionWindowRun(
                order=0,
                priority=5,
                task_id="task_shield",
                description="艾尔德拉施放护盾术",
                field_changes=[
                    {
                        "path": "Aldera.spell_slots.1环",
                        "old_value": "4/4",
                        "new_value": "3/4",
                        "operation": "MOD",
                        "source": "task_shield",
                    }
                ],
            )
        ],
    )
    result = ResolutionResult(
        window_id="window_demo",
        final_resource_costs=[
            {
                "path": "Aldera.spell_slots.1环",
                "old_value": "4/4",
                "new_value": "3/4",
                "operation": "MOD",
                "source": "",
            }
        ],
        resolution_summary="护盾术因法术反制而失效。",
    )

    sanitized = agent._sanitize_result(result, window)

    assert sanitized.final_resource_costs == []
    assert len(sanitized.discarded_resource_costs) == 1
    assert sanitized.discarded_resource_costs[0].path == "Aldera.spell_slots.1环"
