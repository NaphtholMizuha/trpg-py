## 新增需求

## 修改需求

## 移除需求

### 需求: planner 必须使用 LangGraph 作为 workflow 编排真相
**Reason**: 编排真相将迁移到主 agent + delegate 运行时，不再强制绑定 LangGraph。
**Migration**: 将调用方依赖迁移到新的主 agent 入口，而不是 `workflow.py` 中的 LangGraph 图。

### 需求: task 节点核心必须由 langchain.create_agent 驱动
**Reason**: 新架构不再保留固定的 `task_node` 作为长期运行时真相。
**Migration**: 将上下文获取职责迁移到 Context Agent profile，而不是 `task_node`。

### 需求:第一阶段节点必须输出 TaskDraft 而不是受限动作分类
**Reason**: 新架构不再要求固定第一阶段节点与 `TaskDraft` 作为唯一中间真相。
**Migration**: 将中间结果迁移到 Context Agent 返回的高密度上下文包。

### 需求: dsl 节点核心必须由 langchain.create_agent 驱动
**Reason**: 新架构不再保留固定的 `dsl_node` 作为长期运行时真相。
**Migration**: 将校验与执行职责迁移到 Resolution Agent profile。

### 需求: workflow 必须以显式中间对象在两个 agent 节点之间传递状态
**Reason**: 新架构不再围绕固定两节点之间的状态对象流转。
**Migration**: 使用主 agent 委派返回的结构化 bundle 替代旧状态对象。

### 需求: 两个 agent 节点必须具有不同的工具边界
**Reason**: 固定节点边界将被默认子 agent profile 替代。
**Migration**: 将 Context Agent 与 Resolution Agent 的工具边界定义到 `delegating-agent-runtime` capability。

### 需求:task_node 必须把关键规则或状态证据以摘录形式写入 evidence
**Reason**: 旧 requirement 绑定到 `task_node` 与 `evidence` 字段，不再适合作为长期契约。
**Migration**: 将证据密度要求迁移到 Context Agent 的 `rule_evidence` 与 `state_evidence` 结果字段。

### 需求:task_node 必须为具名法术绑定默认施法环级
**Reason**: 该行为不再由固定 `task_node` 承担。
**Migration**: 将默认环级与资源绑定职责迁移到新的 Context/Resolution 分工中重新定义。

### 需求:task_node 必须把范围覆盖判定纳入范围法术任务结构
**Reason**: 该行为不再由固定 `task_node` requirement 表达。
**Migration**: 在新的主 agent 或子 agent 契约中重新定义范围覆盖判定责任。

### 需求:task_node 的 few-shot 必须展示位置获取且不得复用 Fireball 评测样例
**Reason**: 新架构不再以 `task_node` few-shot 作为长期架构真相。
**Migration**: 如仍需提示词约束，应在新的 agent profile prompt 契约中单独定义。

### 需求:TaskDraft 必须通过 evidence 与 states 暴露法术环级和范围前提
**Reason**: `TaskDraft` 不再是唯一必须存在的中间契约。
**Migration**: 将相关证据暴露要求迁移到新的上下文 bundle 结构。

### 需求:task_node prompt 必须明确指导 agent 使用 grep
**Reason**: 新架构不再保留 `task_node prompt` 作为长期契约。
**Migration**: 将 `grep` 的使用语义迁移到 Context Agent 的工具约束或 prompt 契约。

### 需求:task_node prompt 必须采用 judgment-first 顺序
**Reason**: 新架构不再保留 `task_node prompt` 的固定组织方式。
**Migration**: 如仍需保留该推理风格，应在新的 agent profile 中重新定义。

### 需求:task_node prompt 必须为规则检索选择查询模式
**Reason**: 该要求绑定到旧 `task_node` prompt 契约。
**Migration**: 将查询模式选择职责迁移到 Context Agent 的 search 使用约束。

### 需求:task_node prompt 必须区分规则身份证据与结算证据
**Reason**: 该要求绑定到旧 `task_node` prompt 契约。
**Migration**: 将证据类型区分迁移到 Context Agent 的结构化上下文产物。

### 需求:dsl_node 必须只翻译 TaskDraft 而不是重新理解任务
**Reason**: 新架构不再保留 `dsl_node` 与 `TaskDraft` 的固定翻译关系。
**Migration**: 将“不得重新理解任务”的约束迁移到 Resolution Agent 对上下文包的消费契约。

### 需求:TaskDraft 的 missing_info 必须包含默认值语义
**Reason**: `TaskDraft` 不再是唯一必须存在的中间结构。
**Migration**: 将缺口与默认处理语义迁移到新的上下文 bundle 字段。

### 需求:dsl_node 的 few-shot 必须复用 task_node 的任务类型原型
**Reason**: 新架构不再保留 `dsl_node` few-shot 契约。
**Migration**: 如仍需保留样例对齐，应在新的 agent profile prompt 契约中重新定义。

### 需求:task_node prompt 必须感知下游 dsl node 和 engine 的职责边界
**Reason**: 新架构中的职责边界不再围绕 `task_node/dsl_node` 命名。
**Migration**: 将职责边界迁移到主 agent、Context Agent、Resolution Agent 的分工定义。

### 需求:task_node prompt 必须禁止把运行期随机结果写入 missing_info
**Reason**: 该约束绑定到旧 `task_node` prompt 和 `missing_info` 字段。
**Migration**: 在新的上下文 bundle 缺口契约中重新定义“前置缺口”和“运行期结果”的边界。

### 需求:task_node prompt 必须以执行不变量与缺口暴露为主线
**Reason**: 新架构不再保留旧 `task_node` prompt 契约。
**Migration**: 如需保留该原则，应在 Context Agent 的 profile 规范中重新定义。

### 需求:dsl_node 必须基于 primitive 语义做 lowering 与组合
**Reason**: 新架构不再保留固定 `dsl_node` 的长期 requirement。
**Migration**: 将 primitive 语义消费职责迁移到 Resolution Agent 或其内部求解器契约。
