from src.agents.base import _extract_json_payload
from src.agents.deep_planner import DeepPlannerAgent
from src.agents.executor import ExecutorAgent
from src.types import ExecutionResult, TaskExecution


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
