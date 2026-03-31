## 新增需求

### 需求:planner evidence 阶段必须以 DSL 最小闭包作为停止条件
系统必须要求 planner 的 evidence agent 以“是否已经具备生成合法 `TaskDocument` 的最小证据闭包”作为停止条件，而不是继续追求最大确定性。只要剩余未知项不再阻塞合法 DSL 生成，planner 就必须停止继续取证并返回 `status=ready` 的 evidence 结果。

#### 场景:关键缺口已闭合时立即停止取证
- **当** evidence agent 已经确认生成当前动作所需的全部关键状态和规则事实
- **那么** planner 必须停止继续调用 `search`、`grep`、`list` 或 `read`
- **那么** planner 必须返回带 `evidence_bundle` 的 `status=ready`
- **那么** planner 不得仅因还可以补充更多背景信息而继续停留在 evidence 阶段

#### 场景:仅剩非阻塞未知项时仍可进入 DSL 阶段
- **当** evidence agent 仍存在少量未知项
- **当** 这些未知项不会阻止生成合法 `TaskDocument`
- **那么** planner 必须将这些未知项视为非阻塞项
- **那么** planner 必须停止继续取证并进入 DSL 阶段

### 需求:planner evidence 阶段必须显式区分 Required Gaps 与 Optional Gaps
系统必须让 planner evidence 阶段把未知项区分为阻塞合法 `TaskDocument` 生成的 Required Gaps 与仅提升信心的 Optional Gaps。工具调用必须优先且主要用于闭合 Required Gaps，禁止把 Optional Gaps 当成持续取证的默认理由。

#### 场景:工具调用用于闭合 Required Gaps
- **当** evidence agent 准备执行下一次工具调用
- **那么** 该调用必须对应至少一个当前未闭合的 Required Gap
- **那么** planner 不得为了只补充 Optional Gaps 而继续默认调用工具

#### 场景:Optional Gaps 不得单独触发 needs_human
- **当** 所有 Required Gaps 已闭合
- **当** 仍存在只影响信心而不影响 DSL 生成的 Optional Gaps
- **那么** planner 不得仅因为这些 Optional Gaps 而返回 `status=needs_human`
- **那么** planner 必须继续生成 evidence 结果并进入 DSL 阶段

### 需求:planner 必须为简单单体武器攻击使用最小证据闭包
系统必须为“单攻击者对单目标的武器攻击”建立明确的最小证据闭包。对于该类动作，planner 必须把攻击者身份、目标身份、攻击修正或 `to_hit`、目标 AC 以及伤害构成（骰子、加值、伤害类型）视为关键缺口；在这些关键事实全部确认后，planner 必须停止继续补充基础攻击规则或非关键状态。

#### 场景:简单武器攻击在关键事实齐全后直接 ready
- **当** DM 指令可解析为单攻击者对单目标的武器攻击
- **当** planner 已确认攻击者、目标、`to_hit`、目标 AC 和伤害构成
- **那么** planner 必须把 evidence 视为足够
- **那么** planner 必须返回 `status=ready` 的 evidence 结果

#### 场景:简单武器攻击不为非关键状态继续取证
- **当** 简单单体武器攻击的关键事实已经确认
- **当** planner 尚未确认攻击者 HP、目标 HP、攻击者 AC 或其他非关键状态
- **那么** planner 不得仅为这些非关键状态继续默认调用工具
- **那么** planner 不得仅因这些非关键状态未确认而返回 `status=needs_human`

### 需求:planner 必须将 search 作为简单动作的规则兜底而非默认动作
系统必须要求 planner 在简单高频动作上优先通过 `grep` 与批量 `read` 闭合状态型关键缺口，而不是默认把 `search` 作为起手动作。只有当当前 Required Gaps 中仍存在无法由既有 planning pattern 或状态取证闭合的规则型缺口时，planner 才能继续调用 `search`。

#### 场景:简单攻击优先状态取证
- **当** DM 指令属于简单单体武器攻击
- **那么** planner 必须优先使用 `grep` 发现候选路径
- **那么** planner 必须优先使用批量 `read` 确认关键当前值
- **那么** planner 不得在状态关键缺口尚未收敛前默认先调用 `search`

#### 场景:存在规则型关键缺口时允许 search 兜底
- **当** planner 已完成关键状态取证
- **当** 当前仍存在阻塞 DSL 生成的规则型 Required Gap
- **那么** planner 可以调用 `search` 作为兜底规则取证
- **那么** `search` 的使用必须服务于闭合该规则型关键缺口

### 需求:planner 必须把 over-collection 视为停止信号而不是默认延续理由
系统必须要求 planner 识别并抑制 over-collection。若连续工具调用没有缩小 Required Gaps，或新调用只会补充背景信息、重复主题查询或非关键状态，planner 必须优先停止 evidence 阶段，而不是继续围绕同一主题试探直到预算耗尽。

#### 场景:重复查询未缩小关键缺口时停止
- **当** planner 已连续执行多次工具调用
- **当** 最近的工具调用没有减少当前动作的 Required Gaps
- **那么** planner 必须把该状态视为 over-collection 信号
- **那么** planner 必须优先转入 `ready` 或 `needs_human`，而不是继续默认调用更多工具

#### 场景:预算耗尽前先因过采样信号收束
- **当** planner 已出现重复主题查询、非关键状态扩张或无效规则补充等 over-collection 信号
- **那么** planner 不得把 `tool_budget` 当作唯一停止机制
- **那么** planner 必须在预算耗尽前优先尝试收束 evidence 阶段

## 修改需求

### 需求:planner 必须在提问前优先完成可用工具取证
系统必须要求 planner 在触发 HITL 之前尽可能完成 `search`、`grep`、必要时的 `list` 以及必要的批量 `read` 取证尝试，避免因未检索、未发现候选路径或未读取关键值造成过早提问。对于 `grep`、`list` 或 `read` 已明确返回 `status=no_match` 的事实，planner 必须把它视为“当前 state 中没有对应路径或值证据”的信号。若 `grep` 无命中，planner 可以回退到 `list` 做有限补充导航；若 `list` 或 `read` 已给出建议路径，planner 仅可沿建议做有限修正，而不得机械重复原失败请求。对于已经闭合全部 Required Gaps 的场景，planner 必须直接停止取证并进入 DSL 阶段，而不是继续补充仅影响信心的 Optional Gaps。

#### 场景:先 grep/read 取证后提问
- **当** DM 指令初看存在歧义
- **当** planner 仍可通过 `grep`、`list` 或批量 `read` 获取更多状态证据
- **那么** planner 必须先完成这些取证尝试
- **那么** 只有工具取证后仍无法收敛到单一可执行方案时才触发 `needs_human`

#### 场景:grep 无命中后回退 list
- **当** planner 使用 `grep` 检索状态路径且返回 `status=no_match`
- **那么** planner 可以回退到 `list` 观察某个已知范围下的结构
- **那么** planner 不得围绕同一关键词主题无限重复 `grep`

#### 场景:no_match 经过有限修正后仍失败
- **当** `grep`、`list` 或 `read` 返回 `status=no_match`
- **当** planner 已做过一次有限补充检索或建议修正仍未找到所需事实
- **那么** planner 必须把该事实视为当前 state 缺失
- **那么** planner 不得继续围绕原主题无限试探

#### 场景:关键缺口已闭合时不再继续取证
- **当** planner 已经通过 `grep`、`list`、`read` 或必要的 `search` 闭合了当前动作的全部 Required Gaps
- **那么** planner 必须停止继续调用这些取证工具
- **那么** planner 必须直接进入 DSL 阶段而不是为 Optional Gaps 继续默认取证
