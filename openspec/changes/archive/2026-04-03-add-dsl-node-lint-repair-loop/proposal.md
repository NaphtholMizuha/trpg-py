## 为什么

`tighten-dsl-node-compiler-and-lint` 已经把 `dsl_node` 从“发明项目外 DSL 词表”推进到了“基本能选对 engine primitive”，但 smoke 也清楚地表明：单次生成仍然会在 primitive 参数模板、`when` 表达式、path/ref 语义这些细节上反复犯错。现在开发者和模型一次通常只能看到当前候选文档的其中一轮错误，然后靠人肉重跑下一轮。

既然 `lint` 已经开始返回更结构化、更完整的 issues，下一步最自然的演进就是让 `dsl_node` 真正消费这些 issues，把“生成 -> lint -> 修正”内建成一个有限预算的编译回路，而不是继续停留在单次生成器模式。

这个回路应当以内置在 `dsl_node` 里的 ReAct 形式实现，由 agent 自己调用 `lint` 工具、观察 issues 并修复候选文档，而不是扩展成新的 LangGraph 节点流转。

## 变更内容

- 为 `dsl_node` 增加内部 ReAct 式 repair loop，让它在单个 node 内部调用 `lint` 工具，并在初稿不合法时进行 1 到 2 轮定向修正。
- 明确禁止为 repair 引入新的 LangGraph 节点或新的 planner 阶段；外部 workflow 仍保持 `task_node -> dsl_node -> end`。
- 为 repair 阶段定义单独的提示词或等价消息结构，要求模型尽量保留正确步骤，只修复 `lint` 明确指出的问题，并明确约束 `lint` 的最小/最大调用次数和停止条件。
- 让 `dsl_node` 在超过修复预算后仍返回最后一版候选文档和最终 `lint_result`，便于人工调试与 smoke 观察。
- 更新 smoke 输出和测试，让开发者可以看到 repair 回路是否收敛、经过了几轮以及最终剩余哪些问题。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `planner-langgraph-workflow`: `dsl_node` 将从单次生成阶段升级为带内部 ReAct lint-repair 回路的编译阶段，同时保持外层 workflow 不变。
- `lint-tool`: `lint` 返回的结构化 issues 将被正式作为 `dsl_node` repair 回路的输入契约，而不只用于人工观察。
- `smoke-test-layout`: `dsl_node` smoke 入口将需要展示 repair 回路的可观察结果，而不是只打印单轮生成后的 DSL 与 lint 状态。

## 影响

- `src/augury/planner/nodes/dsl_node.py`
- `config/prompts/planner_dsl_node_system.txt`
- `config/prompts/planner_dsl_node_user.txt`
- 可能新增 repair prompt 模板或在现有 prompt 中增加 repair 分支与 `lint` 调用预算约束
- `src/smoke/test_dsl.py`
- `src/tests/test_planner_workflow.py`
- `src/tests/test_smoke_scripts.py`
- 可能涉及 `src/tests/test_agent_lint.py` 的契约断言
