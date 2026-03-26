## 为什么

当前仓库已经具备执行器（可消费 `TaskDocument`）和两类 planner 基础工具（`search`、`fetch_keys`），但缺少一个把 DM 指令转成可执行任务文档的统一规划层。结果是规则检索、状态路径发现、HITL 澄清和 JSON 产出流程分散在人工操作里，无法形成稳定的自动化链路。

现在推进该变更，可以把“指令理解 -> 证据收集 -> 任务文档生成 -> 人类澄清”收敛成单一契约，降低路径幻觉和错误 JSON 进入执行器的概率。

## 变更内容

- 新增 `agent planner` 能力，定义结构化输入输出协议，用于把 DM 指令规划为 `TaskDocument`。
- 明确 planner 第一版基于 LangChain Deep Agents（`deepagents`）实现主流程与工具编排。
- 新增 planner factory，统一模型接入与运行参数配置（`model/base_url/api_key/timeout/max_retries/interrupt_on`）。
- 规定 planner 必须编排 `search` 与 `fetch_keys` 工具完成证据收集，而不是无证据生成关键结论。
- 引入 `ready / needs_human / blocked` 三态规划结果，支持 human-in-the-loop。
- 规定 planner 采用“LLM 主导不确定性判定 + 最小硬约束兜底”的策略。
- 建立 `JSON Schema + validate_task_document` 双层校验闭环，保障产出文档可执行。
- 明确 planner 与 engine 的职责分离：planner 只生成文档，不执行步骤、不提交状态写入。

## 功能 (Capabilities)

### 新增功能
- `agent-planner`: 定义 planner 的职责边界、工具编排、HITL 语义、输出状态协议，以及 `TaskDocument` 生成与校验闭环。

### 修改功能
- `fetch-keys-tool`: 说明该工具被 planner 用作路径发现证据源，作为规划流程中的前置取证能力。
- `agent-search-tool`: 说明该工具被 planner 用作规则证据源，作为规划流程中的前置取证能力。

## 影响

- 受影响代码：`trpg_py.agent`（新增 planner 模块与接口）。
- 受影响规范：新增 `specs/agent-planner/spec.md`；增量修改 `specs/fetch-keys-tool/spec.md` 与 `specs/agent-search-tool/spec.md`。
- 受影响测试：新增 planner 的状态流、HITL 触发与产物校验测试。
- 受影响依赖：新增/启用 Deep Agents 相关运行依赖（`deepagents`，基于 LangGraph runtime）。
- 受影响配置：新增 planner factory 配置项与统一解析优先级（调用参数 > 环境变量 > 默认值）。
- 依赖关系：复用现有 `search`、`fetch_keys` 以及 `engine.core.validate_task_document`。
