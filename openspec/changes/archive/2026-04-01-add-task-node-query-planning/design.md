## 上下文

前一版设计试图在 `task_node` 内部加入显式的 `query_plan` 阶段：

```text
instruction
  -> query planner
  -> grep
  -> drafting pass
```

这个结构虽然提升了可观察性，但也把第一阶段的推理切断了。查询规划和任务起草不再共享同一条思考链，导致：

- agent 不能边查边调整检索策略
- 规则依赖强的任务很难自然决定是否该用 `search`
- `TaskDraft` 里暴露 `query_plan`，却未必真正提升最终任务稿质量

基于这些反馈，本次变更改写为更简单的一体式设计：

```text
instruction
  -> task_node (single ReAct agent)
  -> TaskDraft
  -> dsl_node
```

## 目标 / 非目标

**目标：**
- 保持 `task_node` 为单一 agent 节点，不再拆成“查询规划 + 起草”两个内部阶段。
- 允许 `task_node` 在同一条推理链中决定如何检索和如何起草 `TaskDraft`。
- 删除 `query_plan` 作为公开中间对象的要求。
- 让 `TaskDraft.context_lines` 成为第一阶段唯一必须保留的证据上下文，并要求其保持相关性。

**非目标：**
- 本次设计不恢复 `read` 权限。
- 本次设计不要求引入额外的查询轨迹或工具调用日志 schema。
- 本次设计不改变 `dsl_node` 的核心职责。

## 决策

### 决策 1：`task_node` 应保持为单一 agent

`task_node` 不应再在内部拆成一个“生成查询计划”的 agent 和一个“写任务稿”的 agent。它应当是一个完整的一体式 ReAct 节点，在同一个 agent 中完成：

- 理解 instruction
- 使用工具检索状态或规则
- 根据检索结果继续调整思考
- 最终产出 `TaskDraft`

这样做的原因是：
- 第一阶段真正需要的是边查边想，而不是先规划再消费
- 复杂任务往往需要在观察到证据后继续决定下一步检索
- 单一 agent 更符合“两个节点”的总体目标

替代方案：
- 继续保留 query planner + drafting pass：更可观察，但推理链被切断

### 决策 2：删除 `query_plan` 作为 `TaskDraft` 公开字段的要求

`TaskDraft` 不再要求保留 `query_plan`。第一阶段的核心产物应是任务稿本身和其支持证据，而不是查询计划轨迹。

这样做的原因是：
- 当前最关心的是任务稿质量，而不是查询历史
- `query_plan` 会把中间对象重新变成流程暴露，而不是任务语义暴露
- 如果后续确实需要轨迹，可再单独设计 debug 字段，而不污染任务稿 schema

替代方案：
- 保留字符串列表形式的 `query_plan`：简单，但会继续把第一阶段绑回拆分式设计

### 决策 3：`context_lines` 是 `task_node` 唯一必须公开保留的检索证据

`task_node` 最终应只保留它认为适合支持 `TaskDraft` 的 `context_lines`。这些行可以来自 `grep` 或其他可用工具的证据消费结果，但不要求公开暴露完整查询轨迹。

这样做的原因是：
- `context_lines` 更贴近任务稿需要的证据包
- smoke 和调试可以直接观察“留下了什么证据”
- 比单独暴露 query 轨迹更聚焦、更贴近实际任务质量

替代方案：
- 暴露全部查询与全部命中：可观察性更强，但噪音过高

### 决策 4：检索参数与证据筛选仍需保留

即使不再保留 `query_plan`，前一轮探索得到的两个收敛结论仍然成立：

- `task_node` 不得依赖过低固定 grep limit
- `TaskDraft.context_lines` 必须经过相关性筛选

这样做的原因是：
- 这是检索质量问题，不依赖于是否暴露 query 计划
- 即使在单一 agent 设计下，过低 limit 和无差别拼接命中仍然会破坏任务稿质量

## 风险 / 权衡

- [query 轨迹不再直接可见] → 换来更简单一致的 `TaskDraft` 语义。
- [单一 agent 更依赖 prompt 质量] → 但整体推理链更连贯，复杂任务更自然。
- [后续若要 debug 检索过程，可能需要额外日志层] → 可在 debug/logging 层解决，而不进入任务稿 schema。

## Migration Plan

1. 删除 `TaskDraft` 中公开的 `query_plan` 要求。
2. 把 `task_node` 从内部两段式改回单一 agent。
3. 让 `task_node` 自主使用工具完成检索和任务起草。
4. 保留高于低固定值的 grep limit 策略。
5. 保留 `context_lines` 的相关性筛选。
6. 更新 smoke 与测试，使其围绕“最终上下文是否合适”而不是“query_plan 是否可见”进行验证。

## Open Questions

- 如果后续仍然需要查询轨迹用于调试，应该放在独立日志结构里，还是放在 smoke 的调试输出里，而不进入 `TaskDraft`？
