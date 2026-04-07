## 为什么

当前 `task_node` 的默认 prompt 过度强调任务原型分类、固定工具顺序和 few-shot 范式，容易把模型推向“先套类别、再补证据”的工作方式，削弱其对混合任务、边界案例和真实缺口的判断能力。与此同时，`dsl_node` 虽然已经接入 `template` 与 `lint`，但 prompt 仍更像“受控模板填写器”，没有把 engine primitive 的运行语义充分暴露给模型，导致它在合法性之外缺少对“为什么这样 lowering”与“哪些原语可以合理组合”的更深理解。

现在需要把 planner prompt 从“强行规定思维姿势”调整为“约束输出边界并提升原语理解”。这样既能保留现有 harness 的稳定性，又能释放模型在任务理解与 DSL 编排上的泛化能力。

## 变更内容

- 重写 `task_node` prompt，使其从“分类介绍式 prompt”转向“基于执行目标、关键证据、缺口暴露与状态绑定”的启发式 prompt。
- 降低 `task_node` prompt 对固定任务原型、固定查询模式和过强 few-shot 依赖的中心性，保留必要护栏，但不再把分类结果当作主要推理入口。
- 重写 `dsl_node` prompt，使其明确解释 engine 中每类 primitive 的职责、输入输出语义、常见组合关系和适用边界。
- 允许 `dsl_node` 在理解 engine 原语语义的前提下，更自由地组合 `select`、`check`、`damage`、`heal`、`resource`、`effect`、`state` 等 primitive，而不是只围绕少量模板化任务族做机械填空。
- 保留 `template` 与 `lint` 作为边界护栏和诊断工具，但 prompt 必须把它们描述为帮助模型理解和校验 DSL 的工具，而不是替代原语理解的唯一真相。
- 更新相关 prompt 规范与 workflow 规范，明确新的 prompt 设计目标、允许的自由度以及仍需保留的机械约束。

## 功能 (Capabilities)

### 新增功能

无。

### 修改功能

- `planner-node-prompts`: 调整 `task_node` 与 `dsl_node` 默认 prompt 的设计目标，要求 `task_node` 更具启发性，要求 `dsl_node` 更好地理解 engine primitive 的运行语义与组合方式。
- `planner-langgraph-workflow`: 调整 planner workflow 对两个节点 prompt 行为的规范约束，减少 `task_node` 的“分类先行”硬约束，并强化 `dsl_node` 的 primitive 语义建模与自由 lowering 能力。

## 影响

- 受影响代码：`config/prompts/planner_task_node_system.txt`、`config/prompts/planner_task_node_user.txt`、`config/prompts/planner_dsl_node_system.txt`、`config/prompts/planner_dsl_node_user.txt`
- 受影响测试：`src/tests/test_planner_workflow.py` 以及任何断言旧 prompt 词汇、few-shot 结构或固定流程措辞的测试
- 受影响规范：`openspec/specs/planner-node-prompts/spec.md`、`openspec/specs/planner-langgraph-workflow/spec.md`
- 预期风险：prompt 放松后，短期内可能出现更自由但不够收敛的输出；需要通过规范、测试和 smoke/eval 共同约束
