## 为什么

当前 planner 主流程建立在 `deepagents.create_deep_agent()` 之上，但 planner 实际上只是一个窄域的任务文档规划器，不需要 deep agent 默认附带的通用 coding-agent 能力。现状会额外引入大段基础 prompt 和多种与 planner 无关的 middleware，导致 token 开销偏高、工具行为更难收敛，也让 planner 的运行时语义被不必要地耦合到 `deepagents` 的默认实现细节。

现在需要把 planner 重构为直接基于 `langchain.agents.create_agent()` 创建运行图，在保持现有 `ready / needs_human / blocked` 契约、结构化输出、HITL 与日志能力不变的前提下，移除 deep agent 默认栈带来的 prompt 和 middleware 负担，为后续进一步向显式 LangGraph 工作流演进打下更小、更可控的基础。

## 变更内容

- 将 planner 的默认 agent factory 从 `deepagents.create_deep_agent()` 替换为 `langchain.agents.create_agent()`。
- 保留 planner 当前的对外契约与关键运行能力，包括：
  - `PlannerRequest` / `PlannerResult` 结构化接口
  - `ToolStrategy(PlannerResult)` 结构化输出约束
  - `interrupt_on` / checkpointer 驱动的 HITL 恢复语义
  - 现有 planner 文件日志与 smoke 入口
- 移除 planner 对 deep agent 默认 coding-agent prompt/middleware 栈的依赖，不再要求 planner 运行必须加载与文件系统、待办清单、子代理或补丁工具相关的默认能力。
- 让 planner runtime 更贴近“受控工具型 agent”，并为后续按需引入更细粒度 LangGraph 节点留出清晰边界。

## 功能 (Capabilities)

### 修改功能
- `agent-planner`: planner 的运行时实现从 `deepagents.create_deep_agent()` 重构为 `langchain.agents.create_agent()`，并明确其必须保持现有结构化输出与 HITL 能力，同时移除 deep agent 默认 coding-agent 栈依赖。

## 影响

- `trpg_py/agent/planner.py` 中 planner factory 与默认 agent factory 的实现方式。
- planner 对 `deepagents` 的默认运行时依赖与相关测试断言。
- 与 planner factory、结构化输出、HITL 和日志行为相关的单元测试与 smoke 测试。
- 后续 planner 向自定义 LangGraph 工作流演进时的实现基线。
