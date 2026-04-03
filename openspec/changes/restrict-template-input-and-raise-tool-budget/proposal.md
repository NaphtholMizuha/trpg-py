## 为什么

现在 `template` 已经进入了真实 tool-use 回路，但它的输入仍然是自由字符串，模型可以发明接近却不合法的值，例如 `area_spell`。这会让第一次模板查询直接 `no_match`，把有限的工具预算浪费在无效查询上。

与此同时，`dsl_node` 当前的默认工具预算只够非常理想的路径。一旦出现“首次 template 误查 -> 保守回退 -> 再 lint”的常见回路，就很容易在抵达最终停止条件前触发 `GraphRecursionError`。

## 变更内容

- 将 `template` 工具输入从普通字符串收紧为受控枚举类型，禁止继续接受或默认容忍自由拼写的任务族和值域。
- 要求 `template` 在收到非法枚举值时快速返回结构化错误或等价受控失败，而不是模糊地被当成普通 no-match。
- 提高 `dsl_node` 的默认工具调用预算，使“首次 template 查询失败、保守回退一次、再 lint 校验”的链路可以在默认配置下完成。
- 更新 `dsl_node` prompt，要求模型严格使用文档化的枚举值，并把 `unknown` 作为唯一合法保守回退。
- 补充自动测试与 smoke 验证，覆盖非法 template 输入、合法回退查询和提高预算后的默认运行行为。

## 功能 (Capabilities)

### 新增功能
- `dsl-template-tool-input-contract`: 为 `template` 建立受控输入类型契约，明确合法枚举值、非法输入行为和保守回退规则。

### 修改功能
- `planner-langgraph-workflow`: `dsl_node` 的默认工具预算必须能够覆盖一次模板误查后的保守回退与后续 lint 校验。
- `planner-node-prompts`: `dsl_node` prompt 必须严格指导模型使用合法 template 枚举值，并把 `unknown` 作为唯一保守值。

## 影响

- `src/augury/planner/tools/template.py`
- `src/augury/planner/dsl_template_catalog.py`
- `src/augury/planner/nodes/dsl_node.py`
- `config/prompts/planner_dsl_node_system.txt`
- `config/prompts/planner_dsl_node_user.txt`
- `src/tests/test_planner_workflow.py`
- `src/tests/test_smoke_scripts.py`
