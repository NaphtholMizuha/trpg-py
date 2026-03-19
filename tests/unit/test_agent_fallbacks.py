from src.agents.base import _extract_json_payload
from src.agents.deep_planner import DeepPlannerAgent
from src.agents.executor import ExecutorAgent
from src.agents.resolver import ResolverAgent
from src.tools.toolkit import SearchTool, WriteFieldsTool
from src.types import (
    DiscardedStateChange,
    ExecutionResult,
    Operation,
    ResolutionResult,
    ResolutionWindow,
    ResolutionWindowRun,
    TaskExecution,
)


class _FakeStore:
    def __init__(self, data: dict[str, str]):
        self._data = data

    def get_multi(self, keys: list[str]) -> dict[str, str]:
        return {key: value for key, value in self._data.items() if key in keys}

    def get_keys(self) -> list[str]:
        return list(self._data.keys())

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value


class _FakeRetriever:
    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, limit: int = 2):
        self.calls.append((query, limit))
        return [
            {
                "score": 0.9,
                "content": f"关于 {query} 的检索结果",
                "metadata": {"title": "规则片段", "file": "rules.md"},
            }
        ]


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


def test_executor_rejects_modifying_missing_spell_slot_field():
    agent = object.__new__(ExecutorAgent)
    task = TaskExecution(
        task_id="task_demo",
        description="艾尔德拉施放圣火术点燃火药桶",
        context=(
            "【可写状态】[KV Aldera.spell_slots] 1环: 4/4 | 2环: 2/2\n"
            "【参考状态】[KV Aldera.spells] 戏法: 圣火术 | DC: 15 | 法术攻击: +7"
        ),
        execution_steps=[],
        write_targets=["Aldera.spell_slots.戏法"],
        actor="Aldera",
        target="Barrel",
        source="dm",
        task_category="normal",
    )
    result = ExecutionResult(
        task_id="task_demo",
        success=True,
        field_changes=[
            {
                "path": "Aldera.spell_slots.戏法",
                "old_value": "4/4",
                "new_value": "3/4",
                "operation": "MOD",
                "source": "task_demo",
            }
        ],
        narration="错误地扣减了戏法法术位。",
        triggered_chains=[],
    )

    sanitized = agent._sanitize_result(result, task)

    assert sanitized.field_changes == []


def test_executor_accepts_explicit_add_for_missing_field():
    agent = object.__new__(ExecutorAgent)
    task = TaskExecution(
        task_id="task_demo",
        description="给火药桶新增燃烧层数字段",
        context=(
            "【可写状态】[KV Barrel.status] 火药桶 | 状态: 未爆炸\n"
            "【可新增字段】Barrel.status.燃烧层数"
        ),
        execution_steps=[],
        write_targets=["Barrel.status.燃烧层数"],
        actor="Aldera",
        target="Barrel",
        source="dm",
        task_category="normal",
    )
    result = ExecutionResult(
        task_id="task_demo",
        success=True,
        field_changes=[
            {
                "path": "Barrel.status.燃烧层数",
                "old_value": "",
                "new_value": "1",
                "operation": "ADD",
                "source": "task_demo",
            }
        ],
        narration="给火药桶新增燃烧层数。",
        triggered_chains=[],
    )

    sanitized = agent._sanitize_result(result, task)

    assert len(sanitized.field_changes) == 1
    assert sanitized.field_changes[0].path == "Barrel.status.燃烧层数"


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


def test_planner_normalize_write_targets_does_not_crash_on_field_path():
    agent = object.__new__(DeepPlannerAgent)
    agent.tools = {}
    task = TaskExecution(
        task_id="task_demo",
        description="点燃火药桶",
        context="【可写状态】[KV Barrel.status] 火药桶 | 状态: 未爆炸",
        execution_steps=[],
        write_targets=["Barrel.status.状态"],
        actor="Aldera",
        target="Barrel",
        source="dm",
        task_category="normal",
    )

    normalized = agent._normalize_task(task)

    assert normalized.write_targets == ["Barrel.status.状态"]


def test_write_fields_tool_rejects_adding_unknown_spell_slot_field():
    tool = WriteFieldsTool(store=_FakeStore({"Aldera.spell_slots": "1环: 4/4 | 2环: 2/2"}))

    output = tool._run(
        [
            {
                "path": "Aldera.spell_slots.戏法",
                "old_value": "",
                "new_value": "3/4",
                "operation": "ADD",
            }
        ]
    )

    assert "成功" in output
    assert "Aldera.spell_slots.戏法" in output


def test_search_tool_reuses_similar_query_within_session():
    retriever = _FakeRetriever()
    tool = SearchTool(retriever=retriever)

    first = tool._run("圣火术 点燃 物体", limit=2)
    second = tool._run("圣火术 对物体 目标", limit=2)

    assert "规则片段" in first
    assert "直接复用上一条检索结果" in second
    assert len(retriever.calls) == 1


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
    agent.tools = {}
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


def test_planner_hydrates_kv_lines_from_store_snapshot():
    agent = object.__new__(DeepPlannerAgent)
    agent.tools = {
        "read": type(
            "FakeReadTool",
            (),
            {
                "store": _FakeStore(
                    {
                        "Aldera.spells": "戏法: 圣火术 | 1环法术: 神恩、护盾术、圣光术 | 2环法术: 迷雾步、branding smite | DC: 15 | 法术攻击: +7",
                    }
                )
            },
        )()
    }
    task = TaskExecution(
        task_id="task_demo",
        description="艾尔德拉施放圣火术",
        context="【参考状态】[KV Aldera.spells] 法术: 圣火术 | 1环法术: 神恩、护盾术、圣光术 | 2环法术: 迷雾步、branding smite | DC: 15 | 法术攻击: +7",
        actor="Aldera",
        target="Barrel",
        source="dm",
        task_category="normal",
    )

    normalized = agent._normalize_task(task)

    assert (
        normalized.context
        == "【参考状态】[KV Aldera.spells] 戏法: 圣火术 | 1环法术: 神恩、护盾术、圣光术 | 2环法术: 迷雾步、branding smite | DC: 15 | 法术攻击: +7"
    )


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

    assert sanitized.final_field_changes[0].source == "resolver:window_demo"
    assert len(sanitized.final_field_changes) == 1
    assert sanitized.discarded_field_changes[0].discarded_by == "resolver:window_demo"
    assert sanitized.resolution_summary == "resolver 完成了当前结算窗口的合并裁决。"
    assert sanitized.dm_suggestions == ["请 DM 确认护盾术是否成功。"]
