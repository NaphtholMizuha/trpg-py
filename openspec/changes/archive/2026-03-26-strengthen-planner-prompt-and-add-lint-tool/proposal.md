## 为什么

当前 planner 已经具备结构化三态输出和最终校验闭环，但提示词过于简略，只告诉模型“生成 TaskDocument”，没有充分暴露引擎 DSL 的最小骨架、合法步骤类型和规范示例，导致模型容易产出看似合理却不合法的任务文档。与此同时，planner 只能在最终输出后被动收到校验失败反馈，缺少可在规划过程中主动自检并修复候选文档的工具。

## 变更内容

- 增强 planner prompt，让模型显式知道合法 `TaskDocument` 的最小结构、允许的 `type/kind` 组合、引用约定和代表性示例。
- 在 `trpg_py.agent.tools` 中新增 `lint` 工具，用于对候选 `TaskDocument` 执行只读校验并返回结构化错误结果。
- 调整 planner 的工具编排与提示词约束，使 planner 能在准备返回 `ready` 前主动调用 `lint` 做自检，而不是仅依赖最终兜底修复回路。
- 保持现有后端 Schema + 执行器双层校验作为最终守门，避免将合法性责任完全下放给 prompt 或工具调用策略。

## 功能 (Capabilities)

### 新增功能
- `lint-tool`: 提供驻留在 `trpg_py.agent.tools` 命名空间下的只读任务文档校验工具，供 planner 和其他调用方主动检查候选 `TaskDocument`。

### 修改功能
- `agent-planner`: 强化 planner 对 `TaskDocument` DSL 的显式建模，并要求 planner 在可行时利用 `lint` 工具进行自检收口。

## 影响

- 受影响代码主要位于 `trpg_py/agent/planner.py`、`trpg_py/agent/tools/`、`config/prompts/` 与对应测试。
- planner 默认工具集将从 `search + fetch_keys` 扩展为 `search + fetch_keys + lint`。
- smoke 和调试链路将更容易暴露 planner 是“不会写 DSL”还是“会写但细节不合法”。
