## 为什么

当前项目把 planner 真相绑定在 `LangGraph + task_node + dsl_node` 的两阶段流程上，并把大量手动验证能力长期放在 `src/smoke/`。这让主流程、验证入口和工具边界都围绕旧架构生长，难以演进成一个以委派、子 agent 分工和高密度上下文交换为核心的新系统。

现在需要一次明确的架构切换：以一个主 agent 统一编排技能与委派，用专职子 agent 处理上下文获取与执行求解，并移除所有 smoke 作为长期产品真相，把可回归验证收敛到自动测试与版本化评测入口。

## 变更内容

- **BREAKING** 用主 agent 委派架构替换当前固定的 `task_node -> dsl_node` planner 主流程。
- **BREAKING** 删除 `src/smoke/` 下现有 smoke 入口，并废止把 smoke 目录作为长期验证契约的规范要求。
- 新增主 agent 运行时，要求主 agent 默认具备 `list_skills`、`load_skills`、`delegate` 三个工具，并以它们作为编排真相。
- 新增 Context Agent，要求其默认工具集为 `grep` 与 `search`，并以高信息密度的结构化上下文包返回规则证据、状态证据和未决缺口。
- 新增 Resolution Agent，要求其默认工具集为 `lint` 与 `execute`，并返回结构化的校验与执行结果，而不是只暴露中间节点内部状态。
- 新增 `execute` 工具契约，把现有 engine 执行能力包装为 agent 可调用工具，稳定返回执行报告与状态变化。
- 调整现有 `grep`、`search` 等工具规范，使其围绕子 agent 协作而不是旧的 smoke 与节点分工来定义。
- 调整验证策略，把端到端验证与固定案例回归收敛到自动测试和评测 fixture，而不是手动 smoke 脚本。

## 功能 (Capabilities)

### 新增功能
- `delegating-agent-runtime`: 定义主 agent、`list_skills`/`load_skills`/`delegate` 工具、Context Agent、Resolution Agent，以及它们之间的结构化委派契约。
- `execute-tool`: 定义面向 agent 的 `execute` 工具包装，复用现有 engine 执行链路并稳定返回执行报告与状态变化。

### 修改功能
- `agent-planner`: 将对外 planner 入口从 smoke 驱动的固定 planner 流程调整为主 agent 委派入口。
- `planner-workflow`: 将 workflow 真相从两阶段节点拼接调整为主 agent 编排和子 agent 委派。
- `planner-langgraph-workflow`: 移除对 LangGraph、`task_node`、`dsl_node` 固定编排和中间对象传递方式的依赖，改为委派式运行时约束。
- `agent-search-tool`: 删除 `search` 的 smoke 脚本契约，并将其默认使用语义收敛到 Context Agent 的规则上下文采集契约。
- `grep-tool`: 删除 `grep` 的 smoke 脚本契约，并将其默认使用语义收敛到 Context Agent 的状态上下文采集契约。
- `src-project-layout`: 删除 `src/smoke/` 作为长期目录约束的要求，保留运行时代码与自动测试的 `src/` 布局真相。
- `smoke-test-layout`: 废止以 smoke 目录集中手动验证脚本的长期规范要求。
- `planner-task-smoke-test`: 废止 task smoke 脚本要求。
- `planner-execution-smoke`: 废止 planner 到 engine 端到端 smoke 脚本要求。
- `dsl-execution-smoke`: 废止 dsl smoke 脚本要求。

## 影响

- 受影响代码主要包括 `src/augury/planner/`、`src/augury/planner/nodes/`、`src/augury/planner/tools/`、`src/augury/engine/`、`src/smoke/` 和 `src/tests/`。
- 对外 API 会从“固定 workflow/节点驱动”转向“主 agent + delegate 驱动”，属于破坏性行为调整。
- 需要新增 agent 运行时数据契约，例如 `ContextBundle`、`ResolutionBundle` 或等价结构。
- 需要把现有 engine 执行能力提升为可稳定复用的 agent 工具，并重新梳理回归验证与 fixture 组织方式。
