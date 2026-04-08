## 新增需求

### 需求:系统必须提供 Context Agent 的专用 eval 脚本
系统必须提供一个专门面向 Context Agent 的可手动运行 eval 脚本，并将其作为长期保留的结构化评测入口。系统禁止要求开发者只能通过自动测试断言或完整 planner 流程间接观察 Context Agent 行为。

#### 场景:开发者手动运行 Context Agent eval 脚本
- **当** 开发者运行 Context Agent eval 脚本且未额外覆盖输入
- **那么** 脚本必须直接调用 Context Agent 完成一次真实 bundle 生成
- **那么** 脚本必须展示本次调用返回的真实 `ContextBundle`

### 需求:Context Agent eval 脚本输入必须复用主 agent 的默认委派 payload
系统必须让 Context Agent eval 脚本直接复用主 agent 委派给 Context Agent 的默认 payload 结构，至少包含 `instruction`、`state` 和 `context` 或等价字段。系统禁止维护一套只供 eval 脚本使用的专用输入协议。

#### 场景:脚本构造默认输入
- **当** 开发者运行 Context Agent eval 脚本并提供一条 instruction
- **那么** 脚本必须构造与主 agent 委派 Context Agent 时相同语义的 payload
- **那么** 该 payload 必须可被 Context Agent 直接消费而无需二次适配

### 需求:Context Agent eval 脚本必须展示高信息密度 bundle 字段
系统必须让 Context Agent eval 脚本以人类可读方式展示 `ContextBundle` 的关键字段，至少包括 `status`、`instruction`、`normalized_instruction`、`action`、`resolved_entities`、`rule_evidence`、`state_evidence`、`citations`、`unresolved_gaps` 和 `notes`。系统禁止只打印笼统的成功失败摘要。

#### 场景:脚本展示 bundle 摘要
- **当** Context Agent eval 脚本完成一次调用
- **那么** 调用方必须能直接看见 bundle 的状态类型
- **那么** 调用方必须能直接看见关键规则证据、状态证据和未决缺口
- **那么** 调用方无需额外打开调试器才能理解这次上下文采集结果

### 需求:Context Agent eval 脚本必须支持完整 bundle 输出
系统必须让 Context Agent eval 脚本支持输出完整 bundle，以便开发者复制、比对或留档。系统禁止把结构化 bundle 永久压缩成不可还原的人类摘要文本。

#### 场景:开发者请求完整输出
- **当** 开发者以完整输出模式运行 Context Agent eval 脚本
- **那么** 脚本必须输出完整的结构化 bundle
- **那么** 输出内容必须能够覆盖默认摘要视图中未展示的字段细节

### 需求:Context Agent eval 脚本必须支持默认 fixture state 与显式覆盖
系统必须让 Context Agent eval 脚本默认加载仓库内版本化维护的 world state fixture，并允许调用方显式覆盖 state 文件路径。系统禁止继续把极简内联 state 当作长期默认真相。

#### 场景:脚本使用默认状态夹具
- **当** 开发者直接运行 Context Agent eval 脚本且未传入 state 文件
- **那么** 脚本必须加载仓库内版本化维护的默认 world state fixture
- **那么** 该 fixture 必须可直接用于构造 Context Agent payload

#### 场景:脚本覆盖状态文件
- **当** 开发者为 Context Agent eval 脚本显式传入 state 文件路径
- **那么** 脚本必须使用该文件构造 payload 中的 `state`
- **那么** 脚本不得继续强制使用内置默认状态

## 修改需求

## 移除需求
