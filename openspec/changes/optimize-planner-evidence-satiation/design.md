## 上下文

当前 planner 已经具备 staged agent 结构、`search`/`grep`/`list`/`read` 取证工具链、`lint` 收口以及 `ready` / `needs_human` / `blocked` 状态语义。但从真实 smoke 行为看，evidence agent 在简单动作上仍倾向于继续扩展证据面，而不是在已经足够生成合法 `TaskDocument` 时及时停止。

这个问题当前主要体现为三种症状：
- 对单攻击者、单目标、单武器攻击这类高模板化动作，evidence agent 仍会重复查询基础规则、非关键状态或相似主题关键词，导致工具调用数偏高。
- `tool_budget_exhausted` 经常并非因为存在真实未解歧义，而是因为 evidence agent 在“已经足够”之后仍继续取证。
- smoke 流程中的 HITL 恢复次数被 evidence 过采样放大，测试员需要频繁 `approve` 才能继续。

这次设计的重点不是新增证据缓存，而是让 evidence agent 建立更强的“饱腹感”：它必须知道何时已经具备 DSL 最小闭包，并在该时刻停止继续取证。

## 目标 / 非目标

**目标：**
- 为 evidence agent 引入明确的 evidence sufficiency 判定，使其以“能否生成合法 `TaskDocument`”作为停机条件。
- 把 evidence 阶段的未知项分成阻塞 DSL 的 Required Gaps 与仅提升信心的 Optional Gaps。
- 为简单常见动作定义最小证据闭包，优先覆盖单体武器攻击场景。
- 约束工具调用只服务于闭合 Required Gaps，减少围绕相同主题的重复 `grep` / `search` / `read`。
- 让 `needs_human` 更接近“真实关键缺口仍未闭合”，而不是“预算耗尽”。

**非目标：**
- 不在本次设计中引入跨轮次 evidence cache 或持久化查询历史。
- 不修改 engine DSL 结构，也不引入新的执行器步骤类型。
- 不改变 `search`、`grep`、`list`、`read`、`lint` 工具本身的底层契约。
- 不承诺在所有复杂动作上都显著降低工具调用数，本次优先优化高频简单动作。

## 决策

### 决策 1：把 evidence stop criteria 定义为“DSL 最小闭包满足”，而不是“证据尽可能完整”

evidence agent 的完成条件将从模糊的“证据足够充分”收紧为“Required Gaps 已全部闭合，可以生成合法 `TaskDocument`”。一旦满足该条件，evidence agent 必须返回 `ready` + `evidence_bundle`，而不是继续补充更多规则段落、次要状态值或额外候选路径。

这样做的原因是，当前 evidence agent 的默认行为更接近“最大确定性”，但 planner 真正需要的是“足够生成 DSL”。如果不先把停机条件重新定义清楚，再多的 prompt 微调也容易继续滑向过采样。

考虑过的替代方案：
- 单纯增大 `tool_budget`：只能缓解预算耗尽，不能减少无效取证。
- 优先建设 evidence cache：能缓解 resume 后重复查询，但不能解决首轮就过量取证的问题。

### 决策 2：显式区分 Required Gaps 与 Optional Gaps，并要求工具调用只闭合 Required Gaps

设计将要求 evidence agent 在内部维护两个集合：
- Required Gaps：不补上就无法生成合法 `TaskDocument` 的未知项
- Optional Gaps：补上可以提升信心，但不影响生成的未知项

每次工具调用前后，agent 都应围绕“是否闭合了至少一个 Required Gap”进行自检。若调用只会补充 Optional Gaps，则默认不应执行。

这样做的原因是，当前 evidence agent 缺少统一的“还差什么”模型，导致它会把 actor HP、额外规则背景或同主题重复关键词与真正阻塞 DSL 的事实同等对待。

考虑过的替代方案：
- 只通过 prompt 文案强调“少查一点”：不够可操作，难以形成稳定停机行为。
- 只依赖 `tool_budget` 作为外部刹车：太晚，而且会把系统问题暴露成 HITL。

### 决策 3：为高频动作形态定义最小证据闭包，首批覆盖单体武器攻击

本次设计优先为“单攻击者对单目标的武器攻击”定义明确的最小证据闭包。对这一类动作，Required Gaps 至少包括：
- attacker identity
- target identity
- attack modifier / `to_hit`
- target AC
- damage dice / bonus / damage type

一旦这些关键事实已经确认，evidence agent 必须停止进一步的基础规则搜索或非关键状态确认。nat20 / critical 语义应优先依赖现有 planning pattern 与系统 prompt 中的既有约束表达，而不是在每次简单武器攻击上重复搜索。

这样做的原因是，简单攻击是目前 smoke 中最高频、也最容易暴露“胡吃海塞”问题的场景。先把高频动作模板收紧，比试图一次性为所有动作建立通用完美规则更容易落地和验证。

考虑过的替代方案：
- 一次性为所有动作形态建立完整 Required Gap 模板：范围过大，难以快速验证收益。
- 完全不做动作分类，只靠通用启发式：在简单攻击场景下仍可能不够收敛。

### 决策 4：通过 few-shot 示例教会 evidence agent“何时已经足够”

