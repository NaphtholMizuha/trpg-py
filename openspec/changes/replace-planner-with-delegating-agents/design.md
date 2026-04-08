## 上下文

当前系统的规划真相分散在两层：

- 运行时上，`src/augury/planner/workflow.py` 使用固定的 `task_node -> dsl_node` 流程组织 planner。
- 验证上，`src/smoke/` 下存在多条长期入口，把 task、dsl、search、grep、planner+engine 等手动脚本当作主要观察面。

这套结构的问题不在于“有两个阶段”，而在于它把编排方式、子能力边界和验证方式都固化了：

- 主流程只能围绕 `TaskDraft` 和 `TaskDocument` 两段式展开。
- 上下文获取与执行求解被嵌在固定节点里，无法用统一的委派模型扩展更多 agent。
- smoke 目录既承担调试入口，又承担部分能力契约，导致规范与代码长期围绕手动脚本演进。

这次设计要把系统重心转到“主 agent 委派运行时”：

- 主 agent 负责技能发现、能力装配和子 agent 委派。
- Context Agent 专门获取规则与世界状态上下文。
- Resolution Agent 专门校验与执行。
- 手动 smoke 退出长期架构真相，回归入口收敛到自动测试和版本化评测。

## 目标 / 非目标

**目标：**

- 用单一主 agent 取代固定的双节点 planner 编排真相。
- 为主 agent 提供稳定的 `list_skills`、`load_skills`、`delegate` 三个工具。
- 定义 Context Agent 与 Resolution Agent 的输入输出契约和默认工具边界。
- 新增 `execute` 工具，把现有 engine 执行能力提升为 agent 级工具。
- 删除 `src/smoke/` 及其对应的长期规范约束。
- 保留现有 engine、store、search、grep、lint 等底层能力的可复用性。

**非目标：**

- 本次设计不要求一次性重写 engine 或 store 语义。
- 本次设计不要求保留 `TaskDraft`、`task_node`、`dsl_node` 的兼容 API。
- 本次设计不要求新增更多子 agent 类型；先聚焦主 agent、Context Agent、Resolution Agent。
- 本次设计不把“如何选择具体模型”作为核心目标，模型选择继续沿用现有统一配置思路。

## 决策

### 决策 1：以主 agent 取代固定 LangGraph 编排

主 agent 将成为新的编排真相。它不再依赖固定图里写死的 `task_node` 和 `dsl_node`，而是通过 `delegate` 工具把子任务交给命名子 agent。

选择理由：

- 这更符合后续继续拆分更多专职 agent 的方向。
- “技能发现 / 能力加载 / 委派”会成为一等概念，而不是隐藏在 Python 装配代码里的依赖注入细节。
- 主 agent 的行为边界比 LangGraph 两节点模型更贴近你现在要的产品心智。

备选方案：

- 保留 LangGraph，只把 `task_node` 和 `dsl_node` 改名为 Context/Resolution。未采用，因为这只改了表面命名，没有改编排真相。
- 保留两阶段 workflow，但把工具集改掉。未采用，因为仍然会把新架构锁死在旧中间层上。

### 决策 2：用两个结构化 bundle 连接子 agent，而不是自由文本

Context Agent 返回 `ContextBundle`，Resolution Agent 返回 `ResolutionBundle`。具体字段名可以在实现时细化，但语义必须稳定。

`ContextBundle` 至少包含：

- `rule_evidence`
- `state_evidence`
- `unresolved_gaps`
- `citations`

`ResolutionBundle` 至少包含：

- `status`
- `lint_result`
- `execution_report`
- `state_changes`
- `blocked_reasons`

选择理由：

- 这能避免把委派退化成“子 agent 回一段 prose，主 agent 再猜”。
- 可以直接支持自动测试、评测和阶段化诊断。

备选方案：

- 只让子 agent 返回自然语言摘要。未采用，因为这会让验证、回归和故障定位都重新变脆。
- 继续强制保留 `TaskDraft -> TaskDocument` 作为唯一中间契约。未采用，因为这会把新架构拖回旧分层。

