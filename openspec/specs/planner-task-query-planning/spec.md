# planner-task-query-planning 规范

## 目的
定义 task_node 在单一 agent 模式下如何自主完成检索与任务起草，并约束 TaskDraft 中与查询规划、上下文保留和 grep 执行限额相关的公开契约。

## 需求
### 需求: task_node 必须作为单一 agent 自主完成检索与任务起草
系统必须要求 `task_node` 作为单一 agent 节点完成工具检索与 `TaskDraft` 起草，禁止继续把第一阶段拆成“先生成 query plan 再起草”的两个内部 agent 阶段。

#### 场景:task_node 处理需要状态证据的战斗指令
- **当** `task_node` 接收到一条需要从状态中寻找 actor、target、equipment 或 resource 的指令
- **那么** 它必须由同一个 agent 自主决定如何使用可用工具完成检索
- **那么** 它必须由同一个 agent 直接产出最终 `TaskDraft`
- **那么** workflow 不得要求先经过单独的 query planner agent

### 需求: TaskDraft 不得再公开保留 query_plan
系统必须要求 `TaskDraft` 不再公开保留 `query_plan` 作为中间字段，禁止把查询计划轨迹继续当作任务稿 schema 的一部分。

#### 场景:task_node 产出任务稿
- **当** `task_node` 成功生成 `TaskDraft`
- **那么** `TaskDraft` 只应包含任务稿和支持它的证据上下文
- **那么** `TaskDraft` 不得要求额外暴露显式 query plan 字段

### 需求: TaskDraft 必须只保留 task_node 认为合适的 context_lines
系统必须要求 `TaskDraft.context_lines` 只保留 `task_node` 认为适合支持当前任务稿的证据子集，禁止继续把所有命中或完整查询轨迹原样暴露。

#### 场景:task_node 形成最终 TaskDraft
- **当** `task_node` 完成检索并准备生成 `TaskDraft`
- **那么** 它必须只保留与最终任务稿直接相关的 `context_lines`
- **那么** `context_lines` 不得等于原始命中全集

### 需求: 检索执行不得依赖过低的固定 grep limit
系统必须要求 `task_node` 在使用 grep 时，不得依赖过低的固定 limit 作为通用默认值，禁止让相关证据在高噪音命中前被截断。

#### 场景:task_node 执行 actor 或 target 查询
- **当** `task_node` 使用 grep 检索可能命中大量属性行的实体查询
- **那么** 它必须使用足以覆盖相关证据的执行限额
- **那么** 它不得因为统一过低 limit 导致 hp、ac、equipment、resource 等关键证据无法进入任务稿
