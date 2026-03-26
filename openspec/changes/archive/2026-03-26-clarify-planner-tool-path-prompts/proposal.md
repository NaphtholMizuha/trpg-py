## 为什么

当前 planner prompt 同时向模型展示了 `TaskDocument` 的 `$ref` 命名空间路径（如 `state.actors.goblin_1.ac`）和工具要消费的真实 store 点路径，但没有明确区分这两者的语义边界。结果是 planner 在调用 `fetch_keys` 和 `reads` 时把 `state.` 前缀误当成工具路径的一部分，导致本地 smoke 明明已有完整 state 数据却仍然错误进入 `needs_human`。

这个问题现在值得优先修，因为 `reads` / `lint` / 外置 prompt 刚刚完成接入，prompt 已经成为 planner 行为的主要控制面。如果不尽快把路径语义讲清楚，后续继续堆叠示例和工具说明只会放大这种误导。

## 变更内容

- 优化 planner 的 system/user prompt，明确区分“工具调用使用裸 store 路径”和“TaskDocument `$ref` 使用 `state.` / `context.` / `result.` 命名空间”这两套路径语法。
- 调整 prompt 中关于 `fetch_keys`、`reads` 和 canonical example 的表述，避免模型把 `state.actors...` 直接复制到工具参数里。
- 增加更贴近当前 smoke world state 的路径示例，让 planner 知道如何先用 `actors...` 做路径发现和值确认，再在最终 `TaskDocument` 中写成 `state.actors...` 引用。
- 为该提示词边界补充测试，防止后续 prompt 迭代再次把工具路径和 `$ref` 路径混淆。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `agent-planner`: planner 的提示词必须显式区分工具路径和 `TaskDocument` 引用路径，避免因路径命名空间混淆而错失已有 state 证据。

## 影响

- `config/prompts/planner_system.txt` 与 `config/prompts/planner_user.txt` 的路径语义说明、示例和工具使用指导
- `trpg_py/agent/planner.py` 相关 prompt 装载测试与可能的 smoke 断言
- `tests/test_agent_planner.py`、`tests/test_smoke_scripts.py` 等覆盖 planner 默认 prompt 行为的测试
