## 1. Runtime 收尾改造

- [x] 1.1 在 `ToolCallLimitExceededError` 分支中接入无工具 forced-finalize 路径，替代当前直接返回 `needs_human/tool_budget_exhausted`
- [x] 1.2 让 forced-finalize 继续复用现有 `PlannerResult` 结构校验与 `TaskDocument` 语义校验，确保它输出的仍是合法最终结果
- [x] 1.3 补充日志和 debug 字段，区分“预算耗尽事件”“forced-finalize 已执行”“forced-finalize 自身失败”

## 2. Prompt 与可观察性

- [x] 2.1 更新 planner prompt 或 forced-finalize 输入文案，明确预算耗尽后只能基于已有证据强制收尾，禁止再次调用工具
- [x] 2.2 调整 smoke 摘要或调试输出，使开发者可以看出结果是否来自预算耗尽后的强制收敛

## 3. 验证

- [x] 3.1 添加单元测试，覆盖“预算耗尽但最终返回 ready”和“预算耗尽后返回真实 needs_human”两条路径
- [x] 3.2 添加失败回退测试，覆盖 forced-finalize 本身无法产出合法结果时仍返回 `tool_budget_exhausted`
- [x] 3.3 运行相关测试或 smoke，验证 planner 不再在预算触发时立即停止而是先尝试输出最终结果
