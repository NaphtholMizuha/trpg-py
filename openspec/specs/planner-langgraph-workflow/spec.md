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

### 需求: dsl 节点核心必须由 langchain.create_agent 驱动
系统必须要求 `src/augury/planner/nodes/dsl_node.py` 的核心执行体由 `langchain.create_agent` 创建的 agent 驱动，禁止绕过 agent 直接把中间对象硬编码成最终 DSL 作为最终实现。

#### 场景:dsl 节点生成 TaskDocument
- **当** 第二阶段节点接收到第一阶段产出的中间对象
- **那么** 节点必须通过 `langchain.create_agent` 产出的 agent 执行核心推理
- **那么** 节点必须输出可被 lint 或执行链路直接消费的 TaskDocument DSL
- **那么** 节点必须把第一阶段的任务稿当作主要输入来源，而不是重新把原始 DM 指令当作唯一真相

### 需求: workflow 必须以显式中间对象在两个 agent 节点之间传递状态
系统必须在 LangGraph workflow 的状态对象中显式保存第一阶段产出的中间对象，禁止让第二阶段节点只依赖原始 DM 指令或自由文本重新开始理解任务。

#### 场景:workflow 从 task 节点流转到 dsl 节点
- **当** workflow 收到第一阶段节点结果
- **那么** 它必须把该结果作为显式状态字段传给第二阶段节点
- **那么** 第二阶段节点无需从零重新解析原始 DM 指令

### 需求: 两个 agent 节点必须具有不同的工具边界
系统必须对两个 agent 节点施加不同的 tools 边界：第一阶段节点负责任务理解与上下文获取，第二阶段节点负责 DSL 翻译与校验，禁止默认让两个节点共享完全相同的工具集合。

#### 场景:workflow 装配两个节点
- **当** workflow 装配 task 节点与 dsl 节点
- **那么** task 节点必须作为单一 agent 自主使用受限的上下文收集工具集合完成检索与任务起草
- **那么** task 节点的默认工具边界应服务于生成合适的任务上下文，而不是暴露单独的 query planning 阶段
- **那么** task 节点禁止默认获得 `read` 权限
- **那么** dsl 节点必须获得面向 DSL 生成与校验的工具集合

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
