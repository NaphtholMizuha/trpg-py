## 为什么

当前 `dsl_node` 虽然已经挂载了 `template`，但实际实现是宿主代码先预取模板结果，再把结果塞回 prompt。这不是真正的 tool 调用语义，也让日志、工具预算、回放和失败诊断都失真，用户看到的仍然像“模型没有调用 template”。

现在需要把 `template` 收回到和 `lint` 一样的边界里：由 agent 在推理过程中显式调用、留下调用痕迹、消耗工具预算，并在失败时能明确区分“模板没命中”和“模型没用模板”。

## 变更内容

- 移除 `dsl_node` 宿主侧对 `template` 的预取逻辑，禁止再把预取结果伪装成工具能力注入 prompt。
- 要求 `dsl_node` 中的 agent 像调用 `lint` 一样显式调用 `template`，并把调用结果作为后续 DSL 生成的直接依据。
- 调整 `dsl_node` prompt，不再依赖宿主注入的 `template_query_hint` 或 `template_lookup` JSON，而是要求模型先进行受控枚举分类，再调用 `template`。
- 为 `template` 增加可观测性要求，使日志或等价诊断信息能够证明 agent 是否调用了该工具以及传入了什么查询。
- 更新自动测试与 smoke，验证 `template` 是真实工具调用而不是宿主预取。

## 功能 (Capabilities)

### 新增功能
- `dsl-template-tool`: 为 `dsl_node` 提供必须由 agent 显式调用、可观测、可计入预算的模板查询工具契约。

### 修改功能
- `planner-langgraph-workflow`: `dsl_node` 必须通过 agent 显式调用 `template` 与 `lint`，宿主不得在 agent 运行前代替其完成模板查询。
- `planner-node-prompts`: `dsl_node` prompt 必须指导模型主动调用 `template`，而不是消费宿主预取好的模板结果。

## 影响

- `src/augury/planner/nodes/dsl_node.py`
- `src/augury/planner/tools/template.py`
- `config/prompts/planner_dsl_node_system.txt`
- `config/prompts/planner_dsl_node_user.txt`
- `src/tests/test_planner_workflow.py`
- `src/tests/test_smoke_scripts.py`
- 可能涉及 `src/smoke/test_dsl.py` 的观测或验证输出
