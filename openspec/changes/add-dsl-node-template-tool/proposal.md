## 为什么

现在 `dsl_node` 虽然已经知道一部分 `type.kind` 词表和 shape catalog，但它仍然经常不知道“当前这类任务对应的合法 DSL 模板到底是什么”，结果要么在长 prompt 里来回检索规则，要么直接发明不合法的字段与参数形状。随着模板说明越来越长，prompt 上下文被大量 DSL 教程占用，`dsl_node` 的收敛性和合法性都在恶化。

## 变更内容

- 为 `dsl_node` 增加一个名为 `template` 的只读工具，按需返回少量任务族的合法 DSL 模板、必填绑定项和常见错误提示。
- 让 `dsl_node` prompt 从“内联大段 DSL 教程”改为“识别任务族 -> 调用 template 工具 -> 基于模板填充实例参数 -> 再做 lint 校验”。
- 将 `template` 工具的输入限制为少量受控枚举字段，优先复用 `task_node` prompt 中已经使用的任务类型原型，避免模型自由发明签名。
- 在第一阶段只覆盖少量高频任务：单体武器攻击、单体豁免伤害法术、范围法术伤害、单体治疗或治疗增益。
- 增加自动测试与 smoke 验证，确保 `dsl_node` 能稳定调用 `template` 工具并消费返回的 DSL 骨架。

## 功能 (Capabilities)

### 新增功能
- `dsl-template-tool`: 为 `dsl_node` 提供按任务族查询的合法 DSL 模板、绑定规则与常见错误提示。

### 修改功能
- `planner-langgraph-workflow`: `dsl_node` 将在生成 `TaskDocument` 时调用 `template` 工具获取合法骨架，而不是只依赖长 prompt 中内联的 DSL 教程。
- `planner-node-prompts`: `dsl_node` prompt 将改为指导模型识别少量任务族、调用 `template` 工具并填充返回模板，而不是内联完整 DSL 模板手册。

## 影响

- `src/augury/planner/nodes/dsl_node.py`
- `src/augury/planner/tools/`
- `config/prompts/planner_dsl_node_system.txt`
- `config/prompts/planner_dsl_node_user.txt`
- `src/tests/test_planner_workflow.py`
- `src/tests/test_smoke_scripts.py`
- 可能新增 template 工具数据资产或模板定义模块
