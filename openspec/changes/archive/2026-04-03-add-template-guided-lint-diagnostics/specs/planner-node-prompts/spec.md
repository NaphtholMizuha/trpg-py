## 新增需求

## 修改需求

### 需求:planner node 默认 prompt 必须存放在 config prompts 目录中
系统必须将 `task_node` 与 `dsl_node` 的默认提示词存放在 `config/prompts/` 目录中的独立文件里，禁止继续把完整默认 prompt 只保留为代码内联常量。

#### 场景:默认启动 task node 与 dsl node
- **当** 调用方使用默认配置创建 `task_node` 与 `dsl_node`
- **那么** 两个节点必须能够从 `config/prompts/` 下的独立 system prompt 与 user prompt 文件读取默认提示词模板
- **那么** 两个节点不得要求调用方手工传入完整 prompt 字符串才能工作
- **那么** `dsl_node` 默认 prompt 必须显式声明最终目标是返回 `lint valid` 的 `TaskDocument`

### 需求:task node 与 dsl node 必须使用不同的 prompt 文件
系统必须为 `task_node` 与 `dsl_node` 使用不同的 prompt 文件，禁止两个节点默认共享同一个通用 prompt 文件。

#### 场景:dsl_node prompt 消费模板化 lint 诊断
- **当** `dsl_node` prompt 描述如何消费 `lint` 结果
- **那么** prompt 必须指导模型使用 issue 中的模板化诊断信息
- **那么** prompt 必须优先参考对应 primitive 的必填字段、允许字段和 canonical example
- **那么** prompt 不得只把 `lint` 错误当成一条普通自然语言 message

## 移除需求
