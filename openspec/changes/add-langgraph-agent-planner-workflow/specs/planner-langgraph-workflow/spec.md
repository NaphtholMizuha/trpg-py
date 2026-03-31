## 新增需求

### 需求:planner 必须使用 LangGraph 作为 workflow 编排真相
系统必须在 `src/augury/planner/workflow.py` 中使用 LangGraph 编排新的 planner workflow，禁止继续以普通顺序函数作为新的 planner 主入口真相。

#### 场景:调用方创建新的 planner workflow
- **当** 调用方需要实例化新的 planner workflow
- **那么** 可以从 `src/augury/planner/workflow.py` 获取基于 LangGraph 构造的 workflow 入口
- **那么** 该入口必须以内建图状态流转的方式串联两个阶段节点

### 需求:task 节点核心必须由 langchain.create_agent 驱动
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

### 需求:dsl 节点核心必须由 langchain.create_agent 驱动
系统必须要求 `src/augury/planner/nodes/dsl_node.py` 的核心执行体由 `langchain.create_agent` 创建的 agent 驱动，禁止绕过 agent 直接把中间对象硬编码成最终 DSL 作为最终实现。

#### 场景:dsl 节点生成 TaskDocument
- **当** 第二阶段节点接收到第一阶段产出的中间对象
- **那么** 节点必须通过 `langchain.create_agent` 产出的 agent 执行核心推理
- **那么** 节点必须输出可被 lint 或执行链路直接消费的 TaskDocument DSL
- **那么** 节点必须把第一阶段的任务稿当作主要输入来源，而不是重新把原始 DM 指令当作唯一真相

### 需求:workflow 必须以显式中间对象在两个 agent 节点之间传递状态
系统必须在 LangGraph workflow 的状态对象中显式保存第一阶段产出的中间对象，禁止让第二阶段节点只依赖原始 DM 指令或自由文本重新开始理解任务。

#### 场景:workflow 从 task 节点流转到 dsl 节点
- **当** workflow 收到第一阶段节点结果
- **那么** 它必须把该结果作为显式状态字段传给第二阶段节点
- **那么** 第二阶段节点无需从零重新解析原始 DM 指令

### 需求:两个 agent 节点必须具有不同的工具边界
系统必须对两个 agent 节点施加不同的 tools 边界：第一阶段节点负责任务理解与上下文获取，第二阶段节点负责 DSL 翻译与校验，禁止默认让两个节点共享完全相同的工具集合。

#### 场景:workflow 装配两个节点
- **当** workflow 装配 task 节点与 dsl 节点
- **那么** task 节点必须获得面向上下文收集的工具集合
- **那么** dsl 节点必须获得面向 DSL 生成与校验的工具集合

## 修改需求

## 移除需求
