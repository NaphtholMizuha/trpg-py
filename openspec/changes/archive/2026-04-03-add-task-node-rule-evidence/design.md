## 上下文

当前 `TaskDraft` 主要包含 `task`、`judgments`、`reads`、`writes`、`missing_info`、`assumptions`、`context_lines` 和 `read_values`。这套结构对状态路径绑定已经够用，但对规则型任务仍然不够自然：
- `task_node` 即使通过 search 找到了关键规则，也只能把结论重写进 prose
- 中间对象里没有一个稳定字段来表达“task_node 认为这些证据对后续阶段有用”
- 对火球术这类 AoE 规则，当前 smoke 很难观察 `task_node` 是否已经抓到了范围判定所需的关键线索
- `read_values` 会把读取结果重复保留一份，而 `context_lines` 这个名字又难以体现它其实主要承载状态证据

与此同时，现有 `context_lines` 更偏向状态证据，不适合继续混入规则摘录；它也应该改成更直白的 `states`。规则证据和状态证据语义不同，长期混装会让下游更难区分。

## 目标 / 非目标

**目标：**
- 为 `TaskDraft` 引入 `evidence` 字段，承载供后续阶段消费的摘要化证据。
- 删除 `read_values`，避免中间对象继续保留重复读值快照。
- 把 `context_lines` 重命名为 `states`，明确其角色是状态证据集合。
- 让 `task_node` 可以把“它抓到且认为有用的规则”以摘录形式暴露出来。
- 让 smoke 和测试可以稳定观察 `task_node` 产出的关键规则 / 状态证据。
- 保持证据简短、结构化，不直接放规则原文。

**非目标：**
- 不把完整 search 命中正文复制进 `TaskDraft`。
- 不要求本次就让 `dsl_node` 消费 `evidence`。
- 不要求本次改变 `reads` / `writes` / `judgments` / `missing_info` / `assumptions` 的核心语义。
- 不引入新的外部依赖或复杂检索管线。

## 决策

### 决策 1：新增 `evidence`，并把 `context_lines` 重命名为 `states`
- 选择原因：现有 `context_lines` 名字过泛，实际主要承载状态证据；新增 `evidence` 后，如果不把它改名，两个字段会更容易混淆。
- 替代方案：继续使用 `context_lines`，仅靠语义约定区分它与 `evidence`。
- 未选择原因：短期能工作，但会让字段语义长期不清晰。

### 决策 2：删除 `read_values`
- 选择原因：`read_values` 本质上是对读值的重复快照。当前中间对象已经有 `reads` 和状态证据字段，继续保留一份专门映射会让 schema 更冗余。
- 替代方案：保留 `read_values` 作为调试辅助字段。
- 未选择原因：这会继续强化“中间对象像调试包而不是任务稿”的倾向。

### 决策 3：`evidence` 只放摘录，不放原文
- 选择原因：后续阶段需要的是能驱动推理的关键信息，而不是长段文本。摘录能减少 token 噪音，也更容易做稳定验证。
- 替代方案：直接放 search 命中的原文片段。
- 未选择原因：长原文会增加噪音，也让后续消费更依赖自由摘要而不是稳定线索。

### 决策 4：`evidence` 同时允许规则证据和关键状态证据
- 选择原因：未来后续阶段很可能同时需要“Fireball 是 20 尺半径范围”和“当前 goblin_1 是待结算对象”。统一放进 `evidence`，比继续拆回其他字段更符合“对后续阶段有用的证据”这一职责。
- 替代方案：只让 `evidence` 放规则证据，状态证据继续只放 `states`。
- 未选择原因：会让后续阶段继续跨两个字段拼装关键上下文，收益有限。

### 决策 5：先生产 `evidence`，暂不要求下游立即消费
- 选择原因：当前先要验证 `task_node` 是否能稳定产出有用证据，再决定 `dsl_node` 如何消费它。先拆成两步更利于迭代。
- 替代方案：在同一个变更里同时修改 `task_node` 和 `dsl_node`。
- 未选择原因：范围会变大，也更难判断收益究竟来自上游证据产出，还是来自下游 prompt 调整。

## 风险 / 权衡

- [风险] `evidence` 如果太自由，会退化成新的“垃圾收纳箱”
  - 缓解措施：要求只放 task_node 认为对后续阶段有用的摘录，且禁止直接复制长段原文。

- [风险] `evidence` 与 `judgments` 边界模糊
  - 缓解措施：`judgments` 继续表达执行逻辑；`evidence` 表达支持这些逻辑的摘要化证据。

- [风险] 这次只产出 `evidence`，短期内不一定立刻改善最终 DSL
  - 缓解措施：把本次目标限定为“先让中间对象更诚实、更可观察”；下游消费留给后续独立变更。

## Migration Plan

1. 为 `TaskDraft` 增加 `evidence` 字段。
2. 删除 `read_values`，并将 `context_lines` 迁移为 `states`。
3. 调整 `task_node` prompt，引导其把 search / grep 得到的关键证据摘录进 `evidence`。
4. 更新 smoke 与测试，验证 Fireball 类案例能输出有用的 `evidence` 摘录。
5. 在后续变更中再评估 `dsl_node` 如何消费 `evidence`。

## Open Questions

- `evidence` 是否要在数据结构上区分 `rule` / `state` 两种来源，还是先用统一字符串列表即可？
- `states` 最终是否保留为字符串列表，还是后续演进为更结构化的状态证据对象？
