## 为什么

现在的 `lint` 已经能抓住一部分结构和语义问题，但还没有完全覆盖“能过 lint、却会在 engine runtime 失败”的 DSL 形状错误。同时，`dsl_node` 虽然知道受支持的 `type/kind` 词表，却还不知道“每一种合法 DSL 具体应该长什么样”，因此仍会生成运行时不接受的参数形状。

要让 `dsl_node` 稳定产出真正可执行的 `TaskDocument`，系统需要同时补两件事：一是把 `lint` 提升为更接近 runtime 契约的执行前校验器；二是把所有合法 DSL 形状显式整理成统一的 shape catalog，作为 `dsl_node` prompt 和后续校验的共同来源。

## 变更内容

- 扩展 `lint`，让它不仅检查当前已知字段错误，还尽量覆盖所有会导致 runtime 失败的常见 shape/arg 组合错误。
- 引入一份统一的合法 DSL 形状目录，明确列出每类 `type.kind` 的合法参数模板、必填字段、禁止形状和引用约束。
- 让 `dsl_node` prompt 不再只依赖词表和少量 few-shot，而是显式消费这份 shape catalog，理解“所有可能的合法 DSL 长什么样”。
- 增加针对 runtime-sensitive DSL 错误、shape catalog 渲染和 prompt 对齐的自动测试。

## 功能 (Capabilities)

### 新增功能
- `planner-dsl-shapes`: 统一定义 `dsl_node` 可生成的合法 `TaskDocument` 形状目录，覆盖受支持的 `type.kind` 及其参数模板。

### 修改功能
- `lint-tool`: `lint` 将从一般结构校验扩展为更接近 engine runtime 契约的执行前校验器。
- `planner-node-prompts`: `dsl_node` prompt 将从“词表 + 零散规则”升级为“词表 + 合法 shape 目录 + 约束模板”。

## 影响

- `src/augury/planner/tools/lint.py`
- `src/augury/engine/core/executor.py` 或相关校验辅助逻辑
- `config/prompts/planner_dsl_node_system.txt`
- `config/prompts/planner_dsl_node_user.txt`
- 可能新增统一的 DSL shape 定义模块或配置资产
- `src/tests/test_agent_lint.py`
- `src/tests/test_planner_workflow.py`
