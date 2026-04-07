# planner-e2e-eval-suite 规范

## 目的
待定 - 由归档变更 add-end-to-end-planner-engine-eval-suite 创建。归档后请更新目的。
## 需求
### 需求:系统必须提供固定的 planner 到 engine 端到端评测 fixture bundle
系统必须提供一套专门用于 planner -> engine 端到端评测的固定 fixture bundle，至少包含一个 world state 文件和一个案例 manifest。系统禁止继续只依赖开发者临时手写 instruction、复用日常 smoke state 或口头描述来完成全链路回归验证。

#### 场景:开发者使用默认评测案例
- **当** 开发者运行新的端到端评测入口且未额外指定案例文件
- **那么** 系统必须加载仓库内版本化维护的默认 world state fixture
- **那么** 系统必须加载与该 world state 配套的默认案例 manifest
- **那么** 该默认 manifest 必须包含恰好 10 条用户输入案例

#### 场景:默认案例覆盖关键任务形态
- **当** 调用方查看默认 10 条案例
- **那么** 案例集合必须至少覆盖武器攻击、法术攻击、治疗、范围法术、信息不足导致的 `needs_human`，以及状态投影或记录类任务
- **那么** 默认案例必须包含显式爆点的范围法术与缺少关键绑定信息的范围法术

### 需求:系统必须提供批量运行 instruction 到 engine 的端到端评测入口
系统必须提供一个可手动运行的批量评测入口，用于对每条案例执行 instruction -> `PlannerWorkflowResult` -> `TaskDocument` -> engine execution 的完整流程。系统禁止继续要求开发者手动在多个 smoke 脚本之间搬运 `TaskDraft` 或 `TaskDocument` 才能完成同一套案例的端到端验证。

#### 场景:案例可直接执行到 engine
- **当** 某条案例经过 planner workflow 返回 `status=ready`
- **那么** 评测入口必须继续使用该 `task_document` 调用 engine
- **那么** 评测入口必须基于固定骰子来源运行 execution
- **那么** 评测入口必须记录执行状态和状态变化

#### 场景:案例预期需要人工补充
- **当** 某条案例经过 planner workflow 返回 `status=needs_human`
- **那么** 评测入口不得继续对该案例执行 engine
- **那么** 评测入口必须记录该案例的 `missing_info`、`draft` 和 workflow 状态
- **那么** evaluator 必须允许该案例被判定为“符合预期的缺口暴露”，而不是一律记作失败

### 需求:每条端到端案例必须记录完整中间产物日志
系统必须为每条评测案例生成结构化日志，并在单文件中记录 planner 与 engine 之间的关键中间状态。系统禁止只输出最终 pass/fail 或只输出最终 state diff，而不暴露 `TaskDraft`、`TaskDocument` 和 lint 结果。

#### 场景:开发者查看单案例日志
- **当** 某条案例运行结束
- **那么** 该案例的日志必须至少包含 `case_id`、`instruction`、`workflow_result.status`、`draft`、`missing_info`、`task_document`、`lint_result`、`execution_result`、`state_changes` 和 `evaluation`
- **那么** 若运行中出现异常，日志必须保留结构化错误信息而不是只剩控制台 traceback

#### 场景:开发者比较 planner 中间状态
- **当** 开发者需要定位回归发生在规划、lowering 还是 execution
- **那么** 单案例日志必须允许开发者直接查看 `TaskDraft` 与 `TaskDocument`
- **那么** 日志不得要求开发者额外重跑 task smoke 或 dsl smoke 才能看到这些中间对象

### 需求:端到端评测必须基于结构化 expectation 自动评分
系统必须允许每条案例在 manifest 中声明结构化 expectation，并由 evaluator 自动生成通过、失败和失败原因。系统禁止继续把全文字符串精确匹配作为端到端评测的主要判定标准。

#### 场景:案例声明成功链路 expectation
- **当** 某条案例期望完整执行成功
- **那么** manifest 必须能够声明至少 workflow 状态、lint 状态、关键 step signature、关键 changed paths 或等价结构化断言
- **那么** evaluator 必须依据这些结构化 expectation 生成该案例的通过或失败结果

#### 场景:案例声明缺口暴露 expectation
- **当** 某条案例期望 `needs_human`
- **那么** manifest 必须能够声明期望的 workflow 状态和 `missing_info` 关键词或等价结构化断言
- **那么** evaluator 必须允许该案例在未执行 engine 的前提下通过

### 需求:端到端评测必须生成汇总结果
系统必须为整套 10 条案例生成统一汇总，展示通过率、失败数和每条案例的快速摘要。系统禁止要求开发者逐个打开日志文件才能知道这次评测整体是否通过。

#### 场景:开发者查看默认评测汇总
- **当** 开发者运行默认 10 条案例的端到端评测
- **那么** 系统必须输出整套案例的统计摘要
- **那么** 摘要必须至少包含总案例数、通过数、失败数以及每条案例的 case id 与结果
- **那么** 若某条案例失败，摘要必须能指出失败阶段或失败原因摘要

