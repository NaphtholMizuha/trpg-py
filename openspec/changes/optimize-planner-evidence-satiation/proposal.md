## 为什么

当前 planner 的 evidence agent 在简单动作上经常继续补充“更完整”的证据，而不是在已经足够生成合法 `TaskDocument` 时及时停止。这会推高 `grep`、`search`、`read` 与 `lint` 的调用次数，放大 `tool_budget_exhausted`，并让 smoke 流程频繁落入不必要的 HITL 恢复。

## 变更内容

- 为 planner evidence 阶段补充明确的“证据已足够”停止标准，使其以 DSL 可生成性而不是最大确定性作为停机条件。
- 将 evidence 取证过程划分为阻塞 `TaskDocument` 生成的关键缺口与仅提升信心的可选缺口，要求工具调用只服务于闭合关键缺口。
- 为常见动作形态建立最小证据闭包，优先覆盖单攻击者对单目标的武器攻击场景，减少对基础规则与非关键状态的过量取证。
- 约束 `search`、`grep`、`list`、`read` 与 `lint` 的使用节奏，避免围绕同一主题重复试探，或在没有新证据时继续机械修补。
- 收紧 `needs_human` 触发条件，使其只在关键缺口未闭合或存在真实歧义时出现，而不是因为 evidence agent 过度取证耗尽预算。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `agent-planner`: 调整 planner evidence 阶段的取证停止条件、工具使用边界与 `needs_human` 触发语义，使其在最小证据闭包满足后立即进入 DSL 生成而不是继续过量取证。

## 影响

- 受影响代码：`src/augury/agent/planner.py`、planner prompt 模板、planner 相关测试与 smoke 脚本断言。
- 受影响行为：简单攻击类指令的 evidence tool 调用次数应下降；`tool_budget_exhausted` 导致的 `needs_human` 次数应下降；`search` 应从简单动作的默认取证动作收缩为兜底动作。
- 受影响规范：需要增量修改 `openspec/specs/agent-planner/spec.md`，补充 evidence sufficiency、required/optional gaps 与 over-collection 相关需求。
