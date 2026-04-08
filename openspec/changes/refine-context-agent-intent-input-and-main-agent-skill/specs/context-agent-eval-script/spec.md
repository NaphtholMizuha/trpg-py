## 新增需求

## 修改需求

### 需求:Context Agent eval 脚本输入必须复用主 agent 的默认委派 payload
系统必须让 Context Agent eval 脚本直接复用主 agent 委派给 Context Agent 的默认 payload 结构，并以 `intent`、`goal`、`requests` 作为长期输入契约。系统禁止继续维护以 `instruction`、`state`、`context` 为中心的旧输入协议，也禁止把 `requests` 退化为字段名列表或问句列表。

#### 场景:脚本构造默认输入
- **当** 开发者运行 Context Agent eval 脚本并提供一条用户原始意图
- **那么** 脚本必须构造与主 agent 委派 Context Agent 时相同语义的 `intent`、`goal`、`requests` payload
- **那么** 该 payload 必须可被 Context Agent 直接消费而无需二次适配

### 需求:Context Agent eval 脚本必须展示新的委派任务输入
系统必须让 Context Agent eval 脚本在输出中清晰展示主 agent 发给 Context Agent 的 `intent`、`goal`、`requests` 输入，便于开发者观察事实获取任务是否被正确构造。系统禁止只展示 bundle 而隐藏新的委派输入。

#### 场景:脚本展示事实获取任务
- **当** Context Agent eval 脚本完成一次调用
- **那么** 调用方必须能直接看见 `intent`
- **那么** 调用方必须能直接看见 `goal`
- **那么** 调用方必须能直接看见 `requests`

### 需求:Context Agent eval 测试必须覆盖新输入契约
系统必须为 Context Agent eval 脚本和 helper 提供自动测试，覆盖新 payload 的构造、展示和请求语义。系统禁止只验证 bundle 字段而不验证 `intent.goal.requests` 契约。

#### 场景:自动测试验证 payload 构造
- **当** 自动测试执行 Context Agent eval helper 或脚本相关逻辑
- **那么** 测试必须断言 payload 使用 `intent`、`goal`、`requests`
- **那么** 测试必须断言 `requests` 是自然语言事实获取请求

## 移除需求

### 需求:Context Agent eval 脚本必须支持默认 fixture state 与显式覆盖
**Reason**: Context Agent 的长期输入契约不再要求 `state` 作为委派 payload 的一部分。
**Migration**: 若仍需切换 fixture 或运行态状态来源，应通过 Context Agent 工具装配或运行时依赖注入完成，而不是继续把 `state` 放进长期 payload 契约。
