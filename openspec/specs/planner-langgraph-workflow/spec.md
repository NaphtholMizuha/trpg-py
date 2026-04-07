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

### 需求:第一阶段节点必须输出 TaskDraft 而不是受限动作分类
系统必须要求第一阶段节点输出 `TaskDraft` 一类的结构化自然语言任务稿，禁止把中间表示收窄为受限的动作类型标签作为主要输出真相。

#### 场景:task 节点生成任务稿
- **当** 第一阶段节点完成对 DM 指令的理解
- **那么** 产出的中间对象必须写明要完成什么任务
- **那么** 产出的中间对象必须写明读取哪些值、基于哪些值做什么判定以及最终写回哪些值
- **那么** 当必要信息不足时必须显式列出 `missing_info`
- **那么** `missing_info` 不得包含未来由 engine 计算的随机结果

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
- **那么** 节点必须能够调用 `template` 工具查询当前任务族的合法 DSL 骨架

#### 场景:dsl 节点以 template 作为合法骨架来源
- **当** `dsl_node` 需要为某类任务生成候选 `TaskDocument`
- **那么** 节点必须先识别当前任务属于哪一类高频任务族
- **那么** 节点必须优先调用 `template` 工具获取对应 DSL 骨架
- **那么** 节点不得继续仅依赖 prompt 中内联的大段模板手册自行发明 DSL 结构

#### 场景:dsl 节点同时使用 template 和 lint
- **当** `dsl_node` 已获得 `template` 返回的 DSL 骨架
- **那么** 节点必须基于该骨架填充实例参数
- **那么** 节点仍必须在提交前调用 `lint`
- **那么** `template` 不得替代 `lint` 的最终守门职责

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
- **那么** dsl 节点默认工具集合必须包含 `template`

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
系统必须要求 `task_node` prompt 中的 few-shot 仅在确有必要时作为辅助示例，用于展示如何发现关键前提、绑定状态证据和暴露缺口。系统禁止继续把“覆盖约 5-6 个任务类型原型”作为默认硬要求。系统仍然禁止直接把 `Fireball` 写入 few-shot 作为示例，以避免 smoke 与评测样例失真。

#### 场景:few-shot 作为可选辅助而非主入口
- **当** `task_node` prompt 使用 few-shot 教模型处理 TRPG 任务
- **那么** few-shot 可以只覆盖少量高价值代表性过程
- **那么** few-shot 的主要目的必须是示范如何识别前提、取证和暴露缺口
- **那么** few-shot 不得被规定为必须覆盖固定数量的任务类型原型

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
系统必须要求 `task_node` 的 prompt 以 `judgments` 为核心组织 `TaskDraft`，并让 reads、writes、missing_info 与 assumptions 围绕执行需求和证据缺口派生。系统禁止继续把固定的分类步骤、固定的 search 仪式或平行自由生成当作默认主流程。

#### 场景:规则驱动任务生成 TaskDraft
- **当** `task_node` 处理法术、状态效果、豁免、反应或其他规则驱动任务
- **那么** prompt 必须允许模型先形成 provisional judgments，再决定是否需要 search 或 grep
- **那么** prompt 不得要求 search 一定先于任何 judgments 出现
- **那么** prompt 必须要求 reads、writes、missing_info 和 assumptions 围绕 judgments 再由工具证据绑定或补缺

#### 场景:根据 judgments 派生 reads 与 writes
- **当** `task_node` 已经形成 judgments
- **那么** prompt 必须要求 reads 覆盖 judgments 中声明的判定所需值
- **那么** prompt 必须要求 writes 覆盖 judgments 中声明的状态变更
- **那么** 无法绑定到 exact path 的部分必须进入 missing_info 或 assumptions，而不是直接猜测

