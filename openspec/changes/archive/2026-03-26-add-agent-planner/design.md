## 上下文

当前代码库已经具备三块基础能力：

- `engine` 可校验并执行 `TaskDocument`
- `agent.tools.search` 可检索规则原文证据
- `agent.tools.fetch_keys` 可枚举状态路径

但仍缺少 planner 这一层，把 DM 自然语言指令稳定转换为可执行 `TaskDocument`。目前最突出的风险不是“模型不会推理”，而是“产物不稳定”：

- 关键步骤缺字段或 type/kind 非法，导致执行前校验失败
- 引用路径和规则依据不足，导致幻觉式 JSON
- 信息不足时没有统一 HITL 协议，导致调用方难以恢复

因此本变更需要定义一个明确的 planner 设计：证据驱动、可解释、可校验、可恢复。

## 目标 / 非目标

**目标：**
- 建立 planner 的结构化输入输出契约，统一接收 DM 指令并输出 `ready/needs_human/blocked`。
- 基于 LangChain Deep Agents（`deepagents`）搭建 planner 主循环与工具编排入口。
- 提供 planner factory，统一模型接入点与运行参数解析，避免多处重复配置。
- 定义 planner 的工具编排策略，明确 `search` 与 `fetch_keys` 在证据收集中的职责。
- 定义 LLM 主导不确定性判定与最小硬约束兜底的协作机制。
- 建立“Schema 结构约束 + 执行器语义校验”双层闭环，确保最终 `TaskDocument` 可执行。
- 明确 planner 与 engine 的边界，避免规划层直接执行状态变更。

**非目标：**
- 不在本次设计中实现完整 GUI 或 DM 交互前端。
- 不在本次设计中重写 engine 的步骤语义与执行协议。
- 不在本次设计中强制引入新检索/读值工具（如 `reads`），仅预留扩展位。
- 不在本次设计中直接手写完整的底层 LangGraph 节点编排以替代 Deep Agents 主流程。
- 不在本次设计中规定具体模型供应商或推理参数细节。

## 决策

### 决策: planner 主流程基于 Deep Agents 而非基础 agent loop

planner 第一版以 Deep Agents 作为运行与编排承载层，复用其规划能力、长流程管理和 HITL 友好能力。Deep Agents 底层运行在 LangGraph 上，满足后续需要时向底层扩展的空间。

考虑过的替代方案：
- 仅用 LangChain `create_agent`：起步快，但复杂多步规划和长期流程控制能力较弱。
- 直接以 LangGraph 从零编排：控制力最强，但第一版实现成本高，不利于快速落地 planner 主链路。

### 决策: 通过 planner factory 统一模型接入与运行配置

planner 需要统一的 factory 入口，集中处理模型与运行参数，包括 `model`、`base_url`、`api_key`、`timeout`、`max_retries`、`interrupt_on`。factory 还需定义稳定的配置覆盖优先级（调用参数 > 环境变量 > 默认值），避免不同调用点出现配置漂移。

考虑过的替代方案：
- 各调用点自行构造 Deep Agents：灵活但重复配置多，难以审计和测试。
- 全部依赖环境变量：接入简单，但缺少按请求覆写能力，不利于多租户/多模型场景。

### 决策: planner 输出采用三态协议而非自由文本

planner 输出必须为结构化三态：

- `ready`: 已生成可执行 `task_document`
- `needs_human`: 信息不足，返回结构化问题
- `blocked`: 系统故障或依赖不可用

这样调用方可以直接按状态分支处理，不必再解析自然语言。

考虑过的替代方案：
- 单一自然语言回复：实现快，但不可稳定自动化。
- 仅二态（ready/fail）：无法区分“需要人类澄清”和“系统故障”。

### 决策: 采用“LLM 主导判定 + 最小硬约束兜底”的 HITL 模式

是否触发 HITL 的核心判断由 LLM 完成，因为不确定性来源多且场景化；但系统保留最小硬约束（例如文档结构非法、关键实体无法唯一映射、关键工具连续失败），命中时禁止强行 `ready`。

考虑过的替代方案：
- 全硬编码触发策略：可控但覆盖不足，难适配复杂上下文。
- 完全无约束 LLM 判定：灵活但风险过高，容易输出不可执行文档。

### 决策: 规划流程采用“先取证再提问”

planner 必须先尝试 `search` 与 `fetch_keys`，在仍无法收敛时再进入 `needs_human`。这样可以减少不必要提问，并提升自动完成率。

考虑过的替代方案：
- 先问后查：会增加 DM 负担，且浪费已有工具能力。
- 始终不问：会导致高幻觉率和错误执行风险。

### 决策: `TaskDocument` 生成采用双层校验闭环

先用 JSON Schema 约束基础结构，再用 `validate_task_document` 约束执行语义（如引用合法性、步骤类型与 kind、语义字段约束）。校验失败应触发修复重试或转入 `needs_human`。

考虑过的替代方案：
- 仅依赖 prompt：无法保证稳定性。
- 只做语义校验：错误反馈过晚，修复成本更高。

### 决策: planner 保持纯规划职责，不直接提交状态写入

planner 只产出文档和解释信息，具体状态变化由 engine 在执行期提交。这样可以保持审计边界清晰，降低规划层副作用。

考虑过的替代方案：
- planner 直接执行一步到位：看似高效，但会破坏 engine 单一执行入口和可追溯性。

## 风险 / 权衡

- [LLM 判定不确定性可能漂移] → 用最小硬约束与校验闭环兜底，并输出 `missing_info/assumptions` 供审计。
- [仅靠 `fetch_keys` 不读值会增加 HITL 触发率] → 在契约中预留 `reads` 扩展位，后续渐进增强。
- [工具依赖失败会阻塞规划] → 通过 `blocked` 明确暴露故障并提供恢复建议。
- [Schema 与执行器规则可能重复维护] → 以执行器语义为最终真相，Schema 只负责前置结构约束。
- [规划回合过多导致时延上涨] → 为工具循环设置上限并在超限时转 `needs_human`。
- [多入口配置不一致导致行为漂移] → 强制通过 planner factory 构造实例，并统一优先级解析规则。

## Migration Plan

1. 新增 planner 规范与提案产物，固定协议与边界。
2. 在 `trpg_py.agent` 中引入基于 Deep Agents 的 planner 模块骨架，实现三态输出接口。
3. 新增 planner factory，统一模型接入参数和运行参数解析逻辑。
4. 集成 `search` 与 `fetch_keys` 形成最小取证循环。
5. 集成 JSON Schema 校验与执行器校验，打通修复闭环。
6. 增加 planner 行为测试（ready/needs_human/blocked、校验失败修复、工具失败分支）与 factory 配置解析测试。
7. 灰度接入调用方入口并观察 HITL 比例，评估是否引入 `reads`。

回滚策略：若 planner 行为不稳定，可回退到“人工构造 TaskDocument + engine 执行”流程；该回滚不会影响现有 engine/store/tool 能力。

## Open Questions

- planner 的上下文输入最小集合是什么（仅 DM 指令 + state provider，还是包含会话历史）？
- `needs_human.questions` 的字段粒度是否需要标准化（例如 question_id、why、options）？
- 规划回合上限、工具调用预算与超时策略应如何配置？
- `reads` 是否作为下一变更引入，还是在本变更中预留接口即可？
