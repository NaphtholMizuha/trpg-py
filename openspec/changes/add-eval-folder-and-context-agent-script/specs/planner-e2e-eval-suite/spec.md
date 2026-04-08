## 新增需求

### 需求:端到端评测与子 agent 专项评测必须分离职责
系统必须将 planner 到 engine 的端到端评测与子 agent 的专项评测分离组织。系统禁止继续要求端到端评测入口同时承担 Context Agent bundle 细粒度观察职责。

#### 场景:开发者需要观察 Context Agent bundle
- **当** 开发者需要查看 Context Agent 的规则证据、状态证据和未决缺口
- **那么** 调用方必须可以使用专门的 Context Agent eval 脚本完成观察
- **那么** 端到端评测入口不需要额外承担同等级别的 bundle 展示职责

## 修改需求

### 需求:系统必须提供批量运行 instruction 到 engine 的端到端评测入口
系统必须提供一个可手动运行的批量评测入口，用于对每条案例执行 instruction -> `PlannerWorkflowResult` -> `TaskDocument` -> engine execution 的完整流程。系统禁止继续要求开发者手动在多个入口之间搬运 `TaskDraft` 或 `TaskDocument` 才能完成同一套案例的端到端验证。该端到端评测入口必须继续聚焦 workflow 到 engine 的完整回归，而不是承担针对单个子 agent bundle 的专项观察职责。

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

#### 场景:端到端入口不承担 Context Agent 专项观察
- **当** 开发者需要查看 Context Agent 的实时 `ContextBundle`
- **那么** 开发者必须使用独立的 Context Agent eval 脚本
- **那么** 端到端评测入口不得因为承担该职责而改变自身的批量回归定位

## 移除需求
