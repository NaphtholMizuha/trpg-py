# Ask Mode Rules

回答关于项目的问题时的上下文规则。

## 项目结构

- `src/agents/` - Agent 实现，继承 BaseAgent 的 ReAct 模式
- `src/tools/` - 工具实现，包含 KV 状态存储、逻辑引擎、RAG 检索
- `src/workflow/` - LangGraph 工作流节点和图定义
- `src/executors/` - 执行器（逻辑规则执行等）

## 关键设计决策

### V3 架构
- 使用 LangGraph 替代手动 ReAct 循环
- Planner → Chain → Executor 三段式架构
- 状态存储为纯文本 KV，LLM 直接读写

### 状态存储
- `world_state.txt` 是人类可读的文本格式
- `[Key] Value` 格式，Value 是自然语言段落
- 不是结构化数据，LLM 负责解析和生成

## 术语表

- **ReAct**: Reasoning + Acting 循环模式
- **RAG**: Retrieval-Augmented Generation，检索增强生成
- **KV State**: Key-Value 状态存储
- **Chain Agent**: 链式执行 Agent，负责具体任务执行