### 决策 3：Resolution Agent 对外以执行结果为中心，但内部仍保留可审计中间结果

对调用方来说，Resolution Agent 的主要返回物是 lint / execute 之后的解析结果；但运行时应保留内部候选文档和 lint 细节，以便诊断。

选择理由：

- 这满足“返回的是执行结果”的产品目标。
- 同时保留了调试和评测所需的中间可观测性，避免把问题重新压扁成黑盒。

备选方案：

- 完全不保留中间候选文档。未采用，因为 lint 失败、执行失败和上下文不足将难以区分。

### 决策 4：把 engine 包装成新的 `execute` 工具，而不是让 Resolution Agent 直接调用内部函数

Resolution Agent 将通过稳定的 `execute` 工具调用 engine。该工具复用现有执行器，但以 agent tool 契约暴露。

选择理由：

- 这让 Resolution Agent 的工具边界清晰且可测。
- 主 agent 和子 agent 都不需要直接依赖 engine 内部模块结构。

备选方案：

- 直接在 Resolution Agent 内部调用 `execute_task(...)`。未采用，因为这会把 runtime 编排和 engine API 直接耦合。

### 决策 5：彻底删除 smoke 目录，把回归真相收敛到 tests 和 eval fixtures

`src/smoke/` 不再作为长期目录或规范真相存在。替代路径是：

- 自动测试位于 `src/tests/`
- 版本化评测 fixture 继续位于 `examples/evals/` 或等价目录

选择理由：

- smoke 当前已经从“临时人工观察”膨胀成长期契约，拖慢架构演进。
- 删除 smoke 后，验证入口会更一致：要么是自动测试，要么是固定案例评测。

备选方案：

- 保留 smoke，但标记为 deprecated。未采用，因为会让规范和目录结构继续背负双轨真相。

## 风险 / 权衡

- 破坏性迁移成本高 → 通过新 capability 和显式任务分组，把删除 smoke、替换编排、引入 execute tool 拆开实施。
- 旧规范重叠较多，容易出现遗漏 → 本次变更会同时修改 `planner-workflow`、`planner-langgraph-workflow` 和多份 smoke 相关 spec，避免实现与规范分叉。
- 主 agent 过度智能、边界反而模糊 → 通过固定的三个主工具和两个子 agent profile 收紧第一版范围。
- Resolution Agent 黑盒化风险 → 要求返回结构化 lint / execute 结果，并在内部保留可审计中间状态。
- 删除 smoke 后开发者可能失去手工调试抓手 → 用固定 eval suite 和更可读的测试输出来替代，而不是继续维护脚本式入口。

## 迁移计划

1. 先新增主 agent 运行时和 `execute` 工具契约，不立即删除所有旧实现。
2. 再把 planner 对外入口切换到主 agent + delegate 模式。
3. 让 Context Agent 接管 `grep`/`search`，让 Resolution Agent 接管 `lint`/`execute`。
4. 用测试和评测覆盖新入口后，再删除 `src/smoke/` 和旧的节点编排实现。
5. 最后清理旧规范、旧 prompt 和旧目录假设。

回滚策略：

- 在完全切换对外入口之前，保留旧 planner 路径一小段迁移窗口。
- 若委派式运行时在评测中不稳定，可先回到旧入口，同时保留新 capability 文档继续迭代。

## 开放问题

- Resolution Agent 的内部候选文档是否继续沿用当前 `TaskDocument` 形状，还是引入新的中间 schema。
- `list_skills` / `load_skills` 的“skills”是否仅表示本地 agent profile，还是也包含 prompt/工具模板。
- `delegate` 是否只允许主 agent 使用，还是未来允许子 agent 再次委派。
- 删除 smoke 后，是否仍需要保留一个面向开发者的非测试 CLI 入口，还是完全由 tests/evals 承担观察面。
