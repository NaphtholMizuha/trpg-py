## 1. Evidence stop criteria

- [x] 1.1 在 planner evidence 阶段引入可判定的 Required Gaps / Optional Gaps 模型，并把“关键缺口已闭合”接入 `ready_for_dsl` 的停机条件。
- [x] 1.2 为单攻击者对单目标的武器攻击实现最小证据闭包判定，明确 attacker、target、`to_hit`、target AC 与 damage spec 是首批关键缺口。

## 2. Planner behavior and prompts

- [x] 2.1 更新 planner evidence prompt，使其以 DSL 最小闭包为目标，要求工具调用只服务于闭合 Required Gaps，并把 Optional Gaps 明确降级为非阻塞项。
- [x] 2.2 为 evidence stage 增加 sufficiency-focused few-shot，覆盖“关键缺口闭合后立即 ready”“仍有 Required Gaps 时继续取证”“无法消歧时转入 needs_human”三类示例。
- [x] 2.3 调整 evidence 阶段的工具使用策略，确保简单攻击优先 `grep` + 批量 `read`，仅在仍存在规则型关键缺口时才触发 `search`。
- [x] 2.4 为 evidence 阶段加入 over-collection 收束逻辑，避免围绕同一主题重复查询、补充非关键状态或仅靠预算耗尽才停机。

## 3. Validation

- [x] 3.1 为 planner 单元测试补充 “关键缺口闭合后立即停止取证” 和 “Optional Gaps 不触发 needs_human” 场景。
- [x] 3.2 为 few-shot sufficiency 示例补充针对性测试，确认模型在简单攻击、未闭合关键缺口和真实歧义三类场景下符合预期停机行为。
- [x] 3.3 为简单单体武器攻击补充 smoke/集成验证，确认 evidence 工具调用数下降且不再因过量取证频繁落入 `tool_budget_exhausted`。
