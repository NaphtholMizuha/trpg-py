## 为什么

当前 planner 虽然已经基于 `create_agent()` 和 runtime 护栏运行，但“信息取证”“DSL 生产”“lint 修复”“HITL 暂停/恢复”仍混在一个主循环里。这让工具预算、错误语义和 `needs_human` 的恢复语义持续互相污染，也让后续把 planner 演进成更稳定的 staged workflow 变得困难。

## 变更内容

- 将 planner 主流程重构为显式的 LangGraph 工作流，而不是继续把全部职责塞进单一 planner agent 调用。
- 将 planner 拆成两个 `create_agent()` 节点：
  - `evidence_agent`：只负责 `search`、`list`、`read`
  - `dsl_agent`：只负责基于证据产出 `TaskDocument`，并使用 `lint` 自我迭代
- 在两个阶段之间引入轻量 `EvidenceBundle`，仅承载证据小结、关键事实、缺口、假设和来源路径，而不是过度结构化的全量中间模型。
- 明确 `needs_human` 在内部语义上是可恢复的 HITL 暂停，而不是 planner 工作流的终止；graph 必须支持在同一 thread/state 上 resume。
- 更新 smoke 与相关规范，使调用方能观察 graph 阶段、HITL 暂停点以及恢复后的继续收敛。

## 功能 (Capabilities)

### 新增功能

无

### 修改功能

- `agent-planner`: planner 必须从单体 agent 规划循环演进为 LangGraph staged workflow，并使用轻量 `EvidenceBundle` 串接取证与 DSL 阶段。
- `planner-execution-smoke`: smoke 必须与 staged planner 对齐，把 `needs_human` 视为 HITL 暂停/恢复点，并展示 graph 阶段信息。

## 影响

- `trpg_py/agent/planner.py` 及其 planner factory/runtime 结构
- planner prompt、日志和调试负载的阶段化表达
- HITL resume 语义与 thread/checkpointer 接线
- `smoke/test_planner.py`、`smoke/test_planner_engine.py` 以及相关测试
