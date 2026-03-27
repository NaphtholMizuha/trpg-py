## 新增需求

### 需求:planner 必须能够利用 no_match 建议路径继续收敛状态证据
系统必须允许 planner 在 `list` 或 `read` 返回 `status=no_match` 且包含建议路径时，把这些建议当作后续状态取证线索；禁止 planner 在已经拿到可用建议后仍机械地重复同一失败路径请求。

#### 场景:planner 根据建议路径修正状态取证
- **当** planner 调用 `list` 或 `read` 返回 `status=no_match` 且包含建议路径
- **那么** planner 可以改用建议路径或建议前缀继续取证
- **那么** 若建议已足够支撑后续读取或规划，planner 不得重复同一失败请求

## 修改需求

### 需求:planner 必须通过 search 和 fetch_keys 获取证据
planner 必须将 `search` 与 `list` 作为基础信息工具，并通过工具调用结果驱动后续推理分支。对于需要读取具体状态值的场景，planner 必须能够进一步使用 `read` 工具补充值证据。对于候选 `TaskDocument` 的合法性收口，planner 必须能够进一步使用 `lint` 工具执行只读自检，但 `lint` 不得替代 `search`、`list` 与 `read` 的取证职责。

#### 场景:planner 使用 search 补充规则证据
- **当** DM 指令涉及规则判断（如攻击、豁免、伤害）
- **那么** planner 可以调用 `search` 检索规则原文
- **那么** 规则结论建立在检索证据之上

#### 场景:planner 使用 list 补充状态路径证据
- **当** planner 需要引用状态路径生成步骤参数
- **那么** planner 可以调用 `list` 枚举候选路径
- **那么** 产出的路径引用与 state 点路径语义保持一致

#### 场景:planner 使用 read 补充状态值证据
- **当** planner 已知或可发现候选状态路径但仍需确认具体值
- **那么** planner 可以调用 `read` 读取这些路径上的当前值
- **那么** planner 可以根据读取结果确认 actor_id、target_id、AC、资源或其他关键任务参数

#### 场景:planner 使用 lint 收口候选文档
- **当** planner 已具备足够规则证据和状态路径证据并准备返回 `ready`
- **那么** planner 可以调用 `lint` 对候选 `TaskDocument` 做只读合法性校验
- **那么** `lint` 的结果只用于校验候选文档，不得被当作规则证据或状态事实来源

### 需求:planner 必须在提问前优先完成可用工具取证
系统必须要求 planner 在触发 HITL 之前尽可能完成 `search`、`list` 与必要的 `read` 取证尝试，避免因未检索、未枚举路径或未读取关键值造成过早提问。

#### 场景:先取证后提问
- **当** DM 指令初看存在歧义
- **当** 工具取证后仍无法收敛到单一可执行方案
- **那么** planner 才触发 `needs_human`
- **那么** 提问内容基于已获取证据而非泛化追问

### 需求:planner 必须基于 create_agent runtime 实现
系统必须基于 LangChain 的 `create_agent()`/LangGraph agent runtime 实现 planner 主流程，禁止继续要求 planner 默认依赖 `deepagents.create_deep_agent()` 及其通用 coding-agent 默认 prompt/middleware 栈。planner 仍然必须能够在同一运行流中消费 `search`、`list`、`read` 与 `lint`，并输出结构化结果。

#### 场景:调用方通过 create_agent planner 执行规划
- **当** 调用方创建并运行 planner
- **那么** planner 默认由 `langchain.agents.create_agent()` 创建运行图
- **那么** planner 不再要求加载 deep agent 默认的待办清单、文件系统、子代理或补丁工具中间件
- **那么** planner 仍可在同一运行流中消费 `search`、`list`、`read` 与 `lint`
- **那么** planner 仍输出结构化 `PlannerResult`

### 需求:planner 依赖的工具调用必须可通过运行期日志观察
系统必须确保 planner 所依赖的工具调用在运行期可观察，禁止让调用方只能依赖最终 `ready/needs_human/blocked` 结果反推中间工具输入输出。

#### 场景:planner 调用 search、list 或 read 时留下工具日志
- **当** planner 在一次规划过程中调用 `search`、`list` 或 `read`
- **那么** 运行期日志中必须可见该工具调用的输入参数摘要
- **那么** 运行期日志中必须可见该工具调用的输出状态或错误结果
- **那么** 调用方无需修改 planner 业务逻辑即可观察这些日志

### 需求:planner 必须能够使用 reads 补充状态值证据
系统必须允许 planner 在已知或可发现候选路径的前提下使用 `read` 工具读取当前状态值，以确认实体 ID、AC、资源或其他关键参数，禁止在 state 已经包含答案时仅因无法读取值而直接进入 HITL。

#### 场景:planner 通过 read 确认目标实体与关键数值
- **当** planner 已通过 `list` 找到候选状态路径但仍需确认具体值
- **那么** planner 可以调用 `read` 读取这些路径上的当前值
- **那么** planner 可以根据读取结果确认 actor_id、target_id 或其他关键任务参数
- **那么** 若读取结果已足够支撑规划，planner 不得仅因“未人工澄清”而进入 `needs_human`

## 移除需求
