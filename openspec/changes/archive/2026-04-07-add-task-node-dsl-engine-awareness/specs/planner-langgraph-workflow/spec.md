## 新增需求

### 需求:task_node prompt 必须感知下游 dsl node 和 engine 的职责边界
系统必须要求 `task_node` 的 prompt 明确知道 TaskDraft 只是 planner workflow 的第一阶段输出，其后还有 `dsl node` 将任务稿翻译为结构化 TaskDocument，且最终由 engine 在运行期执行并求值。系统禁止继续让 `task_node` 假设自己必须在第一阶段补齐所有运行期结果。

#### 场景:task_node 生成规则驱动任务稿
- **当** `task_node` 处理一条规则驱动的 DM 指令
- **那么** prompt 必须说明 TaskDraft 会被后续 `dsl node` 消费
- **那么** prompt 必须说明 TaskDocument 会由 engine 在运行期执行
- **那么** agent 必须把第一阶段重点放在执行意图、状态依赖和决策结构上，而不是提前产出运行期结果

### 需求:task_node prompt 必须禁止把运行期随机结果写入 missing_info
系统必须要求 `task_node` 的 prompt 把 `missing_info` 限定为真正阻止 drafting 的前置缺口，禁止把攻击掷骰结果、伤害骰结果、豁免成败等运行期随机结果写入 `missing_info`。

#### 场景:攻击或法术的随机结果尚未产生
- **当** `task_node` 处理需要未来掷骰、未来豁免或未来伤害计算的任务
- **那么** prompt 必须说明这些结果会由 engine 在运行期产生
- **那么** agent 不得因为当前还不知道这些结果就把它们写入 `missing_info`
- **那么** agent 应继续把这些内容保留在 judgments 或执行计划中

#### 场景:真正缺失的前置信息仍应进入 missing_info
- **当** `task_node` 无法确认 exact path、规则身份、必要状态值或会改变执行形状的人类决策
- **那么** agent 仍必须把这些内容写入 `missing_info`
- **那么** prompt 不得让 agent 因为“后面还有 engine”就忽略这些真实缺口

## 修改需求

### 需求:第一阶段节点必须输出 TaskDraft 而不是受限动作分类
系统必须要求第一阶段节点输出 `TaskDraft` 一类的结构化自然语言任务稿，禁止把中间表示收窄为受限的动作类型标签作为主要输出真相。

#### 场景:task 节点生成任务稿
- **当** 第一阶段节点完成对 DM 指令的理解
- **那么** 产出的中间对象必须写明要完成什么任务
- **那么** 产出的中间对象必须写明读取哪些值、基于哪些值做什么判定以及最终写回哪些值
- **那么** 当必要信息不足时必须显式列出 `missing_info`
- **那么** `missing_info` 不得包含未来由 engine 计算的随机结果

## 移除需求
