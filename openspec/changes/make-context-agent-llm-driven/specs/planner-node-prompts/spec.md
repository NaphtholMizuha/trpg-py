## 新增需求

## 修改需求

### 需求:planner node 默认 prompt 必须存放在 config prompts 目录中
系统必须将主 planner、Context Agent 与 Resolution Agent 的默认提示词存放在 `config/prompts/` 目录中的独立文件里，并要求运行时真实读取这些模板参与对应 agent 推理。系统禁止继续把 context-agent prompt 仅保留在配置文件和测试夹具中而不接入真实执行链路。

#### 场景:默认启动 Context Agent
- **当** 调用方使用默认配置创建 planner 并委派 Context Agent
- **那么** Context Agent 必须能够从 `config/prompts/` 下读取自己的 system prompt 与 user prompt 文件
- **那么** 这些 prompt 必须被渲染为真实模型请求的一部分
- **那么** 调用方不得手工拼接完整 prompt 字符串才能让 Context Agent 工作

#### 场景:测试覆写 Context Agent prompt
- **当** 调用方或测试为 Context Agent 显式提供 prompt 字符串
- **那么** Context Agent 必须优先使用显式提供的 prompt
- **那么** 运行时不得继续读取并覆盖该显式值

### 需求:Context Agent user prompt 必须描述可用工具与结构化动作格式
系统必须要求 Context Agent 的 user prompt 明确描述当前事实获取任务、已收集证据、可用工具和允许输出的结构化动作格式。系统禁止继续让 Context Agent prompt 只给出泛化目标，而不说明模型如何请求取证、ask 或完成。

#### 场景:Context Agent 基于中间证据继续多轮取证
- **当** Context Agent 已经拿到部分 `grep` 或 `search` 证据但仍未完成 grounding
- **那么** user prompt 必须让模型看到这些中间证据摘要
- **那么** user prompt 必须说明模型可以继续请求取证、发起 ask 或结束

#### 场景:Context Agent 生成 ask request
- **当** 模型判断需要向 DM 发起 ask
- **那么** prompt 必须指导模型返回结构化的 `question_id`、`prompt`、`options`、默认值和自定义输入约束或等价字段
- **那么** prompt 不得只让模型输出无法稳定解析的自然语言提问段落

## 移除需求
