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

## 移除需求
