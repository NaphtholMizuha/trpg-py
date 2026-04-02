## 上下文

当前 planner 已经开始形成 `workflow + nodes + tools` 的目录骨架，但 workflow 仍然可以被任意方式实现，节点核心也还可能退化成手写函数或占位逻辑。这会让后续 planner 的控制流、消息边界和工具调用模式继续飘动，尤其是在两阶段节点都要具备 ReAct 风格工具使用能力的前提下。

这次变更的目标不是再讨论 planner 是否需要两阶段，而是把“两阶段如何编排、节点内部如何执行、两阶段之间传什么”这三个关键点固定下来：
- workflow 用 LangGraph 表达控制流与状态流转
- `task_node` 与 `dsl_node` 的核心执行体都用 `langchain.create_agent`
- 第一阶段输出 `TaskDraft`，而不是受限的动作分类结果

## 目标 / 非目标

**目标：**
- 将新的 planner workflow 明确为一个 LangGraph 图，而不是普通顺序函数。
- 将两个阶段节点的核心执行方式明确为 `langchain.create_agent` 产出的 agent。
- 保持两阶段职责清晰：第一阶段生成结构化自然语言任务稿，第二阶段将任务稿翻译为 TaskDocument DSL。
- 明确 workflow 状态对象、图节点输入输出以及 tools 注入边界。
- 为后续引入 verifier、HITL 节点或条件分支保留自然扩展点。

**非目标：**
- 本次设计不要求一次性确定所有 prompt 文案。
- 本次设计不扩展新的 planner 工具协议。
- 本次设计不要求第一版 LangGraph workflow 就实现复杂分支、并发或循环控制。
- 本次设计不要求重做 engine DSL 或 executor 语义。

## 决策

### 决策 1：workflow 必须用 LangGraph 表达两阶段主链路

`src/augury/planner/workflow.py` 必须以 LangGraph StateGraph 或等价 LangGraph 图构造 API 表达 planner 的主链路。该图至少包含：
- 一个 workflow 入口
- `task_node`
- `dsl_node`
- 一个结束节点或等价终态

选择 LangGraph 的原因是：
- 它天然适合把 planner 建模成显式状态图
- 后续插入 verifier、retry、HITL 分支时不需要推翻主入口结构
- 节点边界、状态对象和流转关系都能保持清晰

替代方案：
- 普通 Python 顺序编排：短期更快，但难以自然扩展到后续分支和状态图
- 自己维护节点调度器：会重复造轮子，且增加维护负担

### 决策 2：两个节点的核心执行体必须用 `langchain.create_agent`

`task_node.py` 和 `dsl_node.py` 都必须围绕 `langchain.create_agent` 构造 agent，并由该 agent 承担各自阶段的核心推理与工具调用职责。

选择 `create_agent` 的原因是：
- 它比手写提示词拼装 + 裸模型调用更接近 LangChain 的标准 agent 入口
- 节点可以自然声明自己的 tools 集合和结构化输出目标
- 后续如果更换模型或扩展中间件，节点改动范围可控

替代方案：
- 手写 node 函数内部直接调模型：不利于统一 agent 行为和工具接入
- 用一个 agent 兼顾两阶段：会让节点职责重新耦合

### 决策 3：第一阶段必须输出结构化自然语言任务稿

第一阶段节点不应把 DM 指令压缩成受限的 `action_shape` 或同类动作分类标签，而应输出一个 `TaskDraft`。`TaskDraft` 的中心是自然语言任务稿，但它必须显式写明：
- 要完成什么任务
- 读取哪些状态值
- 基于这些值做什么判定
- 最终把结果写回哪些路径
- 仍缺什么信息

推荐的中间对象语义是：

```text
TaskDraft
├── task
├── reads
├── judgments
├── writes
├── missing_info
└── assumptions
```

这样做的原因是：
- 它比动作分类更能保留复杂任务语义
- 它更贴近 `dsl_node` 真正需要的输入
- 它让第二阶段真正成为“翻译器”，而不是第二个重新理解任务的 planner

替代方案：
- 使用 `action_shape` 等受限类别：实现简单，但会过早限制任务表达空间
- 只传自由文本摘要：过于松散，`dsl_node` 仍需重新理解

### 决策 4：两个 agent 拥有不同的工具边界

第一阶段 agent 负责起草任务稿和补上下文，因此可以访问状态/规则检索相关工具，但默认边界必须收敛到 `grep` 与可选 `search`，不得继续直接持有 `read` 权限。第二阶段 agent 负责把 `TaskDraft` 翻译为 DSL，因此默认只应访问 DSL 构造与校验所需工具，例如 `lint`。

这样做的原因是：
- 可以抑制第二阶段重复做第一阶段的检索工作
- 能让 `TaskDraft` 真正成为结构化边界，而不是一层虚壳
- 有助于控制 token 消耗和 agent 行为漂移
- 让第一阶段先暴露“找候选、提规则”的能力，而不是直接读取任意状态值，避免它在工具层获得过强权限

替代方案：
- 给两个 agent 同一套 tools：实现简单，但极易重新耦合两阶段职责
- 继续给 `task_node` 暴露 `read`：实现上方便，但会让第一阶段直接读取状态值，弱化工具边界约束

### 决策 5：workflow 状态对象必须显式承载中间对象和节点结果

LangGraph workflow 的状态必须显式包含：
- 原始 instruction
- 第一阶段产出的中间对象，例如 `TaskDraft`
- 第二阶段产出的 TaskDocument
- 可选 lint 结果或终态信息

这样做的原因是，LangGraph 的价值在于显式状态流转；如果状态对象仍然只传自由文本，graph 结构会沦为形式化外壳。

替代方案：
- 节点之间只传字符串：实现快，但无法保证两阶段边界稳定

## 风险 / 权衡

- [引入 LangGraph 与 LangChain 依赖会提高实现复杂度] → 通过把第一版 graph 限定为最小线性主链路来控制复杂度。
- [`create_agent` 的默认行为可能比手写函数更不稳定] → 通过限制每个节点的 tools 边界、输入输出 schema 和测试契约来约束行为。
- [结构化自然语言任务稿可能比动作分类更难约束] → 通过显式字段如 `reads / judgments / writes / missing_info` 给自然语言稿加边界。
- [两阶段 agent 组合可能带来更多运行时开销] → 这是为了换取更清晰的职责边界和后续扩展空间。
- [现有骨架代码需要重构] → 通过单独开新变更，把 LangGraph 版本和已有骨架版本分离，避免一次改动里同时处理两种架构。

## Migration Plan

1. 在新变更下定义基于 LangGraph 的 workflow 需求和设计，不直接覆盖已有骨架方案。
2. 重构 `src/augury/planner/workflow.py`，将顺序调用主链路替换为 LangGraph 图。
3. 将第一阶段节点从 `intent_node` 重命名并重构为 `task_node`，其产出改为 `TaskDraft`。
4. 重构 `src/augury/planner/nodes/dsl_node.py`，使其以 `TaskDraft` 作为唯一主输入来源。
5. 将 workflow 状态对象、中间对象、tools 注入与最小测试同步更新。

## Open Questions

- `create_agent` 是否要在节点模块导出为可替换工厂，以便测试时注入 fake agent？
- `TaskDraft` 中 `reads / judgments / writes` 应该是纯字符串列表，还是升级为带 purpose/path/value 的结构化对象？
- 第一版 LangGraph workflow 是否需要在 graph 内处理 lint 失败分支，还是先由 `dsl_node` 内部完成最小闭环？
- 是否需要把模型和 system prompt 配置集中到 planner 配置模块，而不是散在各节点文件中？
