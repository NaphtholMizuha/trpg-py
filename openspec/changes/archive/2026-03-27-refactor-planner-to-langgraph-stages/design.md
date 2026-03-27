## 上下文

当前 planner 已经使用 `create_agent()` 运行，但从职责上看仍是一个“混合 agent”：
- 同一轮里既负责 `search/list/read` 取证，又负责产出 `TaskDocument`
- `lint` 既是校验器，也是隐式的 DSL 修复回路
- `needs_human` 对外暴露为返回状态，但内部实现仍接近“本轮结束”

这让几个问题反复出现：
- 取证预算和 DSL 修复预算混用
- `ToolCallLimitExceededError`、DSL 校验失败和真正的业务缺口很容易被混成同类失败
- `needs_human` 虽然名义上支持 resume，但在架构上还不是显式的暂停点

这次变更的核心不是换一个框架名词，而是把 planner 明确建模成一个可暂停、可恢复、可观察的 staged workflow。

## 目标 / 非目标

**目标：**
- 把 planner 主流程重构为显式的 LangGraph 工作流。
- 让 `evidence_agent` 和 `dsl_agent` 成为两个独立的 `create_agent()` 节点。
- 用轻量 `EvidenceBundle` 作为阶段边界，避免第二阶段重新做路径考古。
- 把 `needs_human` 明确为 HITL 暂停点，并继续支持同一 thread 上 resume。
- 让 `lint` 成为 DSL 阶段的自反馈回路，而不是全局混用工具。

**非目标：**
- 不修改 engine 的 DSL 结构或执行语义。
- 不引入厚重、全量、数据库式的中间证据模型。
- 不让 DSL 阶段重新获得 `search/list/read` 工具。

## 决策

### 决策 1：planner 主流程改为显式 graph，而不是继续扩充单体 agent
- 选择：使用 LangGraph 把 planner 建模为一条显式工作流，至少包含 `evidence_agent`、证据判断/HITL、`dsl_agent` 和 lint 修复/收口几个阶段。
- 理由：当前问题已经是状态机问题，而不只是 prompt 工程问题；显式 graph 更适合表达暂停、恢复、分预算和阶段日志。
- 替代方案：
  - 继续在单体 `create_agent()` 上追加 prompt 和 runtime 护栏。缺点是阶段边界始终是软约束。
  - 手写普通 while-loop 状态机。缺点是会丢掉现有 LangGraph 的 checkpointer 和 interrupt 语义。

### 决策 2：阶段边界使用轻量 `EvidenceBundle`
- 选择：中间产物只保留“证据小结 + 关键事实 + 缺口/假设 + 来源路径”，而不是把所有证据压成厚重 schema。
- 理由：过度结构化会让 `evidence_agent` 变成数据录入器；而完全不结构化又会让 `dsl_agent` 重复解释自然语言总结。
- 建议形态：
  - `summary`
  - `facts[]`，每项包含 `name`、`value_summary`、`source_paths`、`source_kind`
  - `missing_info`
  - `assumptions`
  - `ready_for_dsl`
- 替代方案：
  - 全结构化 Evidence 模型。缺点是僵硬且扩展成本高。
  - 纯自然语言摘要。缺点是 phase 2 难以稳定引用路径和做自动判断。

### 决策 3：`evidence_agent` 与 `dsl_agent` 工具严格分离
- 选择：
  - `evidence_agent` 只挂载 `search`、`list`、`read`
  - `dsl_agent` 只挂载 `lint`
- 理由：工具隔离是最强的阶段边界，能从 runtime 层阻止 `dsl_agent` 回头继续取证。
- 替代方案：
  - 让 `dsl_agent` 在必要时重新拿回 `search/list/read`。缺点是阶段边界再次塌陷。
  - 让 `evidence_agent` 也可直接产出 DSL。缺点是又回到当前混合模式。

### 决策 4：`needs_human` 在内部语义上是 interrupt/resume，不是终态
- 选择：graph 内部把 `needs_human` 视为 HITL 暂停点；对外仍保持 `PlannerResult(status=needs_human)` 兼容接口，但 runtime 必须把它实现为可恢复 continuation。
- 理由：用户已经明确希望 `needs_human` 表示“等人回来继续”，而不是“本轮就此结束”。
- 替代方案：
  - 保持 `needs_human` 只是普通返回值。缺点是恢复语义只能靠调用方补丁式拼接。

### 决策 5：`lint` 作为 `dsl_agent` 的内循环反馈器
- 选择：DSL 阶段允许 `draft -> lint -> repair -> lint` 的有限闭环，并配置独立 repair budget。
- 理由：`lint` 的最佳位置不是全局工具，而是 `dsl_agent` 的自我迭代反馈信号。
- 替代方案：
  - 仅在最终 ready 前调用一次 `lint`。缺点是会降低自修能力。
  - 把 `lint` 留在全局共享工具集中。缺点是职责边界不清。

## 风险 / 权衡

- [graph 重构范围较大] → 先做最小节点集和兼容层，避免一次性改写所有对外接口。
- [新增 `EvidenceBundle` 仍可能被设计得过重] → 明确只保留小结、事实、缺口、假设和路径，不承载全量世界模型。
- [两个 agent 间可能丢失上下文细节] → 在 `EvidenceBundle.summary` 中保留弹性文字摘要，同时保留关键 `source_paths`。
- [resume 语义迁移可能影响 smoke 与 HITL 脚本] → 先保持现有 `thread_id/resume` 外观兼容，再逐步下沉到 graph state。
- [阶段过多可能增加理解成本] → 第一版控制在最少必要节点，避免过度细分。

## Migration Plan

1. 定义 graph state 和轻量 `EvidenceBundle`。
2. 实现 `evidence_agent` 节点，产出 `EvidenceBundle` 或触发 HITL 暂停。
3. 实现 `dsl_agent` 节点及其 `lint` 修复回路。
4. 把 `needs_human` 映射为 graph interrupt/resume，同时保持现有对外结果接口兼容。
5. 更新 smoke、日志与测试，展示阶段信息和恢复后的继续执行。

## Open Questions

- `EvidenceBundle.facts` 是否需要支持“confirmed”与“candidate”两种证据强度，还是先只保留简短 `note` 即可？
- DSL 修复 budget 是否应独立配置，还是先复用 planner 统一配置下的默认值？
