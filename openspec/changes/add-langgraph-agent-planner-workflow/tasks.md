## 1. LangGraph Workflow

- [ ] 1.1 在 `src/augury/planner/workflow.py` 中将 planner 主入口重构为 LangGraph workflow，定义最小 graph state、入口和结束流转。
- [ ] 1.2 将 workflow 的状态对象改为围绕 `TaskDraft` 与 TaskDocument 结果边界，确保 graph 在两个阶段之间传递显式任务稿。

## 2. Agent Nodes

- [ ] 2.1 将第一阶段节点从 `intent_node` 重命名并重构为 `task_node`，继续使用 `langchain.create_agent` 作为核心执行体。
- [ ] 2.2 设计并实现 `TaskDraft` 中间对象，至少覆盖 `task / reads / judgments / writes / missing_info / assumptions`。
- [ ] 2.3 重构 `src/augury/planner/nodes/dsl_node.py`，使其以 `TaskDraft` 作为主要输入来源完成 DSL 翻译。
- [ ] 2.4 为两个节点分别收敛 tools 边界，确保 `task_node` 使用上下文检索工具、`dsl_node` 使用 DSL 生成/校验工具。

## 3. Integration And Validation

- [ ] 3.1 将 workflow、`task_node`、`dsl_node`、共享类型和 planner tools 串接为可运行的 LangGraph 主链路。
- [ ] 3.2 新增或更新最小测试，验证 workflow 通过 LangGraph 顺序执行 `task_node -> dsl_node` 并以 `TaskDraft` 作为中间状态产出结构化结果。
