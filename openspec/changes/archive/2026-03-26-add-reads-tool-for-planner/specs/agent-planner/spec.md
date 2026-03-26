## 新增需求

### 需求:planner 必须能够使用 reads 补充状态值证据
系统必须允许 planner 在已知或可发现候选路径的前提下使用 `reads` 工具读取当前状态值，以确认实体 ID、AC、资源或其他关键参数，禁止在 state 已经包含答案时仅因无法读取值而直接进入 HITL。

#### 场景:planner 通过 reads 确认目标实体与关键数值
- **当** planner 已通过 `fetch_keys` 找到候选状态路径但仍需确认具体值
- **那么** planner 可以调用 `reads` 读取这些路径上的当前值
- **那么** planner 可以根据读取结果确认 actor_id、target_id 或其他关键任务参数
- **那么** 若读取结果已足够支撑规划，planner 不得仅因“未人工澄清”而进入 `needs_human`

## 修改需求

### 需求:planner 必须通过 search 和 fetch_keys 获取证据
planner 必须将 `search` 与 `fetch_keys` 作为基础信息工具，并通过工具调用结果驱动后续推理分支。对于需要读取具体状态值的场景，planner 必须能够进一步使用 `reads` 工具补充值证据，但 `reads` 不得替代 `search` 的规则检索职责或 `fetch_keys` 的路径发现职责。

#### 场景:planner 使用 search 补充规则证据
- **当** DM 指令涉及规则判断（如攻击、豁免、伤害）
- **那么** planner 可以调用 `search` 检索规则原文
- **那么** 规则结论建立在检索证据之上

#### 场景:planner 使用 fetch_keys 补充状态路径证据
- **当** planner 需要引用状态路径生成步骤参数
- **那么** planner 可以调用 `fetch_keys` 枚举候选路径
- **那么** 产出的路径引用与 state 点路径语义保持一致

#### 场景:planner 使用 reads 确认候选路径上的当前值
- **当** planner 已找到候选路径但仍需确认具体值
- **那么** planner 可以调用 `reads` 读取这些路径对应的当前值
- **那么** `reads` 的结果只用于补充状态值证据，不得被伪装成规则原文或执行结果
