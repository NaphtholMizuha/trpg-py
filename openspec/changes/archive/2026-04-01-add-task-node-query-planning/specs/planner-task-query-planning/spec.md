## 新增需求

### 需求:task_node 必须作为单一 agent 自主完成检索与任务起草
系统必须要求 `task_node` 作为单一 agent 节点完成工具检索与 `TaskDraft` 起草，禁止继续把第一阶段拆成“先生成 query plan 再起草”的两个内部 agent 阶段。

#### 场景:task_node 处理需要状态证据的战斗指令
- **当** `task_node` 接收到一条需要从状态中寻找 actor、target、equipment 或 resource 的指令
- **那么** 它必须由同一个 agent 自主决定如何使用可用工具完成检索
- **那么** 它必须由同一个 agent 直接产出最终 `TaskDraft`
- **那么** workflow 不得要求先经过单独的 query planner agent

### 需求:TaskDraft 不得再公开保留 query_plan
系统必须要求 `TaskDraft` 不再公开保留 `query_plan` 作为中间字段，禁止把查询计划轨迹继续当作任务稿 schema 的一部分。

#### 场景:task_node 产出任务稿
- **当** `task_node` 成功生成 `TaskDraft`
- **那么** `TaskDraft` 只应包含任务稿和支持它的证据上下文
- **那么** `TaskDraft` 不得要求额外暴露显式 query plan 字段

### 需求:TaskDraft 必须只保留 task_node 认为合适的 context_lines
系统必须要求 `TaskDraft.context_lines` 只保留 `task_node` 认为适合支持当前任务稿的证据子集，禁止继续把所有命中或完整查询轨迹原样暴露。

#### 场景:task_node 形成最终 TaskDraft
- **当** `task_node` 完成检索并准备生成 `TaskDraft`
- **那么** 它必须只保留与最终任务稿直接相关的 `context_lines`
- **那么** `context_lines` 不得等于原始命中全集

### 需求:检索执行不得依赖过低的固定 grep limit
系统必须要求 `task_node` 在使用 grep 时，不得依赖过低的固定 limit 作为通用默认值，禁止让相关证据在高噪音命中前被截断。

#### 场景:task_node 执行 actor 或 target 查询
- **当** `task_node` 使用 grep 检索可能命中大量属性行的实体查询
- **那么** 它必须使用足以覆盖相关证据的执行限额
- **那么** 它不得因为统一过低 limit 导致 hp、ac、equipment、resource 等关键证据无法进入任务稿

## 修改需求

### 需求:workflow 必须以显式中间对象在两个 agent 节点之间传递状态
系统必须在 LangGraph workflow 的状态对象中显式保存第一阶段产出的中间对象，禁止让第二阶段节点只依赖原始 DM 指令或自由文本重新开始理解任务。

#### 场景:workflow 从 task 节点流转到 dsl 节点
- **当** workflow 收到第一阶段节点结果
- **那么** 它必须把该结果作为显式状态字段传给第二阶段节点
- **那么** 第一阶段结果应当能够包含任务稿和经过筛选的 `context_lines`
- **那么** 第二阶段节点无需从零重新解析原始 DM 指令

## 移除需求

### 需求:task_node 必须先生成 grep 查询计划再执行检索
删除这个需求。`task_node` 不再要求先显式生成 query plan。

### 需求:第一版查询计划必须完全由 agent 生成
删除这个需求。当前变更不再围绕 query plan schema 设计。

### 需求:查询计划必须输出 grep 可执行表达式
删除这个需求。工具调用合法性仍重要，但不再通过公开的 query plan schema 建模。

### 需求:查询计划必须成为 task_node 的可观察中间结果
删除这个需求。当前阶段只要求最终保留合适的 `context_lines`。

### 需求:当前阶段不得要求自动判断查询是否过宽
删除这个需求。当前变更不再把“query planning”作为公开能力建模。