### 需求:task_node prompt 必须为规则检索选择查询模式
系统必须要求 `task_node` 在规则优先任务中保留规则术语锚点、避免规则身份漂移，并仅在缺少可靠术语时转向更语义化的检索。系统禁止继续把 `term`、`balanced`、`semantic` 三种查询模式当作每次都必须显式完成的前置分类仪式。

#### 场景:存在明确规则术语锚点
- **当** `task_node` 处理包含明确规则术语的规则优先任务
- **那么** prompt 必须要求 query 保留该规则术语锚点
- **那么** prompt 不得鼓励模型把具名法术或动作先改写成宽泛规则场景再检索

#### 场景:不存在可靠规则术语锚点
- **当** `task_node` 处理规则优先任务，但当前没有可靠规则术语锚点
- **那么** prompt 必须允许模型使用更语义化的规则场景描述
- **那么** prompt 必须要求模型在规则身份不明确时保守处理
- **那么** prompt 不得要求模型先完成固定的三选一查询模式判定才能继续 reasoning

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

### 需求:dsl_node 必须只翻译 TaskDraft 而不是重新理解任务
系统必须要求 `dsl_node` 将 `TaskDraft` 作为翻译真相。系统禁止 `dsl_node` 在生成 `TaskDocument` 时重新补完任务结构、重新发明缺口解释，或覆盖 `task_node` 已确认的 judgments / evidence / states。

#### 场景:dsl_node 翻译已存在缺口的 TaskDraft
- **当** `dsl_node` 接收到一个包含 `missing_info` 的 `TaskDraft`
- **那么** `dsl_node` 必须把这些缺口及其默认值语义翻译进 `TaskDocument`
- **那么** `dsl_node` 不得自行重新判断这些缺口的默认处理
- **那么** `dsl_node` 不得把 `TaskDraft` 改写成新的任务理解版本

### 需求:TaskDraft 的 missing_info 必须包含默认值语义
系统必须要求 `TaskDraft.missing_info` 不再只是自由文本字符串列表，而应包含可供下游直接翻译的默认值或默认处理语义。系统禁止继续只给 `dsl_node` 一段模糊缺口描述再要求其自行推断默认行为。

#### 场景:范围法术缺失爆点时给出默认处理
- **当** `task_node` 发现某个范围法术任务缺少爆点或覆盖判定信息
- **那么** `missing_info` 必须显式说明该缺口
- **那么** `missing_info` 必须同时给出默认值或默认处理方向
- **那么** `dsl_node` 可以直接翻译该默认值语义，而无需重新猜测

#### 场景:缺失默认值语义时视为 TaskDraft 不完整
- **当** `TaskDraft.missing_info` 只包含自由文本描述而没有默认值或默认处理语义
- **那么** 系统不得把该 `TaskDraft` 视为对 `dsl_node` 完整可翻译的中间对象契约

### 需求:dsl_node 的 few-shot 必须复用 task_node 的任务类型原型
系统必须要求 `dsl_node` prompt 的 few-shot 使用与 `task_node` 一致的任务类型原型。系统禁止 `dsl_node` 维护一套与 `task_node` 脱节的独立场景分类。

#### 场景:dsl_node few-shot 覆盖主要任务类型
- **当** `dsl_node` prompt 使用 few-shot 教模型翻译 `TaskDraft`
- **那么** few-shot 必须覆盖与 `task_node` 对齐的主要任务类型原型
- **那么** 至少必须包括单体攻击、单体法术、范围法术、治疗或增益、状态或条件效果、纯状态查询等主要类别
- **那么** 每个 few-shot 的重点必须是展示“该类型的 TaskDraft 如何被翻译成 TaskDocument”

### 需求:task_node prompt 必须感知下游 dsl node 和 engine 的职责边界
系统必须要求 `task_node` 的 prompt 明确知道 TaskDraft 只是 planner workflow 的第一阶段输出，其后还有 `dsl node` 将任务稿翻译为结构化 TaskDocument，且最终由 engine 在运行期执行并求值。系统禁止继续让 `task_node` 假设自己必须在第一阶段补齐所有运行期结果。

