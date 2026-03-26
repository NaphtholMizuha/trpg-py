## 为什么

最近的 planner+engine 端到端 smoke 暴露出一个高价值缺口：在 DnD5e 攻击场景下，planner 可能生成“可执行但语义不完整”的 TaskDocument，遗漏 `check.attack` 的 `tags=["nat"]`，或遗漏把 `crit_success` 传播到 `damage.apply.is_critical`。这会让天然 20 在执行阶段只表现为普通命中，而不是暴击。

现在处理这件事很合适，因为引擎已经具备正确的暴击语义，问题主要集中在 planner 默认提示词和回归守护不足，修复成本低但对端到端可信度提升很大。

## 变更内容

- 强化 planner 默认 prompt 中的 DnD5e 攻击规划指导，明确攻击检定默认应保留 `nat` 标签语义。
- 强化 planner 默认 prompt 中的后续伤害规划指导，明确攻击命中后若存在 `damage.apply`，应把前序 `crit_success` 映射到 `is_critical`。
- 调整 canonical example 或等价说明，使“攻击检定 -> 暴击结果 -> 伤害暴击扩展”这一链路更显式、更难被模型遗漏。
- 为 planner prompt 与 smoke 回归补充测试或复核任务，防止后续提示词演化再次丢失该语义。

## 功能 (Capabilities)

### 新增功能

无

### 修改功能

- `agent-planner`: planner 默认提示词必须稳定保留 DnD5e 攻击中的 `nat` 标签与暴击伤害传播语义。

## 影响

- `config/prompts/planner_system.txt`
- `config/prompts/planner_user.txt`
- `tests/test_agent_planner.py`
- 可能涉及 `tests/test_smoke_scripts.py` 或手动 smoke 复核说明
