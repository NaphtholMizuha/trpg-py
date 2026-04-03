# planner-langgraph-workflow 规范

## 目的
定义基于 LangGraph 的 planner 主工作流，以及 task/dsl 两阶段节点的职责边界、提示词约束与中间对象契约，确保任务理解、DSL 生成和后续执行链路之间有稳定可验证的协作关系。
## 需求
### 需求: planner 必须使用 LangGraph 作为 workflow 编排真相
系统必须在 `src/augury/planner/workflow.py` 中使用 LangGraph 编排新的 planner workflow，禁止继续以普通顺序函数作为新的 planner 主入口真相。

#### 场景:调用方创建新的 planner workflow
- **当** 调用方需要实例化新的 planner workflow
- **那么** 可以从 `src/augury/planner/workflow.py` 获取基于 LangGraph 构造的 workflow 入口
- **那么** 该入口必须以内建图状态流转的方式串联两个阶段节点

### 需求: task 节点核心必须由 langchain.create_agent 驱动
系统必须要求 `src/augury/planner/nodes/task_node.py` 的核心执行体由 `langchain.create_agent` 创建的 agent 驱动，禁止只保留手写占位函数作为最终实现。

#### 场景:task 节点处理 DM 指令
- **当** 第一阶段节点接收到一条 DM 指令
- **那么** 节点必须通过 `langchain.create_agent` 产出的 agent 执行核心推理
- **那么** 节点必须输出可供下一个节点消费的结构化自然语言任务稿

### 需求: 第一阶段节点必须输出 TaskDraft 而不是受限动作分类
系统必须要求第一阶段节点输出 `TaskDraft` 一类的结构化自然语言任务稿，禁止把中间表示收窄为受限的动作类型标签作为主要输出真相。

#### 场景:task 节点生成任务稿
- **当** 第一阶段节点完成对 DM 指令的理解
- **那么** 产出的中间对象必须写明要完成什么任务
- **那么** 产出的中间对象必须写明读取哪些值、基于哪些值做什么判定以及最终写回哪些值
- **那么** 当必要信息不足时必须显式列出 `missing_info`
- **那么** 产出的中间对象必须允许通过 `evidence` 字段携带供下游消费的摘要化证据
- **那么** 产出的中间对象不得继续保留 `read_values`
- **那么** 产出的中间对象必须使用 `states` 表达状态证据，而不是继续使用 `context_lines`

### 需求: dsl 节点核心必须由 langchain.create_agent 驱动
系统必须要求 `src/augury/planner/nodes/dsl_node.py` 的核心执行体由 `langchain.create_agent` 创建的 agent 驱动，禁止绕过 agent 直接把中间对象硬编码成最终 DSL 作为最终实现。

#### 场景:dsl 节点生成 TaskDocument
- **当** 第二阶段节点接收到第一阶段产出的中间对象
- **那么** 节点必须通过 `langchain.create_agent` 产出的 agent 执行核心推理
- **那么** 节点必须输出可被 lint 或执行链路直接消费的 TaskDocument DSL
- **那么** 节点必须把第一阶段的任务稿当作主要输入来源，而不是重新把原始 DM 指令当作唯一真相
- **那么** 节点必须继续通过 `response_format=TaskDocumentSchema` 提交最终结构化结果
- **那么** 系统不得为了修复当前问题移除 `dsl_node` 的结构化输出协议
- **那么** 节点生成的步骤类型与步骤 kind 必须限定在当前 engine 支持的 DSL 词表内
- **那么** 节点不得发明引擎不支持的高层 workflow 术语作为 step type 或 kind

#### 场景:dsl 节点消费模板化 lint 诊断
- **当** `dsl_node` 获得 `lint` 返回的结构化 issues
- **那么** 节点必须能够消费其中的模板化诊断信息，而不只把 `message` 当成普通字符串
- **那么** 节点必须把这些模板化诊断视为生成或修正 DSL 的约束依据之一

#### 场景:dsl 节点以 lint valid 作为最终目标
- **当** `dsl_node` 生成最终 `TaskDocument`
- **那么** 节点必须把“返回当前 lint 视角下的 valid 结果”视为默认目标
- **那么** 节点不得把已经被 `lint` 判为 invalid 的 candidate 当作理想最终状态

