# Architect Mode Rules

架构决策和设计约束。

## 核心架构

### V3 三层架构
1. **Planner** - 任务规划，将自然语言拆分为可执行任务
2. **Chain** - 链式执行，调用工具链完成任务
3. **Executor** - 规则执行，处理确定性逻辑（如伤害计算）

### 状态管理
- **单文件文本存储**: `world_state.txt` 作为唯一状态源
- **LLM 可读写**: 状态格式为人类可读的自然语言
- **原子操作**: `patch()` 方法保证状态变更是原子性的

## 设计约束

### Agent 设计
- **无状态 Agent**: Agent 不保存对话历史，状态完全依赖外部存储
- **工具注入**: 所有工具通过构造函数注入，便于测试和替换

### LLM 集成
- **OpenAI 兼容接口**: 使用 LangChain ChatOpenAI，支持 DeepSeek 等兼容服务
- **工具绑定**: 通过 `bind_tools()` 自动处理工具调用

### 扩展性
- **工具注册**: 新工具继承 LangChain BaseTool，自动可被 Agent 使用
- **工作流节点**: LangGraph 节点可自由组合，支持条件分支
