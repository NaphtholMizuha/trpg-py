## 为什么

当前项目已经明确了 engine 和 store 的执行边界，但面向 DM 的 planner agent 仍缺少最基础的规则检索能力。为了让后续的 LLM 能根据 DM 指令自行推理并生成合法的 `TaskDocument`，系统需要先提供一个稳定、可复用的 `search` 工具，从 Qdrant 中检索与 query 匹配的规则原文。

## 变更内容

- 新增 `agent-search-tool` 能力，定义面向 agent 的规则文本检索工具。
- 在 `trpg_py.agent.tools` 包下提供 `search` 工具实现，负责根据 query 调用 Qdrant 执行混合检索，并通过 reranker 对候选结果重排。
- 约束 `search` 工具只返回检索命中的原始文本及其必要元数据，不负责规则归纳、结构化事实提取或 `TaskDocument` 生成。
- 为该工具提供 LangChain tool 封装，使 planner agent 可以直接以工具调用方式消费。
- 明确 Qdrant 检索输入输出契约、错误语义和空结果语义，为后续接入更多 agent 工具打基础。

## 功能 (Capabilities)

### 新增功能
- `agent-search-tool`: 提供从 Qdrant 检索规则原文并暴露为 LangChain tool 的 agent 搜索能力。

### 修改功能
- 无

## 影响

- 新增 `trpg_py.agent.tools` 命名空间及其模块组织约定。
- 新增与 Qdrant 客户端、embedding / sparse 检索链路及 reranker 交互的依赖和配置约定。
- 新增 LangChain tool 包装层，影响后续 planner agent 的工具集成方式。
- 为后续 `fetch_keys` 等 agent 工具建立统一的工具契约和返回形状。
