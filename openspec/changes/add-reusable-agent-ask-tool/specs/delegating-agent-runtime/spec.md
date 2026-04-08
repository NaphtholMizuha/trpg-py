## 新增需求

## 修改需求

### 需求:Context Agent 必须通过工具返回高信息密度上下文包与结构化 ask_requests
系统必须定义一个默认的 Context Agent，并要求其默认工具集包含 `grep`、`search` 与可复用的 `ask`。Context Agent 必须返回高信息密度的结构化上下文包，覆盖规则证据、状态证据、来源定位以及在适合时生成的结构化 `ask_requests`；系统禁止让其只返回无法稳定消费的一段自由文本摘要，也禁止继续把面向 DM 的澄清需求放在普通文本缺口里作为主返回承载。

#### 场景:Context Agent 收集规则与状态上下文
- **当** 主 agent 将一项包含 `intent`、`goal`、`requests` 的事实获取任务委派给 Context Agent
- **那么** Context Agent 必须能够调用 `grep` 获取状态证据
- **那么** Context Agent 必须能够调用 `search` 获取规则证据
- **那么** 在适合的歧义场景下 Context Agent 必须能够调用 `ask` 生成结构化澄清请求
- **那么** 返回结果必须同时包含 `rule_evidence`、`state_evidence`、`citations` 与 `ask_requests` 或等价结构

#### 场景:Context Agent 把可明确提问的缺口升级为 ask_requests
- **当** Context Agent 已经把歧义或缺失收敛成有限候选或明确的人类确认点
- **那么** Context Agent 必须优先生成 ask 请求，而不是只输出模糊问题文本
- **那么** ask 请求必须保留候选项、默认值和自定义输入入口

#### 场景:Context Agent 不再把面向 DM 的问题作为普通缺口主返回
- **当** Context Agent 已经能够把某个缺口组织成明确 ask 请求
- **那么** 该问题必须进入 `ask_requests` 或等价结构
- **那么** 该问题不得继续作为普通 `unresolved_gaps` 一类的上层返回字段主路径存在

#### 场景:Context Agent 通过工具自行获取材料
- **当** 主 agent 将事实获取任务委派给 Context Agent
- **那么** Context Agent 必须通过其默认工具边界自行获取状态和规则材料
- **那么** 调用方不得再依赖把 `state` 或通用 `context` 作为长期必备输入字段传递给 Context Agent

## 移除需求
