## 为什么

当前 `dsl_node` 已经能访问 `lint`，也已经能看到 richer diagnostics，但它仍然经常只检查一次就结束。结果是即使首稿被判为 `invalid`，节点也不会稳定继续修正并再次校验，smoke 里长期停留在 `lint_calls: 1`。

## 变更内容

- 强化 `dsl_node` 的默认 prompt，明确要求在提交最终 `TaskDocument` 前使用 `lint` 做自检。
- 把“最终输出必须以当前 `lint` 视角下的 `valid` DSL 为默认目标”写成 `dsl_node` 的默认行为约束。
- 明确 `dsl_node` 在调用了 `lint` 且结果为 `invalid` 时，必须继续依据 `issues` 与 `expected` 修正 candidate，而不是直接结束。
- 为 `dsl_node` 增加有限的 `max_tool_calling` 预算，让 agent 可以进行受控的多次 `lint` 校验。
- 保留并明确 Python 侧 fallback：如果 agent 没有主动调用 `lint`，节点必须补做至少一次 fallback lint。
- 更新 workflow 和测试契约，覆盖 `invalid -> 修正 -> 再 lint` 与 fallback 场景。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `planner-node-prompts`: 调整 `dsl_node` 默认提示词，明确要求使用 `lint` 自检、在 `invalid` 后继续修正，并以输出 `valid` DSL 为默认目标
- `planner-langgraph-workflow`: 调整 `dsl_node` 的行为契约，要求它采用受控的多次 `lint` 校验，并保留 fallback lint

## 影响

- `config/prompts/planner_dsl_node_system.txt`
- `config/prompts/planner_dsl_node_user.txt`
- `src/augury/planner/nodes/dsl_node.py`
- `src/tests/test_planner_workflow.py`
- `src/tests/test_smoke_scripts.py`
- `src/smoke/test_dsl.py`
