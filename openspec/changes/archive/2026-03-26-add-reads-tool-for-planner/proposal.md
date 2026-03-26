## 为什么

当前 planner 已经有 `search` 和 `fetch_keys`，但前者只补规则证据，后者只补路径发现，planner 仍然无法直接读取状态值来确认实体 ID、AC、资源或法术位等关键信息。这会让像“哥布林用弯刀攻击 aldera”这样的指令在 state 明明已经包含答案时仍然触发不必要的 HITL。

## 变更内容

- 在 `trpg_py.agent.tools` 中新增 `reads` 工具，向 agent 暴露只读的状态值读取能力。
- 让 `reads` 工具复用现有 `state-store` 的 `reads` 语义，稳定返回命中、无命中和错误结果。
- 调整 planner 的工具集与规划策略，使 planner 可以结合 `fetch_keys + reads` 完成实体解析和关键参数确认，而不是仅凭路径枚举猜测。
- 提供对应的 smoke 脚本和测试，帮助开发者观察 `reads` 的值读取边界。

## 功能 (Capabilities)

### 新增功能
- `reads-tool`: 提供驻留在 `trpg_py.agent.tools` 命名空间下的只读状态值读取工具，供 planner 和其他 agent 在不写状态的前提下读取点路径值。

### 修改功能
- `agent-planner`: 扩展 planner 的证据工具能力，使其在需要实体 ID 或关键状态值时能够使用 `reads` 而不是直接进入 HITL。

## 影响

- 受影响代码主要位于 `trpg_py/agent/tools/`、`trpg_py/agent/planner.py`、`smoke/` 和对应测试。
- planner 默认工具集将从 `search + fetch_keys (+ lint)` 扩展为 `search + fetch_keys + reads (+ lint)`。
- planner 在默认 world state 存在答案时，预计会减少“请提供 actor/target id”这类可避免的澄清。