#### 场景:dsl 节点把 lint 作为提交前检查
- **当** `dsl_node` 从 `TaskDraft` 生成候选 `TaskDocument`
- **那么** 节点必须把 `lint` 视为提交前检查工具，而不是纯可选附属工具
- **那么** 节点的默认成功标准必须是输出当前 `lint` 视角下的 `valid` TaskDocument`
- **那么** 节点必须为 agent 提供有限的 `lint` 工具调用预算，以支持受控的再次校验

#### 场景:dsl 节点不应把 lint invalid 当作理想终态
- **当** `dsl_node` 已经拿到某个 candidate 的 `lint invalid` 结果
- **那么** 节点不得把该 candidate 视为理想最终答案
- **那么** 节点必须至少把该结果作为继续修正或重新生成时的约束依据

#### 场景:dsl 节点提供 fallback lint
- **当** `dsl_node` 最终没有从 agent 响应中获得 `lint` 结果
- **那么** 节点必须执行至少一次 fallback lint
- **那么** 节点必须把 fallback 是否触发记录到可观察元数据中

#### 场景:dsl 节点根据 lint 结果修复候选文档
- **当** `dsl_node` 的首轮候选 `TaskDocument` 未通过 lint
- **那么** repair 回路必须保持在 `dsl_node` 内部，由 agent 以 ReAct/tool-use 形式调用 `lint`
- **那么** 系统不得为了 repair 新增外层 LangGraph 节点或新的 planner 阶段
- **那么** 节点必须能够读取当前 candidate 和对应的结构化 lint issues
- **那么** 节点必须在有限预算内尝试修复该 candidate，而不是只能返回首轮失败结果
- **那么** 节点提示词必须明确约束 `lint` 的调用次数和停止条件
- **那么** 节点在 repair 阶段应尽量保留已合法的步骤，而不是无谓重写整份文档

### 需求: workflow 必须以显式中间对象在两个 agent 节点之间传递状态
系统必须在 LangGraph workflow 的状态对象中显式保存第一阶段产出的中间对象，禁止让第二阶段节点只依赖原始 DM 指令或自由文本重新开始理解任务。

#### 场景:workflow 从 task 节点流转到 dsl 节点
- **当** workflow 收到第一阶段节点结果
- **那么** 它必须把该结果作为显式状态字段传给第二阶段节点
- **那么** 第一阶段结果必须能够表达任务稿本身以及供后续阶段消费的 `evidence`
- **那么** 第一阶段结果必须能够表达供后续阶段消费的 `states`
- **那么** 第二阶段节点无需从零重新解析原始 DM 指令

### 需求: 两个 agent 节点必须具有不同的工具边界
系统必须对两个 agent 节点施加不同的 tools 边界：第一阶段节点负责任务理解与上下文获取，第二阶段节点负责 DSL 翻译与校验，禁止默认让两个节点共享完全相同的工具集合。

#### 场景:workflow 装配两个节点
- **当** workflow 装配 task 节点与 dsl 节点
- **那么** task 节点必须作为单一 agent 自主使用受限的上下文收集工具集合完成检索与任务起草
- **那么** task 节点的默认工具边界应服务于生成合适的任务上下文，而不是暴露单独的 query planning 阶段
- **那么** task 节点禁止默认获得 `read` 权限
- **那么** dsl 节点必须获得面向 DSL 生成与校验的工具集合
- **那么** dsl 节点生成候选 DSL 时必须能够消费 lint 级错误反馈，而不是只看到单一模糊失败摘要

### 需求:task_node 必须把关键规则或状态证据以摘录形式写入 evidence
系统必须要求 `task_node` 在 rule-first 或需要后续阶段理解规则结构的任务中，把它抓取到且认为有用的关键规则或状态证据写入 `TaskDraft.evidence`。系统禁止把长段规则原文直接复制进 `evidence`，也禁止完全不暴露支持关键 judgments 的证据摘要。

#### 场景:范围法术需要下游识别 AoE targeting
- **当** `task_node` 处理如“`Aldera用火球术攻击goblin`”这类规则型任务
- **那么** `evidence` 必须能够提供足以让后续阶段发现范围判定的摘要线索
- **那么** 这些线索可以包括范围类型、豁免类型、伤害结算方式或当前目标与法术规则的关系
- **那么** `evidence` 不得只是整段 search 原文复制

#### 场景:状态证据也可进入 evidence
- **当** `task_node` 抓取到对后续结构推断有帮助的关键状态事实
- **那么** 它可以把这些事实以摘录形式放入 `evidence`
- **那么** 后续阶段无需只依赖 `task` 或 `judgments` 的 prose 才能理解这些关键状态前提

### 需求:task_node 必须为具名法术绑定默认施法环级
系统必须要求 `task_node` 在处理已明确法术名称的任务时，先确认法术身份与默认施法环级，再绑定对应的资源路径。系统禁止在没有升环依据时，把法术默认绑定到任意可用法术位。

#### 场景:Fireball 默认绑定法术本身环级
- **当** `task_node` 处理如“`Aldera用火球术攻击goblin`”这类具名法术任务
- **那么** prompt 必须要求先确认 `Fireball` 对应的法术身份
- **那么** prompt 必须要求读取施法者已知或已准备法术所在的默认环级
- **那么** 如果指令没有明确升环依据，`TaskDraft` 必须默认绑定该法术本身的环级资源，而不是任意较低或较高法术位

#### 场景:无法确认默认环级时显式暴露缺口
- **当** `task_node` 已确认法术身份
- **并且** 当前状态无法确认该法术在施法者身上的默认环级或可用资源路径
- **那么** `TaskDraft` 必须把该缺口写入 `missing_info`
- **那么** `TaskDraft` 不得假装已经安全绑定某个 `spell_slots.level_n.current`

### 需求:task_node 必须把范围覆盖判定纳入范围法术任务结构
系统必须要求 `task_node` 在 AoE / burst / line / cone 等范围效果任务中，把覆盖判定视为任务结构的一部分。系统禁止把范围法术直接降格成“对单个宾语对象做一次豁免和伤害结算”的单体任务。

#### 场景:Fireball 任务先判定覆盖对象再逐个结算
- **当** `task_node` 处理 `Fireball`、`Lightning Bolt` 或其他具名范围法术任务
- **那么** `TaskDraft.task` 或 `judgments` 必须先表达施法距离、爆点或覆盖范围、以及受影响对象集合的判定
- **那么** `TaskDraft` 必须把“对每个受影响对象进行豁免和伤害结算”作为后续步骤
- **那么** `TaskDraft` 不得只把宾语实体直接当作唯一受影响对象，除非当前状态已明确只有该对象被覆盖

#### 场景:覆盖范围无法确认时保留不确定性
- **当** `task_node` 处理范围法术任务
- **并且** 当前状态不足以确认爆点、覆盖范围或受影响对象集合
- **那么** `TaskDraft` 必须将该缺口写入 `missing_info`
- **那么** `TaskDraft` 不得输出看似完整的单目标结算计划来掩盖这一不确定性

### 需求:task_node 的 few-shot 必须展示位置获取且不得复用 Fireball 评测样例
系统必须要求 `task_node` prompt 中的 few-shot 用约 5-6 个任务类型原型覆盖主要任务结构，并在范围效果示例里显式展示位置获取步骤。系统禁止直接把 `Fireball` 写入 few-shot 作为示例，以避免 smoke 与评测样例失真。

#### 场景:few-shot 覆盖主要任务类型原型
- **当** `task_node` prompt 使用 few-shot 教模型处理 TRPG 任务
- **那么** few-shot 必须覆盖约 5-6 个任务类型原型
- **那么** 这些原型至少必须包括单体攻击、单体法术、范围法术、治疗或增益、状态或条件效果、纯状态查询中的主要类别
- **那么** each few-shot 的目的必须是教模型识别任务结构与检索顺序，而不是记忆某一个评测题目的固定答案

#### 场景:范围效果 few-shot 展示位置前提
- **当** `task_node` prompt 使用 few-shot 教模型处理范围效果任务
- **那么** few-shot 必须显式展示读取 actor / target 位置、再判断覆盖关系或暴露缺口的过程
- **那么** few-shot 不得只展示 save / hp / spell slot 绑定而省略位置前提

#### 场景:Fireball 仅作为测试和 smoke 样例
- **当** 系统需要通过 few-shot 教模型学习范围任务模式
- **那么** few-shot 不得直接使用 `火球术 Fireball` 作为示例
- **那么** `Fireball` 可以继续保留在 smoke 与测试中，作为对真实泛化行为的评测样例

### 需求:TaskDraft 必须通过 evidence 与 states 暴露法术环级和范围前提
系统必须要求范围法术相关的 `TaskDraft` 在 `evidence` 与 `states` 中同时暴露支撑任务结构的关键规则与状态证据。系统禁止只暴露 save / hp 路径，而隐藏法术环级和位置前提。

#### 场景:Fireball 暴露法术环级与位置前提
- **当** `task_node` 成功生成 `Fireball` 任务稿
- **那么** `evidence` 必须能够摘录 `Fireball` 的范围类型、豁免类型和伤害结算摘要
- **那么** `states` 必须能够暴露施法者法术位资源、施法者位置、目标位置或其他范围判定前提中实际使用的状态证据
- **那么** smoke 和测试必须可以观察这些证据，而不是只能看到 `spell_dc`、`hp` 与 `dex save`

### 需求:task_node prompt 必须明确指导 agent 使用 grep
系统必须要求 `task_node` 的 prompt 明确指导 agent 如何更好地使用 `grep`，禁止继续只依赖抽象高层描述让 agent 自由摸索。

#### 场景:task_node 需要从状态中发现实体与资源
- **当** `task_node` 处理需要使用 `grep` 的 instruction
- **那么** prompt 必须说明如何从自然语言实体、物品、法术或资源构造更合适的 `grep` 查询
- **那么** prompt 必须说明如何消费 `grep` 返回的 `key`、`value` 和 `sim`
- **那么** prompt 必须说明哪些低相关命中不应进入最终 `context_lines`

#### 场景:task_node prompt 使用 few-shot
- **当** `task_node` prompt 需要帮助 agent 学会稳定使用 `grep`
- **那么** prompt 可以包含 few-shot 示例
- **那么** few-shot 必须展示从 instruction 到 `grep` 使用再到任务稿取舍的代表性过程

### 需求:task_node prompt 必须采用 judgment-first 顺序
系统必须要求 `task_node` 的 prompt 明确采用 judgment-first 的内部顺序，禁止继续让 `judgments`、`reads`、`writes` 平行自由生成。

#### 场景:规则驱动任务生成 TaskDraft
- **当** `task_node` 处理法术、状态效果、豁免、反应或其他规则驱动任务
- **那么** prompt 必须先要求 agent 判断是否需要 search
- **那么** 如果需要，prompt 必须要求先 search，再形成 judgments
- **那么** prompt 必须要求 reads、writes、missing_info 和 assumptions 都围绕 judgments 再由 grep 绑定或补缺

#### 场景:根据 judgments 派生 reads 与 writes
- **当** `task_node` 已经形成 judgments
- **那么** prompt 必须要求 reads 覆盖 judgments 中声明的判定所需值
- **那么** prompt 必须要求 writes 覆盖 judgments 中声明的状态变更
- **那么** 无法绑定到 exact path 的部分必须进入 missing_info 或 assumptions，而不是直接猜测

### 需求:task_node prompt 必须为规则检索选择查询模式
系统必须要求 `task_node` 在规则优先任务中调用 `search` 前，先判断当前任务是否存在明确规则术语，并在 `term`、`balanced`、`semantic` 三种查询模式中选择其一。系统禁止继续把所有规则检索都统一改写为 HyDE 风格自然语言查询。

#### 场景:存在明确规则术语且只需定位条目
- **当** `task_node` 处理包含明确规则术语的规则优先任务，且当前只需要确认规则条目身份
- **那么** prompt 必须引导 agent 选择 `term` 模式
- **那么** query 必须保留规则术语原词
- **那么** query 禁止被改写成宽泛的规则场景描述

#### 场景:存在明确规则术语且需要少量结算细节
- **当** `task_node` 处理包含明确规则术语的规则优先任务，且当前 judgments 还需要少量结算信息
- **那么** prompt 必须引导 agent 选择 `balanced` 模式
- **那么** query 必须保留规则术语锚点
- **那么** query 只能补充当前 judgments 真正需要确认的少量规则点

#### 场景:不存在可靠规则术语锚点
- **当** `task_node` 处理规则优先任务，但指令或 judgments 中没有可靠的规则术语锚点
- **那么** prompt 必须引导 agent 选择 `semantic` 模式
- **那么** query 可以使用中文自然语言描述规则场景
- **那么** agent 不得假装已经确认某个具体规则名称

### 需求:task_node prompt 必须区分规则身份证据与结算证据
系统必须要求 `task_node` 在消费 search 结果时区分“规则身份定位”与“规则结算理解”两类证据，禁止把语义相似但身份不明的规则命中直接当作目标规则本体。

#### 场景:术语命中用于确认规则身份
- **当** `task_node` 使用 `term` 或 `balanced` 模式命中了与术语锚点一致的规则条目
- **那么** prompt 必须引导 agent 优先将该结果视为规则身份证据
- **那么** agent 不得让其他仅语义相似的结果轻易覆盖该规则身份

#### 场景:语义命中只用于补充结算细节
- **当** `task_node` 使用 `semantic` 模式，或在 `balanced` 模式下获得更多语义相关结果
- **那么** prompt 必须引导 agent 将这些结果主要用于补充结算细节
- **那么** 如果规则身份仍不明确，agent 必须保守处理并把不确定性留在 `missing_info` 或 judgments 之外
