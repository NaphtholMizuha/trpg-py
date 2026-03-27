## 为什么

当前 planner 在单次 `agent.invoke(...)` 内会围绕同一类状态缺口反复调用 `list`、`read`、`search` 与 `lint`，即使工具已经给出了 `no_match` 与建议路径，也仍可能继续重复试探。这会放大延迟、污染日志，并让明显应当快速收口为“没有此状态事实”或“需要人工确认”的场景变成长时间打转。

## 变更内容

- 将 planner 的状态取证策略收敛为“先 `list` 发现，再尽量批量 `read` 确认”，避免把同类值拆成大量零散读取。
- 明确 `list` / `read` 的 `status=no_match` 语义是“当前 state 中未找到对应事实”，planner 不得把它继续当作“也许只是没查对”的无限重试信号。
- 要求 planner 在相同路径、相同前缀或相同缺口上限制重复取证次数；若建议路径仍未命中，则必须转为收口结论，而不是机械重试。
- 为 planner runtime 增加单轮工具调用次数上限，避免一次 `agent.invoke(...)` 内无限工具循环。
- 更新 prompt、smoke 与测试，覆盖“批量 read”“no_match 视为缺失事实”“工具调用上限触发收口”的行为。

## 功能 (Capabilities)

### 新增功能

无

### 修改功能

- `agent-planner`: planner 必须把 `no_match` 视为缺失事实证据、优先批量 `read`，并在重复失败或超出工具预算时强制收口。
- `fetch-keys-tool`: `list`/`fetch_keys` 的无命中语义需要进一步约束为可供 planner 直接收口的缺失事实证据，而不是鼓励无限试探。
- `reads-tool`: `read`/`reads` 需要支持 planner 以批量读取方式确认同类状态值，并让无命中语义稳定可消费。
- `planner-execution-smoke`: 端到端 smoke 需要覆盖 planner 在缺失法术位、缺失法术或工具预算耗尽时的可解释收口结果。

## 影响

- `trpg_py/agent/planner.py` 及 planner factory/runtime 配置
- planner prompt 模板、planner debug 日志与工具调用策略
- `trpg_py/agent/tools/fetch_keys.py`、`trpg_py/agent/tools/reads.py` 的 planner-facing 语义说明
- `smoke/test_planner.py`、`smoke/test_planner_engine.py` 与相关单元/集成测试
