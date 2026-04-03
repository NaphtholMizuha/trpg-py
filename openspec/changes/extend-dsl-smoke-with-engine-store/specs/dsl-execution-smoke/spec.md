## 新增需求

### 需求:test_dsl 必须能够把 lint 通过的 TaskDocument 交给真实 engine 执行
系统必须让 `src/smoke/test_dsl.py` 在生成并校验 `TaskDocument` 后，于 `lint_result.status == "valid"` 时继续调用真实 engine 执行该文档，禁止把 smoke 停留在“只展示 DSL 和 lint”这一层。

#### 场景:lint 通过后继续执行 DSL
- **当** 开发者运行 `src/smoke/test_dsl.py` 且生成的 `lint_result.status` 为 `valid`
- **那么** 脚本必须把该 `task_document` 交给真实 engine 执行
- **那么** 脚本必须输出执行阶段的结果摘要

### 需求:test_dsl 执行阶段必须使用真实 store state 并展示关键变化
系统必须让 `src/smoke/test_dsl.py` 在执行阶段基于真实 world state/store 语义运行，并展示执行前后发生变化的关键 path 摘要，禁止只打印“执行成功”而完全不展示状态变化。

#### 场景:开发者观察执行后的状态变化
- **当** `src/smoke/test_dsl.py` 成功执行一份 lint 通过的 `TaskDocument`
- **那么** 输出中必须可以看到执行前后发生变化的关键 state path
- **那么** 输出中必须可以看到这些变化与本次执行结果相关联

## 修改需求

### 需求:smoke 目录必须为 dsl_node 提供独立的手动验证入口
系统必须在 `src/smoke/` 目录下为 `dsl_node` 提供独立的手动验证脚本入口，禁止要求开发者只能通过自动测试、临时 Python 片段或完整 planner workflow 才能观察 `TaskDraft -> TaskDocument` 的翻译结果。

#### 场景:开发者单独验证 dsl_node 输出
- **当** 开发者需要检查一份现成 `TaskDraft` 会被 `dsl_node` 翻译成什么 `TaskDocument`
- **那么** 可以直接在 `src/smoke/` 下找到独立的 `dsl_node` smoke 入口
- **那么** 该入口必须与其他 smoke 脚本保持一致的目录语义

#### 场景:开发者观察 dsl_node repair 回路
- **当** `dsl_node` smoke 入口在首轮生成后进入 lint-repair 回路
- **那么** 脚本输出必须能让开发者观察是否触发了 repair
- **那么** 脚本输出必须能让开发者观察最终轮次和最终 lint 结论

#### 场景:lint 未通过时跳过执行阶段
- **当** `src/smoke/test_dsl.py` 生成的 `lint_result.status` 不为 `valid`
- **那么** 脚本必须明确标记执行阶段被跳过
- **那么** 脚本禁止继续把无效 `TaskDocument` 交给 engine 执行

## 移除需求
