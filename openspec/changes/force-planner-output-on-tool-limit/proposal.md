## 为什么

当前 planner 在单次规划内一旦触发 `ToolCallLimitExceededError`，会立即中止本轮并返回 `needs_human/tool_budget_exhausted`。这让已经收集到的证据和已形成的候选结论无法被最后一次整理成结构化结果，导致“预算耗尽”被误当成“必须人工介入”。

## 变更内容

- 调整 planner 的工具预算耗尽语义：达到工具上限后不得立即终止整个规划，而是必须基于当前上下文进入一次“无工具最终收敛”阶段。
- 要求最终收敛阶段禁止再次调用工具，只能整理已有证据并输出 `ready`、`needs_human` 或 `blocked` 中的一个结构化结果。
- 明确只有在最终收敛阶段仍无法得到合法结果时，planner 才能返回 `needs_human/tool_budget_exhausted`；若已有证据足够，则必须正常输出结果。
- 为日志、调试信息和测试补充“预算耗尽后强制输出”的可观察性，确保 smoke 能区分“预算触发收尾”与“真正未收敛”。

## 功能 (Capabilities)

### 新增功能

无

### 修改功能

- `agent-planner`: planner 在工具预算耗尽时必须从“立即停止”改为“禁止继续取证，但强制输出最终结构化结果”。

## 影响

- `trpg_py/agent/planner.py` 中的工具预算异常处理与轮次收敛逻辑
- planner prompt 与 runtime/debug 日志中对工具预算语义的说明
- 覆盖 `ToolCallLimitExceededError` 的单元测试和 smoke 行为断言
