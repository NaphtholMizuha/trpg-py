## 新增需求

## 修改需求

### 需求:Context Agent 必须通过 grep 与 search 返回高信息密度上下文包
系统必须定义一个默认的 Context Agent，并要求其默认工具集仅包含 `grep` 与 `search`。Context Agent 必须返回高信息密度的结构化上下文包，覆盖规则证据、状态证据、来源定位和未决缺口；系统禁止让其只返回无法稳定消费的一段自由文本摘要。主 agent 默认委派给 Context Agent 的输入必须以 `intent`、`goal`、`requests` 为中心组织，其中 `requests` 必须是自然语言描述的事实获取请求；系统禁止继续把 `instruction`、`state`、`context` 作为长期默认委派输入真相。

#### 场景:Context Agent 收集规则与状态上下文
- **当** 主 agent 将一项包含 `intent`、`goal`、`requests` 的事实获取任务委派给 Context Agent
- **那么** Context Agent 必须能够调用 `grep` 获取状态证据
- **那么** ContextAgent 必须能够调用 `search` 获取规则证据
- **那么** 返回结果必须同时包含 `rule_evidence`、`state_evidence`、`citations` 与 `unresolved_gaps` 或等价结构

#### 场景:Context Agent 返回高信息密度结果
- **当** Context Agent 完成一次上下文采集
- **那么** 返回结果必须优先保留关键规则摘录、关键状态摘录和缺口摘要
- **那么** 返回结果不得把全部价值压缩为单段概述 prose

#### 场景:Context Agent 通过工具自行获取材料
- **当** 主 agent 将事实获取任务委派给 Context Agent
- **那么** Context Agent 必须通过其默认工具边界自行获取状态和规则材料
- **那么** 调用方不得再依赖把 `state` 或通用 `context` 作为长期必备输入字段传递给 Context Agent

## 移除需求
