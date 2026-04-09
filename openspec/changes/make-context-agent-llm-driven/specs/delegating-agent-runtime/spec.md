## 新增需求

## 修改需求

### 需求:Context Agent 必须通过 grep 与 search 返回高信息密度上下文包
系统必须定义一个默认的 Context Agent，并要求其在模型驱动的上下文收集循环中通过自己装配并持有的 `grep`、`search` 和 `ask` 工具组装高信息密度的结构化上下文包。系统禁止让 Context Agent 退化为只运行类内部启发式逻辑，或只返回无法稳定消费的一段自由文本摘要。

#### 场景:Context Agent 收集规则与状态上下文
- **当** 主 agent 将一条 `intent.goal.requests` 形式的事实获取任务委派给 Context Agent
- **那么** Context Agent 必须通过模型决定何时调用 `grep` 获取状态证据
- **那么** Context Agent 必须通过模型决定何时调用 `search` 获取规则证据
- **那么** 返回结果必须同时包含 `rule_evidence`、`state_evidence`、`citations` 与未决缺口或等价结构

#### 场景:Context Agent 返回结构化 ask interrupt
- **当** Context Agent 判断当前缺口已经阻止其安全 grounding
- **那么** Context Agent 必须能够返回结构化 `ask_requests` 与 `pending_interrupt`
- **那么** ask 的触发时机必须来自模型决策而不是类内部硬编码分支

#### 场景:Context Agent 返回高信息密度结果
- **当** Context Agent 完成一次上下文采集
- **那么** 返回结果必须优先保留关键规则摘录、关键状态摘录和缺口摘要
- **那么** 返回结果不得把全部价值压缩为单段概述 prose

### 需求:Context Agent 运行时必须校验模型动作并限制工具边界
系统必须把 Context Agent 设计为基于 `langchain.create_agent` 的“模型决策、agent 内执行”运行时循环。`ContextAgent` 必须校验 agent 返回的结构化动作，只允许其请求自己装配的 `grep`、`search`、`ask` 操作或返回最终 bundle；系统禁止让模型直接绕过 `ContextAgent` 的校验发起任意工具调用或直接执行副作用。

#### 场景:模型请求一次状态取证
- **当** 模型要求 Context Agent 调用 `grep`
- **那么** `ContextAgent` 必须校验该动作的类型和参数后再执行工具
- **那么** 工具结果必须被追加到后续轮次可见的证据上下文中

#### 场景:模型输出非法动作
- **当** 模型返回未声明的动作类型、缺失必要字段或非法工具名
- **那么** `ContextAgent` 必须阻止该动作被执行
- **那么** Context Agent 必须返回结构化错误或阻塞结果，而不是默默忽略该异常输出

## 移除需求
