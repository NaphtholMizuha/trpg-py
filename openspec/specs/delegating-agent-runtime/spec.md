# delegating-agent-runtime 规范

## 目的
待定 - 由归档变更 replace-planner-with-delegating-agents 创建。归档后请更新目的。
## 需求
### 需求:主 agent 必须作为唯一长期编排真相
系统必须以一个主 agent 作为 planner 的唯一长期编排真相，并通过工具调用完成能力发现、能力装配和子 agent 委派。系统禁止继续把固定的双节点 workflow 作为默认编排真相。

#### 场景:调用方发起一次规划请求
- **当** 调用方向新的 planner 入口提交 instruction 与 state
- **那么** 主 agent 必须成为接收该请求的第一执行单元
- **那么** 主 agent 必须通过工具调用决定需要哪些能力和子 agent
- **那么** 调用方不得再被要求直接装配 `task_node`、`dsl_node` 或等价的固定阶段节点

### 需求:主 agent 必须默认提供 list_skills、load_skills 与 delegate 三个工具
系统必须为主 agent 默认提供 `list_skills`、`load_skills` 和 `delegate` 三个工具，并把它们视为能力发现与委派的基础接口。系统禁止要求主 agent 依赖隐藏的 Python 装配逻辑才能得知可用能力。

#### 场景:主 agent 查询可用能力
- **当** 主 agent 需要判断当前可调用哪些子能力
- **那么** 它必须能够调用 `list_skills`
- **那么** 返回结果必须可区分可直接加载的能力项

#### 场景:主 agent 装配某项能力
- **当** 主 agent 确定需要某项能力或子 agent profile
- **那么** 它必须能够调用 `load_skills`
- **那么** 装配结果必须可被后续 `delegate` 调用消费

#### 场景:主 agent 委派子任务
- **当** 主 agent 决定把子任务交给某个已装配的子 agent
- **那么** 它必须能够调用 `delegate`
- **那么** `delegate` 必须接受目标子 agent 标识与结构化输入
- **那么** `delegate` 不得退化为简单字符串拼接或隐藏的内部函数调用

### 需求:Context Agent 必须通过 grep 与 search 返回高信息密度上下文包
系统必须定义一个默认的 Context Agent，并要求其默认工具集仅包含 `grep` 与 `search`。Context Agent 必须返回高信息密度的结构化上下文包，覆盖规则证据、状态证据、来源定位和未决缺口；系统禁止让其只返回无法稳定消费的一段自由文本摘要。

#### 场景:Context Agent 收集规则与状态上下文
- **当** 主 agent 将一条 instruction 与当前 state 委派给 Context Agent
- **那么** Context Agent 必须能够调用 `grep` 获取状态证据
- **那么** Context Agent 必须能够调用 `search` 获取规则证据
- **那么** 返回结果必须同时包含 `rule_evidence`、`state_evidence`、`citations` 与 `unresolved_gaps` 或等价结构

#### 场景:Context Agent 返回高信息密度结果
- **当** Context Agent 完成一次上下文采集
- **那么** 返回结果必须优先保留关键规则摘录、关键状态摘录和缺口摘要
- **那么** 返回结果不得把全部价值压缩为单段概述 prose

### 需求:Resolution Agent 必须通过 lint 与 execute 返回结构化求解结果
系统必须定义一个默认的 Resolution Agent，并要求其默认工具集仅包含 `lint` 与 `execute`。Resolution Agent 必须以结构化方式返回 lint 结论、执行报告、状态变化和阻塞原因；系统禁止把最终结果折叠为无细节的成功或失败字符串。

#### 场景:Resolution Agent 处理可执行任务
- **当** 主 agent 将 instruction 与 Context Agent 返回的上下文包委派给 Resolution Agent
- **那么** Resolution Agent 必须能够调用 `lint`
- **那么** Resolution Agent 必须能够在通过校验后调用 `execute`
- **那么** 返回结果必须包含 `lint_result`、`execution_report` 与 `state_changes` 或等价结构

#### 场景:Resolution Agent 因校验或缺口阻塞
- **当** Resolution Agent 无法安全完成校验或执行
- **那么** 返回结果必须明确标记阻塞状态
- **那么** 返回结果必须保留结构化的 `blocked_reasons`、`lint_result` 或等价诊断信息

