## 新增需求

### 需求:planner workflow 必须由主 agent 通过 delegate 编排子 agent
系统必须让 planner workflow 由主 agent 通过 `delegate` 编排子 agent，而不是继续把固定两阶段节点作为 workflow 真相。

#### 场景:workflow 需要完成一次完整规划
- **当** planner workflow 收到一条 instruction
- **那么** 主 agent 必须能够把上下文采集委派给 Context Agent
- **那么** 主 agent 必须能够把校验与执行委派给 Resolution Agent
- **那么** 调用方不得手工拼装旧的阶段节点来完成同一流程

## 修改需求

## 移除需求

### 需求:planner 必须提供位于 planner 根目录的 workflow 入口
**Reason**: 编排真相从固定 planner 根目录 workflow 入口迁移到主 agent 运行时。
**Migration**: 将调用入口迁移到新的 `augury.agent` 主 agent 接口或其等价公共入口。

### 需求:planner 必须在 nodes 目录下拆分两个阶段节点文件
**Reason**: 新架构不再以固定两阶段节点文件作为长期真相。
**Migration**: 将阶段职责迁移到主 agent、Context Agent 与 Resolution Agent 的 profile 和工具边界。

### 需求:第一阶段节点必须把 DM 指令转换为半结构化任务概述
**Reason**: 新架构不再要求以固定“第一阶段节点”作为唯一任务理解入口。
**Migration**: 将任务理解迁移到 Context Agent 返回的结构化上下文包。

### 需求:第二阶段节点必须把任务概述翻译为 TaskDocument DSL
**Reason**: 新架构不再要求以固定“第二阶段节点”作为唯一求解入口。
**Migration**: 将求解职责迁移到 Resolution Agent，并由其决定 lint 与 execute 的调用顺序。

### 需求:workflow 必须以明确的中间对象在两阶段之间传递状态
**Reason**: 新架构不再围绕固定的两阶段中间对象流转。
**Migration**: 使用 `ContextBundle`、`ResolutionBundle` 或等价结构作为新的委派结果契约。