#### 场景:task_node 生成规则驱动任务稿
- **当** `task_node` 处理一条规则驱动的 DM 指令
- **那么** prompt 必须说明 TaskDraft 会被后续 `dsl node` 消费
- **那么** prompt 必须说明 TaskDocument 会由 engine 在运行期执行
- **那么** agent 必须把第一阶段重点放在执行意图、状态依赖和决策结构上，而不是提前产出运行期结果

### 需求:task_node prompt 必须禁止把运行期随机结果写入 missing_info
系统必须要求 `task_node` 的 prompt 把 `missing_info` 限定为真正阻止 drafting 的前置缺口，禁止把攻击掷骰结果、伤害骰结果、豁免成败等运行期随机结果写入 `missing_info`。

#### 场景:攻击或法术的随机结果尚未产生
- **当** `task_node` 处理需要未来掷骰、未来豁免或未来伤害计算的任务
- **那么** prompt 必须说明这些结果会由 engine 在运行期产生
- **那么** agent 不得因为当前还不知道这些结果就把它们写入 `missing_info`
- **那么** agent 应继续把这些内容保留在 judgments 或执行计划中

#### 场景:真正缺失的前置信息仍应进入 missing_info
- **当** `task_node` 无法确认 exact path、规则身份、必要状态值或会改变执行形状的人类决策
- **那么** agent 仍必须把这些内容写入 `missing_info`
- **那么** prompt 不得让 agent 因为“后面还有 engine”就忽略这些真实缺口

### 需求:task_node prompt 必须以执行不变量与缺口暴露为主线
系统必须要求 `task_node` 的 prompt 先识别任务的执行不变量、关键前提、受影响对象和潜在写回，再决定需要哪些工具证据。系统禁止继续把 upfront 任务分类当作主要推理入口。

#### 场景:task_node 处理规则与状态交织的任务
- **当** `task_node` 处理同时涉及规则形状、状态路径和资源绑定的任务
- **那么** prompt 必须优先引导模型明确执行目标、关键前提和安全可绑定的写回
- **那么** prompt 可以把任务原型当作辅助手段
- **那么** prompt 不得要求模型必须先完成固定任务分类后才能开始形成 `judgments`

#### 场景:task_node 暴露真实缺口
- **当** `task_node` 无法安全确认路径、覆盖范围、默认环级或受影响对象集合
- **那么** prompt 必须要求模型保留这种不确定性
- **那么** prompt 不得让模型用更像某个任务类别的表述来掩盖真实缺口

### 需求:dsl_node 必须基于 primitive 语义做 lowering 与组合
系统必须要求 `dsl_node` 根据 `TaskDraft` 的 judgments、reads、writes、evidence 和 states，理解每个 engine primitive 在执行链中的职责后再做 lowering。系统禁止继续把 `dsl_node` 默认约束为只能围绕少量任务族模板做机械填空。

#### 场景:dsl_node 生成多步 DSL
- **当** `dsl_node` 需要把一份复杂 `TaskDraft` 翻译成多步 `TaskDocument`
- **那么** 节点必须能够理解哪些步骤负责确定对象集合、哪些步骤负责生成判定结果、哪些步骤负责写回状态
- **那么** 节点必须能够在当前 engine 支持的 step type / kind 范围内自由合理地组合这些 primitive
- **那么** 节点不得因为某个高层任务族未完全命中模板而放弃合理的 primitive 组合

#### 场景:dsl_node 使用 template 收敛自由组合
- **当** `dsl_node` 在自由组合 primitive 的同时使用 `template`
- **那么** `template` 必须帮助节点确认合法 shape、默认骨架与常见错误
- **那么** 节点仍必须以 primitive 运行语义和 `TaskDraft` 真相为主
- **那么** 系统不得把 `template` 视为唯一允许的 primitive 组合来源

