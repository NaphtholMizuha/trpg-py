# planner-node-prompts 规范

## 目的
待定 - 由归档变更 extract-planner-node-prompts-to-config 创建。归档后请更新目的。
## 需求
### 需求:planner node 默认 prompt 必须存放在 config prompts 目录中
系统必须将 `task_node` 与 `dsl_node` 的默认提示词存放在 `config/prompts/` 目录中的独立文件里，禁止继续把完整默认 prompt 只保留为代码内联常量。

#### 场景:默认启动 task node 与 dsl node
- **当** 调用方使用默认配置创建 `task_node` 与 `dsl_node`
- **那么** 两个节点必须能够从 `config/prompts/` 下的独立 system prompt 与 user prompt 文件读取默认提示词模板
- **那么** 两个节点不得要求调用方手工传入完整 prompt 字符串才能工作
- **那么** `dsl_node` 默认 prompt 必须显式声明最终目标是返回 `lint valid` 的 `TaskDocument`
- **那么** `dsl_node` 默认 prompt 必须显式声明当前 engine 支持的 step type / kind 词表
- **那么** `dsl_node` 默认 prompt 必须显式禁止生成引擎不支持的 step type / kind 术语
- **那么** `dsl_node` 默认 prompt 必须明确要求在最终输出前使用 `lint` 检查 candidate
- **那么** `dsl_node` 默认 prompt 必须明确要求 `lint` 返回 `invalid` 时继续依据问题诊断修正 candidate

### 需求:task_node 默认 prompt 必须优先表达执行需求与证据缺口
系统必须要求 `task_node` 的默认 prompt 以执行目标、关键前提、证据缺口和安全状态绑定为主线组织 `TaskDraft`。系统禁止继续把任务原型分类、分类介绍或固定 few-shot 覆盖当作 prompt 的主要推理入口。

#### 场景:task_node 处理混合或边界案例任务
- **当** `task_node` 处理同时包含规则理解、状态发现、范围判定或资源绑定的任务
- **那么** prompt 必须优先引导模型识别要执行什么、依赖哪些前提、哪些路径可安全绑定
- **那么** prompt 不得要求模型先把任务硬塞进某个固定任务原型再开始取证
- **那么** prompt 必须要求证据不足的部分进入 `missing_info` 或 `assumptions`，而不是被类别标签掩盖

#### 场景:task_node prompt 使用 few-shot
- **当** `task_node` prompt 仍然使用 few-shot
- **那么** few-shot 的角色必须是示范取证原则、缺口暴露和任务稿取舍
- **那么** few-shot 不得再以“覆盖所有任务类型原型”作为主要目标
- **那么** few-shot 不得让模型把示例类别当作最终答案模板

### 需求:task node 与 dsl node 必须使用不同的 prompt 文件
系统必须为 `task_node` 与 `dsl_node` 使用不同的 prompt 文件，禁止两个节点默认共享同一个通用 prompt 文件。

#### 场景:节点初始化默认 prompt
- **当** `task_node` 与 `dsl_node` 初始化默认 prompt
- **那么** `task_node` 必须读取属于自己的 system prompt 文件与 user prompt 文件
- **那么** `dsl_node` 必须读取属于自己的 system prompt 文件与 user prompt 文件

#### 场景:dsl_node prompt 消费模板化 lint 诊断
- **当** `dsl_node` prompt 描述如何消费 `lint` 结果
- **那么** prompt 必须指导模型使用 issue 中的模板化诊断信息
- **那么** prompt 必须优先参考对应 primitive 的必填字段、允许字段和 canonical example
- **那么** prompt 不得只把 `lint` 错误当成一条普通自然语言 message

#### 场景:节点初始化默认 prompt
- **当** `task_node` 与 `dsl_node` 初始化默认 prompt
- **那么** `task_node` 必须读取属于自己的 system prompt 文件与 user prompt 文件
- **那么** `dsl_node` 必须读取属于自己的 system prompt 文件与 user prompt 文件
- **那么** `dsl_node` 的 prompt 必须包含把 `TaskDraft` 映射到现有 engine primitive 的 lowering 原则或等价示例
- **那么** `dsl_node` 的 prompt 必须解释主要 primitive 的职责与组合边界，而不是只列出受支持词表
- **那么** `dsl_node` 的 prompt 必须把 `lint` 描述为提交前可用的诊断工具，而不是唯一最终输出通道
- **那么** `dsl_node` 的 prompt 不得默认要求模型维护 `repair_mode`、`current_candidate`、固定 lint 预算这类重状态回路字段

### 需求:dsl_node 默认 prompt 必须解释 engine primitive 的运行语义与组合边界
系统必须要求 `dsl_node` 的默认 prompt 明确解释 engine 中各类 primitive 的职责、关键输入输出语义、常见连接关系和适用边界。系统禁止继续让 `dsl_node` 只把 engine primitive 视为模板槽位或少量任务族的机械填空目标。

#### 场景:dsl_node 从 TaskDraft lower 到 TaskDocument
- **当** `dsl_node` 读取 `TaskDraft` 并准备生成 `TaskDocument`
- **那么** prompt 必须帮助模型理解 `select`、`check`、`damage`、`heal`、`resource`、`effect`、`state` 各自承担什么运行职责
- **那么** prompt 必须说明这些 primitive 在结果流和状态写回中的典型连接方式
- **那么** prompt 必须允许模型在当前 engine 支持的 DSL 词表内自由合理地组合这些 primitive

#### 场景:dsl_node 使用 template 与 lint
- **当** `dsl_node` 使用 `template` 或 `lint`
- **那么** prompt 必须把 `template` 描述为合法 shape 与常见骨架的参考工具
- **那么** prompt 必须把 `lint` 描述为提交前诊断与收敛工具
- **那么** prompt 不得暗示只有模板命中的固定任务族才允许组合 engine primitive

#### 场景:dsl_node prompt 处理 lint invalid 结果
- **当** `dsl_node` prompt 描述如何消费 `lint` 结果
- **那么** prompt 必须明确指出 `lint` 返回 `invalid` 时，该 candidate 不是理想最终答案
- **那么** prompt 必须指导模型优先依据 `lint` 返回的错误与模板化诊断调整 candidate
- **那么** prompt 必须指导模型继续调用 `lint` 检查修正后的 candidate，直到结果为 `valid` 或工具预算耗尽
- **那么** prompt 不得把 `lint` 仅描述成可有可无的普通参考工具

### 需求:config.toml 必须为两个 node 单独声明 prompt 文件名
系统必须在 `config/config.toml` 中为 `task_node` 与 `dsl_node` 分别声明 prompt 文件名配置，禁止只依赖代码约定猜测文件名。

#### 场景:节点解析默认 prompt 配置
- **当** `task_node` 或 `dsl_node` 需要加载默认 prompt
- **那么** 节点必须通过 `config/config.toml` 中属于自己的 prompt 配置节解析 `system_file` 与 `user_file`
- **那么** 节点不得把文件名只写死在代码里作为唯一真相

### 需求:显式传入的 prompt 必须覆盖文件默认值
系统必须允许调用方在 node 依赖或初始化参数中显式传入 prompt 文本，并且该值必须覆盖配置文件中的默认 prompt 内容。

#### 场景:测试覆写 task node prompt
- **当** 调用方为 `task_node` 或 `dsl_node` 显式提供 prompt 字符串
- **那么** 节点必须优先使用显式提供的 prompt
- **那么** 节点不得继续读取并覆盖该显式值
