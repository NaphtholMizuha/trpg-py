## 1. Planner Runtime 替换

- [x] 1.1 将 `trpg_py.agent.planner` 的默认 agent factory 从 `deepagents.create_deep_agent()` 替换为 `langchain.agents.create_agent()`
- [x] 1.2 移除 planner 对 deep agent 默认 coding-agent prompt/middleware 栈的依赖，只保留 planner 真实需要的运行时能力
- [x] 1.3 保持 `ToolStrategy(PlannerResult)`、工具集合与 planner 对外结构化契约不变

## 2. HITL 与兼容性收口

- [x] 2.1 在 `create_agent()` 路径下保留 `interrupt_on`、checkpointer 与 resume/thread 语义
- [x] 2.2 更新或补充 planner factory 与 smoke 相关测试，覆盖默认 runtime、结构化输出与中断恢复能力

## 3. 验证与文档

- [x] 3.1 运行 planner 相关单元测试与 smoke 测试，确认 `ready / needs_human / blocked` 契约不回退
- [x] 3.2 更新必要的文档或注释，明确 planner 默认基于 `create_agent()` 而不再依赖 deep agent 默认实现
