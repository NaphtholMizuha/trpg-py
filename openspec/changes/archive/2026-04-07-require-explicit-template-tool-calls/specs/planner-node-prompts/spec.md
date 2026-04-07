## 新增需求

## 修改需求

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
- **那么** `dsl_node` 默认 prompt 必须指导模型优先通过 `template` 工具获取合法 DSL 骨架，而不是只从 prompt 中回忆模板
- **那么** `dsl_node` 默认 prompt 不得依赖宿主注入的 `template_lookup` 或 `template_query_hint` 作为默认工作流前提

### 需求:task node 与 dsl node 必须使用不同的 prompt 文件
系统必须为 `task_node` 与 `dsl_node` 使用不同的 prompt 文件，禁止两个节点默认共享同一个通用 prompt 文件。

#### 场景:节点初始化默认 prompt
- **当** `task_node` 与 `dsl_node` 初始化默认 prompt
- **那么** `task_node` 必须读取属于自己的 system prompt 文件与 user prompt 文件
- **那么** `dsl_node` 必须读取属于自己的 system prompt 文件与 user prompt 文件
- **那么** `dsl_node` 的 prompt 必须包含把 `TaskDraft` 映射到现有 engine primitive 的 translation rules 或等价 few-shot
- **那么** `dsl_node` 的 prompt 必须把 `lint` 描述为提交前可用的诊断工具，而不是唯一最终输出通道
- **那么** `dsl_node` 的 prompt 必须把 `template` 描述为按需查询合法骨架的工具
- **那么** `dsl_node` 的 prompt 不得默认要求模型在 prompt 内背诵完整 DSL 模板手册

#### 场景:dsl_node prompt 调用 template 工具
- **当** `dsl_node` prompt 指导模型生成候选 `TaskDocument`
- **那么** prompt 必须要求模型先根据 `task_node` 已使用的任务原型识别当前任务族
- **那么** prompt 必须要求模型使用少量受控枚举字段调用 `template` 工具
- **那么** prompt 必须禁止模型自由发明模板签名字符串
- **那么** prompt 必须指导模型根据 `template` 返回的 `required_bindings` 和 `binding_rules` 填充实例参数
- **那么** prompt 不得把宿主预取好的模板结果当作默认输入字段直接提供给模型

#### 场景:dsl_node prompt 处理 template 工具未完全命中
- **当** `dsl_node` 无法安全细分全部二级字段
- **那么** prompt 必须允许模型使用 `unknown` 或等价保守值查询模板
- **那么** prompt 不得要求模型为了命中模板而瞎编更细的签名

## 移除需求
