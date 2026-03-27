## 新增需求

### 需求:planner 必须实现为显式的 LangGraph staged workflow
系统必须将 planner 主流程实现为显式的 LangGraph 工作流，而不是继续依赖单体 agent 在一次调用内同时完成取证、DSL 生产、修复和 HITL 协调。该工作流必须至少区分 `evidence_agent` 阶段和 `dsl_agent` 阶段。

#### 场景:planner 在 graph 中先取证后产出 DSL
- **当** 调用方发起一次新的规划请求
- **那么** planner 先进入 `evidence_agent` 阶段
- **那么** 在证据足够时 planner 再进入 `dsl_agent` 阶段
- **那么** 系统不得要求单一 agent 同时承担两个阶段的全部职责

### 需求:planner 必须使用两个独立的 create_agent 节点承担核心阶段
系统必须把信息获取和 DSL 生产/修复分别建模为两个独立的 `create_agent()` 节点，并统一命名为 `evidence_agent` 与 `dsl_agent`。`evidence_agent` 必须只挂载 `search`、`list`、`read`；`dsl_agent` 必须只挂载 `lint`，并且不得回头访问信息获取工具。

#### 场景:evidence_agent 只消费取证工具
- **当** planner 执行信息获取阶段
- **那么** `evidence_agent` 可以使用 `search`、`list`、`read`
- **那么** `evidence_agent` 不得调用 `lint`
- **那么** `evidence_agent` 输出证据中间产物或进入 HITL

#### 场景:dsl_agent 只消费 lint
- **当** planner 执行 DSL 生产或修复阶段
- **那么** `dsl_agent` 可以使用 `lint`
- **那么** `dsl_agent` 不得调用 `search`、`list`、`read`
- **那么** 系统通过 runtime 工具隔离维持阶段边界

### 需求:阶段间必须通过轻量 EvidenceBundle 传递证据
系统必须在 `evidence_agent` 阶段和 `dsl_agent` 阶段之间使用轻量 `EvidenceBundle` 传递证据。该中间产物必须至少包含证据小结、关键事实、缺口、假设以及来源路径；系统禁止要求该中间产物承载过度结构化的全量世界模型。

#### 场景:evidence_agent 输出轻量 EvidenceBundle
- **当** `evidence_agent` 完成一次证据收集
- **那么** 输出必须包含可读证据小结
- **那么** 输出必须包含关键事实及其来源路径
- **那么** 输出必须包含缺口和假设
- **那么** 输出必须指示是否已准备好进入 `dsl_agent` 阶段

#### 场景:dsl_agent 消费 EvidenceBundle 而不是原始工具回放
- **当** `dsl_agent` 开始生成或修复 `TaskDocument`
- **那么** `dsl_agent` 基于 `EvidenceBundle` 消费证据
- **那么** `dsl_agent` 无需重新解释原始 `search/list/read` 输出
- **那么** `dsl_agent` 仍能根据来源路径生成正确的 `$ref`

### 需求:needs_human 必须表示可恢复的 HITL 暂停
系统必须把 `needs_human` 视为 graph 内部的 HITL 暂停点，而不是 planner 工作流的终止。系统对外仍可返回 `status=needs_human`，但内部必须支持在同一 thread 或等价 graph state 上 resume 并继续后续阶段。

#### 场景:evidence_agent 在证据不足时暂停
- **当** `evidence_agent` 完成可用取证后仍存在关键缺口
- **那么** planner 触发 `needs_human`
- **那么** 该状态表示 HITL 暂停而不是终止
- **那么** 调用方可以在同一 thread 或等价 state 上恢复 graph

#### 场景:dsl_agent 在业务决策仍缺失时暂停
- **当** `dsl_agent` 发现证据虽足够取证但仍缺少必要人类决策
- **那么** planner 触发 `needs_human`
- **那么** graph 必须暂停在当前阶段上下文
- **那么** 恢复后系统继续同一条规划工作流，而不是重启整轮规划

### 需求:lint 必须驱动 dsl_agent 的自我迭代
系统必须允许 `dsl_agent` 把 `lint` 作为自反馈工具，用于在 ready 前对候选 `TaskDocument` 进行有限次数的自我修复。系统禁止把 `lint` 仅保留为全局末端校验，导致 `dsl_agent` 无法利用校验反馈迭代自身产物。

#### 场景:dsl_agent 根据 lint 反馈修复候选文档
- **当** `dsl_agent` 产出候选 `TaskDocument` 且 `lint` 返回非法结果
- **那么** 系统把该反馈回灌到 `dsl_agent`
- **那么** `dsl_agent` 可以在限定预算内重新生成或修复文档
- **那么** 若修复成功，planner 继续返回 `ready`

## 修改需求

### 需求:planner 必须显式区分 ready、needs_human 与 blocked
planner 必须以稳定状态语义区分三类规划结果：可直接执行、需要 DM 澄清、以及系统阻塞。系统禁止把这三类情况折叠为单一自由文本回复。对于 `needs_human` 与 `blocked`，系统还必须暴露可读的根因解释，禁止把内部校验失败或修复未收敛笼统伪装成“用户信息不足”。

#### 场景:信息不足时返回 needs_human
- **当** planner 在 `evidence_agent`、`dsl_agent` 或等价 graph 阶段判断关键信息不足或不确定性过高
- **那么** 返回 `status=needs_human`
- **那么** 返回体包含结构化澄清问题列表
- **那么** 该结果在内部语义上表示可恢复的 HITL 暂停，而不是工作流终止

### 需求:planner 必须先取证再触发 HITL
系统必须要求 planner 在触发 HITL 之前尽可能完成 `search` 和 `fetch_keys` 的取证尝试，避免因未检索或未枚举路径造成过早提问。

#### 场景:先取证后提问
- **当** DM 指令初看存在歧义
- **当** `evidence_agent` 完成可用工具取证后仍无法收敛到单一可执行方案
- **那么** planner 才触发 `needs_human`
- **那么** 提问内容基于 `EvidenceBundle` 中已获取的证据而非泛化追问

## 移除需求

无
