## 新增需求

### 需求:task_node 默认 prompt 必须优先表达执行需求与证据缺口
系统必须要求 `task_node` 的默认 prompt 以执行目标、关键前提、证据缺口和安全状态绑定为主线组织 `TaskDraft`。系统禁止继续把任务原型分类、分类介绍或 few-shot 原型覆盖当作 prompt 的主要推理入口。

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

## 修改需求

### 需求:task node 与 dsl node 必须使用不同的 prompt 文件
系统必须为 `task_node` 与 `dsl_node` 使用不同的 prompt 文件，禁止两个节点默认共享同一个通用 prompt 文件。

#### 场景:节点初始化默认 prompt
- **当** `task_node` 与 `dsl_node` 初始化默认 prompt
- **那么** `task_node` 必须读取属于自己的 system prompt 文件与 user prompt 文件
- **那么** `dsl_node` 必须读取属于自己的 system prompt 文件与 user prompt 文件
- **那么** `dsl_node` 的 prompt 必须包含把 `TaskDraft` 映射到现有 engine primitive 的 lowering 原则
- **那么** `dsl_node` 的 prompt 必须解释主要 primitive 的职责与组合边界，而不是只列出受支持词表
- **那么** `dsl_node` 的 prompt 必须把 `lint` 描述为提交前可用的诊断工具，而不是唯一最终输出通道
- **那么** `dsl_node` 的 prompt 不得默认要求模型维护 `repair_mode`、`current_candidate`、固定 lint 预算这类重状态回路字段

#### 场景:dsl_node prompt 消费模板化 lint 诊断
- **当** `dsl_node` prompt 描述如何消费 `lint` 结果
- **那么** prompt 必须指导模型使用 issue 中的模板化诊断信息
- **那么** prompt 必须优先参考对应 primitive 的必填字段、允许字段和 canonical example
- **那么** prompt 必须同时结合 primitive 的运行语义理解这些诊断，而不是只把 `lint` 错误当成一条普通自然语言 message

## 移除需求
