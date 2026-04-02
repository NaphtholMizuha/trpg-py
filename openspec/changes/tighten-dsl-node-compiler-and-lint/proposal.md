## 为什么

`dsl_node` 当前能够把 `TaskDraft` 翻译成“看起来像流程 DSL”的 JSON，但它并不知道本项目引擎实际接受的 `TaskDocument` 词表、步骤原语和最小参数约束。结果就是 smoke 能稳定产出结构化结果，却同样稳定地产出 `read`、`calculate`、`write` 这类引擎根本不支持的 step type / kind。

与此同时，`lint` 目前在语义校验阶段通常只会停在第一个命中的错误上。这对人工调试还勉强可用，但对 `dsl_node` 这种要靠反馈迭代修正的生成阶段不够友好，因为模型和开发者一次只能看到“第一个坏点”，看不到整份候选文档里同时存在的其他明显问题。

## 变更内容

- 收紧 `dsl_node` 的“编译目标”，让它明确知道当前引擎支持的 `TaskDocument` step type / kind、常见最小参数约束以及禁止发明新 DSL 术语。
- 收紧 `TaskDocument` 的结构化输出边界，让 `dsl_node` 在结构化输出阶段就更难生成项目外的 DSL 词表。
- 为 `dsl_node` prompt 增加 few-shot 和 translation rules，重点展示 `TaskDraft` 如何下降到现有 engine primitive，而不是自由发明高层工作流步骤。
- 改进 `lint` 的返回策略，让它尽量在一轮校验中汇总同一候选文档中所有可独立发现的结构和语义错误，而不是只报第一个语义错误。
- 让 `dsl_node` 可以更有效地消费 `lint` 结果，为后续的自动修正回路创造条件。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `planner-langgraph-workflow`: `dsl_node` 将被收紧为面向当前 engine DSL 的受约束编译阶段，而不是自由生成通用 workflow JSON。
- `planner-node-prompts`: `dsl_node` 默认 prompt 将新增真实 DSL 词表、翻译规则和 few-shot，明确禁止生成引擎不支持的步骤类型。
- `lint-tool`: `lint` 将尽量在单轮校验中返回一组可定位的结构和语义错误，而不只停在第一个可见失败点。

## 影响

- `config/prompts/planner_dsl_node_system.txt`
- `config/prompts/planner_dsl_node_user.txt`
- `src/augury/planner/task_document.py`
- `src/augury/planner/nodes/dsl_node.py`
- `src/augury/planner/tools/lint.py`
- `src/augury/engine/core/executor.py`
- `src/tests/test_planner_workflow.py`
- `src/tests/test_agent_lint.py`
- `src/tests/test_smoke_scripts.py`
