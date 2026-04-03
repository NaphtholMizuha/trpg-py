## 新增需求

## 修改需求

### 需求:planner node 默认 prompt 必须存放在 config prompts 目录中
系统必须将 `task_node` 与 `dsl_node` 的默认提示词存放在 `config/prompts/` 目录中的独立文件里，禁止继续把完整默认 prompt 只保留为代码内联常量。

#### 场景:默认启动 task node 与 dsl node
- **当** 调用方使用默认配置创建 `task_node` 与 `dsl_node`
- **那么** 两个节点必须能够从 `config/prompts/` 下的独立 system prompt 与 user prompt 文件读取默认提示词模板
- **那么** 两个节点不得要求调用方手工传入完整 prompt 字符串才能工作
- **那么** `dsl_node` 默认 prompt 必须显式声明当前 engine 支持的 step type / kind 词表
- **那么** `dsl_node` 默认 prompt 必须显式禁止生成引擎不支持的 step type / kind 术语
- **那么** `dsl_node` 默认 prompt 必须与 `response_format=TaskDocumentSchema` 的结构化输出协议保持一致

### 需求:task node 与 dsl node 必须使用不同的 prompt 文件
系统必须为 `task_node` 与 `dsl_node` 使用不同的 prompt 文件，禁止两个节点默认共享同一个通用 prompt 文件。

#### 场景:节点初始化默认 prompt
- **当** `task_node` 与 `dsl_node` 初始化默认 prompt
- **那么** `task_node` 必须读取属于自己的 system prompt 文件与 user prompt 文件
- **那么** `dsl_node` 必须读取属于自己的 system prompt 文件与 user prompt 文件
- **那么** `dsl_node` 的 prompt 必须包含把 `TaskDraft` 映射到现有 engine primitive 的 translation rules 或等价 few-shot
- **那么** `dsl_node` 的 prompt 必须把 `lint` 描述为提交前可用的诊断工具，而不是唯一最终输出通道
- **那么** `dsl_node` 的 prompt 不得默认要求模型维护 `repair_mode`、`current_candidate`、固定 lint 预算这类重状态回路字段

## 移除需求
