## 为什么

现在的 `lint` 已经能指出 `dsl_node` 生成的 DSL 哪里错了，但还不能稳定告诉它“正确形状应该长什么样”。结果就是模型即使知道 `check.save` 少了 `dice`，仍然会继续猜 `save_ability`、`amount`、`conditional_halving_on_save` 这种项目外字段，导致修复效率很差。

要让 `dsl_node` 真正消费 lint 结果，而不是只把它当报错列表，系统需要让 `lint` 返回模板化诊断：不仅指出错误路径和消息，还提供当前 `type.kind` 的最小合法模板、必填字段、允许字段和 canonical example。同时，`dsl_node` 的 prompt 和节点行为也要同步适配，显式把这些模板化诊断当成修正依据。

## 变更内容

- 为 `lint` 增加模板化诊断能力：当某个 step 或 args 形状不合法时，issue 除了 `path/message/code` 外，还返回该 `type.kind` 的期望模板信息。
- 引入一份统一的 step shape catalog，定义每类受支持 DSL primitive 的 canonical 模板、必填字段、允许字段和常见错误形状。
- 让 `dsl_node` prompt 明确把 lint 返回的模板化诊断视为修正依据，并把“最终目标必须是 lint valid”写成默认约束。
- 调整 `dsl_node` 节点与测试契约，使其能够稳定消费 richer lint issues，而不是只看一条 message。

## 功能 (Capabilities)

### 新增功能
- `lint-diagnostic-templates`: 为受支持的 DSL primitive 提供统一的模板化诊断契约，供 lint、dsl_node 和测试共享。

### 修改功能
- `lint-tool`: `lint` 将从“指出哪里错了”升级为“指出哪里错了 + 给出对应 primitive 的期望模板”。
- `planner-langgraph-workflow`: `dsl_node` 将显式把模板化 lint 诊断作为生成/修正约束的一部分，而不只是把 lint 当普通字符串反馈。
- `planner-node-prompts`: `dsl_node` prompt 将明确要求最终目标是 `lint valid`，并指导模型消费 lint 返回的模板、必填字段和 canonical example。

## 影响

- `src/augury/planner/tools/lint.py`
- 可能新增统一的 DSL step shape catalog 模块
- `src/augury/engine/core/executor.py` 或相关校验辅助逻辑
- `src/augury/planner/nodes/dsl_node.py`
- `config/prompts/planner_dsl_node_system.txt`
- `config/prompts/planner_dsl_node_user.txt`
- `src/tests/test_agent_lint.py`
- `src/tests/test_planner_workflow.py`
- `src/smoke/test_dsl.py`
