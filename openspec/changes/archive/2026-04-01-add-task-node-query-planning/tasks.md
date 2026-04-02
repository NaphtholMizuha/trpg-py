## 1. TaskDraft Schema

- [x] 1.1 从 `TaskDraft` 中删除公开的 `query_plan` 字段及其相关兼容逻辑。
- [x] 1.2 保持 `context_lines` 作为第一阶段唯一必须保留的证据上下文字段。

## 2. Task Node Integration

- [x] 2.1 把 `task_node` 从“query planner + drafting pass”重构回单一 agent。
- [x] 2.2 恢复 `task_node` 自主使用工具并直接生成 `TaskDraft` 的流程。
- [x] 2.3 保留更高的 grep limit 策略，避免高噪音检索过早截断关键证据。
- [x] 2.4 保留 `context_lines` 的轻量相关性筛选，只输出合适的证据子集。

## 3. Validation

- [x] 3.1 更新测试，验证 `task_node` 不再需要内部两次 agent 调用。
- [x] 3.2 更新 smoke 输出，删除对 `query_plan` 的展示与断言。
- [x] 3.3 更新测试，验证高噪音查询不会因为过低 limit 丢失关键证据。
- [x] 3.4 更新测试，验证 `context_lines` 只保留与最终任务稿直接相关的证据行。