除了补充原则性 prompt 约束外，设计将通过 evidence stage 的 few-shot 示例明确示范“什么叫证据已经足够”。这些示例至少应覆盖三类情况：
- 简单单体武器攻击在关键事实齐全后立即返回 `ready`
- 仍存在 Required Gaps 时继续取证
- 工具已经无法继续消歧时直接返回 `needs_human`

few-shot 的重点不是单纯展示工具调用顺序，而是显式展示：
- 当前动作形态
- Required Gaps / Optional Gaps 的划分
- 为什么当前调用能够闭合关键缺口
- 为什么当前阶段应该停止而不是继续补充背景信息

这样做的原因是，当前 evidence agent 已经被 prompt 充分教会“如何调用工具”，但没有被足够清楚地教会“什么时候应该停止”。few-shot 可以把“关键缺口清空后必须停”的行为模式具体化，减少模型继续朝“再补一点更稳”滑移。

考虑过的替代方案：
- 只增加抽象规则描述，不提供示例：约束方向正确，但模型更容易在复杂提示中退回保守过采样习惯。
- 只依赖代码侧停止逻辑，不改 prompt：能够提供兜底，但难以减少前期无效调用。

### 决策 5：把 `search` 从简单动作的默认动作收缩为兜底动作

在简单动作上，状态取证优先级应调整为：
1. 用 `grep` 发现关键候选路径
2. 用一次批量 `read` 确认关键当前值
3. 仅当仍存在规则型 Required Gap 时才触发 `search`

`search` 继续保留为规则证据工具，但不再被视为“只要涉及攻击就默认先搜一轮规则”的动作。

这样做的原因是，当前 system/user prompt 对 `search` 的强调过强，容易把已被 planning pattern 覆盖的基础规则再次外部检索，从而放大不必要调用。

考虑过的替代方案：
- 完全禁止 `search`：会让复杂规则动作失去必要兜底。
- 保持 `search` 默认优先级不变，仅靠 budget 压制：仍然容易在简单动作上浪费调用。

### 决策 6：把 over-collection 视为 planner 级错误倾向，并通过停止规则提前终止

设计将把以下信号视为 over-collection：
- 已有 canonical DSL 所需关键状态后仍继续搜索基础 attack / critical 规则
- 围绕同一 Required Gap 用不同关键词重复 `grep`
- 读取明显不阻塞 DSL 的状态值，只为“顺便确认”
- 连续两次工具调用都没有减少 Required Gaps

当出现这些信号时，planner 应优先：
- 若 Required Gaps 已清空，则直接返回 `ready`
- 若仍存在真实关键歧义，则返回 `needs_human`

这样做的原因是，预算本身不应成为 evidence 阶段的主要停机装置。更合理的做法是让 planner 在“开始胡吃海塞”时主动收束，而不是等到 budget 中间件报错后才暴露问题。

考虑过的替代方案：
- 完全依赖 prompt 自觉避免 over-collection：缺少稳定可测试边界。
- 只在 budget 用尽时做 forced finalize：能够减轻 HITL，但无法减少前面的浪费调用。

## 风险 / 权衡

- [把 stop criteria 收得过紧可能让复杂动作过早停止] → 首批只为简单高频动作建立明确闭包，并保留复杂动作继续使用现有兜底路径。
- [Required / Optional Gaps 分类若定义不清，可能引入新的误判] → 在规格中为高频动作给出明确场景，并通过 smoke/单测验证最小闭包是否足够。
- [降低 `search` 默认优先级后，模型可能过度依赖已有 prompt 常识] → 只在 simple attack pattern 中收缩 `search`，对仍有规则型 Required Gap 的场景继续允许兜底检索。
- [“连续两次未缩小 Required Gaps 就停止”可能对个别复杂路径过于激进] → 先把它定义为 over-collection 信号而非绝对硬门槛，允许在复杂动作中结合 gap 类型判断。

## Migration Plan

1. 先更新 `agent-planner` 规范，补充 evidence sufficiency、Required/Optional Gaps、simple attack minimal closure 和 over-collection 相关需求。
2. 再调整 planner prompt 与 evidence stage 决策逻辑，使其显式围绕 Required Gaps 组织取证顺序和停机条件。
3. 为 evidence stage 加入 sufficiency-focused few-shot，明确示范“关键缺口闭合后立即停止”“关键缺口未闭合时继续取证”“无法消歧时返回 needs_human”。
4. 为简单单体武器攻击补充针对性 smoke/单测，验证工具调用数与 `needs_human` 次数下降。
5. 根据验证结果再决定是否把同样的 stop criteria 模板扩展到 spell attack、save-based effect 等动作形态。

回滚策略：若 stop criteria 导致 planner 过早结束并频繁产出不合法文档，可先回退到仅添加观测与 prompt 约束的版本，同时保留规格中的 gap taxonomy 作为后续迭代基础。

## Open Questions

- Required Gaps 是否需要出现在 debug / planner logs 中，便于开发者定位 evidence agent 为什么继续或停止？
- 对 spell attack、save-based spell、resource consume 这类动作，最小闭包应该分批扩展还是先维持通用兜底？
- `search` 降级为 simple attack 兜底动作后，是否还需要在 prompt 中保留“Always use search and grep before asking the DM”这类强措辞？
- evidence few-shot 是否需要同时包含 over-collection 反例，以减少模型把“继续搜索基础规则”误判为稳健行为？
