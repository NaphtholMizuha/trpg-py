## 新增需求

## 修改需求

### 需求:两个 agent 节点必须具有不同的工具边界
系统必须对两个 agent 节点施加不同的 tools 边界：第一阶段节点负责任务理解与上下文获取，第二阶段节点负责 DSL 翻译与校验，禁止默认让两个节点共享完全相同的工具集合。

#### 场景:workflow 装配两个节点
- **当** workflow 装配 task 节点与 dsl 节点
- **那么** task 节点必须作为单一 agent 自主使用受限的上下文收集工具集合完成检索与任务起草
- **那么** task 节点的默认工具边界应服务于生成合适的任务上下文，而不是暴露单独的 query planning 阶段
- **那么** dsl 节点必须获得面向 DSL 生成与校验的工具集合

### 需求:task_node prompt 必须明确指导 agent 使用 grep
系统必须要求 `task_node` 的 prompt 明确指导 agent 如何更好地使用 `grep`，禁止继续只依赖抽象高层描述让 agent 自由摸索。

#### 场景:task_node 需要从状态中发现实体与资源
- **当** `task_node` 处理需要使用 `grep` 的 instruction
- **那么** prompt 必须说明如何从自然语言实体、物品、法术或资源构造更合适的 `grep` 查询
- **那么** prompt 必须说明如何消费 `grep` 返回的 `key`、`value` 和 `sim`
- **那么** prompt 必须说明哪些低相关命中不应进入最终 `context_lines`

#### 场景:task_node prompt 使用 few-shot
- **当** `task_node` prompt 需要帮助 agent 学会稳定使用 `grep`
- **那么** prompt 可以包含 few-shot 示例
- **那么** few-shot 必须展示从 instruction 到 `grep` 使用再到任务稿取舍的代表性过程

## 移除需求
