## 新增需求

### 需求:主 agent 的默认指引必须教会其如何使用 Context Agent
系统必须为主 agent 或其等价默认指引提供明确约束，教会它在调用 Context Agent 之前先构造事实获取任务。系统禁止继续让主 agent 仅凭原始用户句子和隐式实现细节来决定 Context Agent 的输入形状。

#### 场景:主 agent 构造 Context Agent 委派输入
- **当** 主 agent 决定需要 Context Agent 收集上下文
- **那么** 默认指引必须要求主 agent 保留用户原始意图为 `intent`
- **那么** 默认指引必须要求主 agent 生成描述上下文采集目的的 `goal`
- **那么** 默认指引必须要求主 agent 生成自然语言事实获取请求 `requests`

## 修改需求

## 移除需求
