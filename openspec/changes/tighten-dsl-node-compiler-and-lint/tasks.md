## 1. DSL Output Boundary

- [ ] 1.1 收紧 `src/augury/planner/task_document.py` 中的 `TaskDocumentSchema` / `TaskStepSchema`，让 `type` 与 `kind` 更接近当前 engine DSL 词表。
- [ ] 1.2 增加或调整测试，验证 `dsl_node` 的结构化输出不再轻易接受 `read`、`calculate`、`write` 这类项目外 step type。

## 2. DSL Prompting

- [ ] 2.1 更新 `config/prompts/planner_dsl_node_system.txt`，显式列出 engine 支持的 step type / kind，并禁止发明项目外 DSL 术语。
- [ ] 2.2 更新 `config/prompts/planner_dsl_node_user.txt`，加入 `TaskDraft -> engine primitive` 的 translation rules。
- [ ] 2.3 为 `dsl_node` 增加少量 few-shot，优先覆盖单体攻击、范围效果和状态更新等典型 lowering 模式。

## 3. Lint Aggregation

- [ ] 3.1 改造 `src/augury/engine/core/executor.py` 或相邻校验层，使语义校验尽量收集同一轮可独立发现的多个错误，而不是遇到第一个就停止。
- [ ] 3.2 更新 `src/augury/planner/tools/lint.py` 与相关测试，验证 `lint` 返回多个结构/语义问题时仍能给出稳定的 `issues` 列表。

## 4. Validation

- [ ] 4.1 更新 `src/tests/test_planner_workflow.py`，断言 `dsl_node` prompt 已明确声明 engine DSL 词表和禁止项。
- [ ] 4.2 更新 `src/tests/test_agent_lint.py`，增加“同一候选文档返回多个独立错误”的断言。
- [ ] 4.3 使用 `src/smoke/test_dsl.py` 验证 Fireball 样例不再优先生成项目外 DSL 术语，且 lint 能暴露多个明显问题。
