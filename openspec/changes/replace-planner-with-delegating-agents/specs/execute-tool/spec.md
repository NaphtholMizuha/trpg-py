## 新增需求

### 需求:execute 工具必须驻留在 augury.agent.tools 命名空间
系统必须在 `augury.agent.tools` 命名空间下提供名为 `execute` 的工具能力，并允许 agent 与 Python 调用方直接复用。系统禁止要求 Resolution Agent 直接依赖 engine 内部模块路径完成执行。

#### 场景:调用方装配 Resolution Agent 工具集
- **当** 开发者或运行时需要为 Resolution Agent 装配执行能力
- **那么** 可以从 `augury.agent.tools` 获取 `execute` 工具实现
- **那么** 调用方不需要手工拼装 engine 执行与结果整形逻辑

### 需求:execute 工具必须复用现有 engine 执行链路
系统必须让 `execute` 工具复用现有 TaskDocument 校验与 engine 执行链路，禁止维护一套与 engine 真正行为不一致的并行执行器。

#### 场景:Resolution Agent 提交候选任务文档
- **当** 调用方向 `execute` 提交一个候选 `TaskDocument` 与当前 state
- **那么** 工具必须复用现有 engine 的校验与执行语义
- **那么** 返回结果必须与直接调用 engine 的行为保持一致

### 需求:execute 工具必须结构化返回执行报告与状态变化
系统必须让 `execute` 工具返回结构化的执行结果，至少包含执行状态、执行报告和状态变化摘要。系统禁止只返回一段不可分解的自然语言消息。

#### 场景:execute 成功执行任务
- **当** `execute` 成功执行一份合法的 `TaskDocument`
- **那么** 返回结果必须包含 `status`
- **那么** 返回结果必须包含完整的 `execution_report` 或等价执行明细
- **那么** 返回结果必须包含 `state_changes` 或等价的状态变化摘要

#### 场景:execute 遇到校验失败或运行失败
- **当** `execute` 在校验阶段或运行阶段失败
- **那么** 返回结果必须明确区分失败类型
- **那么** 返回结果必须保留结构化错误信息，而不是只输出控制台异常文本

### 需求:execute 工具必须记录输入输出摘要
系统必须要求 `execute` 工具在每次调用时记录输入输出摘要，便于定位执行阶段故障。系统禁止把可观察性责任完全留给上层 agent。

#### 场景:execute 完成一次调用
- **当** `execute` 完成一次成功或失败调用
- **那么** 系统必须记录任务标识、调用状态和关键结果摘要
- **那么** 调试人员必须能够从日志中区分校验失败与执行失败

## 修改需求

## 移除需求
