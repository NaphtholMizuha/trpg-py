## 为什么

`dsl_node` 现在同时承担两件事：一边通过 `lint` 工具做内部自检，一边通过 `response_format=TaskDocumentSchema` 提交最终结构化结果。`task_node` 已经证明“工具 + 结构化输出”这组能力本身是可行的，但 `dsl_node` 目前又把 `lint` 提升成了带预算、带 repair 状态、带 candidate 回传的控制流工具，导致 prompt 里塞进了过多回路状态。

`task_node` 没有同样的问题，是因为它把工具当作取证手段，最后一次性提交结构化结果；`dsl_node` 目前却把 `lint` 提升成了流程控制器。这次变更要把 `dsl_node` 拉回更稳定的协议：保留 `response_format=TaskDocumentSchema` 作为最终提交通道，但把 `lint` 降回诊断工具，去掉 prompt 中过重的 repair 回路控制和中间 candidate 状态。

## 变更内容

- 将 `dsl_node` 的 `lint` 从“必须驱动内部 repair 控制流的工具”降级为“可选的诊断/查证工具”，允许 agent 在最终结构化提交前用它检查 candidate，但不再把它写成强制控制流。
- 调整 `dsl_node` 的 prompt 与节点状态，移除与强制 repair 回路、固定 lint 预算、中间 candidate 回传绑定过深的机制。
- 保留 `response_format=TaskDocumentSchema` 作为 `dsl_node` 最终提交协议，并确保默认提示词明确要求最终只提交一份结构化 `TaskDocument`。
- 更新 smoke 和测试，验证 `dsl_node` 在使用 `lint` 诊断后仍能稳定返回结构化 DSL，并继续兼容 lint 观察与后续执行链路。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `planner-langgraph-workflow`: `dsl_node` 将继续使用 `response_format=TaskDocumentSchema` 作为最终提交协议，但其内部不再默认依赖强制 repair 回路和固定 lint 预算。
- `planner-node-prompts`: `dsl_node` prompt 将改为指导 agent 把 `lint` 当作诊断工具使用，并避免输出中间 candidate、repair 状态和多余控制流文本。
- `smoke-test-layout`: `dsl_node` smoke 入口需要继续显示 lint 与 execution 结果，并帮助开发者观察结构化输出是否仍然稳定。

## 影响

- `src/augury/planner/nodes/dsl_node.py`
- `config/prompts/planner_dsl_node_system.txt`
- `config/prompts/planner_dsl_node_user.txt`
- `src/smoke/test_dsl.py`
- `src/tests/test_planner_workflow.py`
- `src/tests/test_smoke_scripts.py`
