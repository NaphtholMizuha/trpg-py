## 为什么

当前已经有一个新的两阶段 planner 骨架方向，但编排方式、节点命名和中间表示都还没有定型。现在需要明确把 workflow 收敛到 LangGraph，把两个阶段节点的核心执行体收敛到 `langchain.create_agent`，并把第一阶段重新定义为“生成结构化自然语言任务稿”，这样后续 planner 的控制流、节点职责和 DSL 翻译边界才有稳定真相。

## 变更内容

- 新增一个基于 LangGraph 的 planner workflow，由 `src/augury/planner/` 根目录下的 workflow 入口负责图编排与状态流转。
- 规定 `src/augury/planner/nodes/task_node.py` 和 `src/augury/planner/nodes/dsl_node.py` 的核心实现都必须由 `langchain.create_agent` 创建的 agent 驱动，而不是手写占位逻辑。
- 明确第一阶段 agent 负责“DM 指令 -> 结构化自然语言任务稿（TaskDraft）”，第二阶段 agent 负责“任务稿 -> TaskDocument DSL”，并由 workflow 以显式中间对象传递状态。
- 要求任务稿必须写明读取哪些值、基于哪些值做什么判定、以及最终结果写回哪些值，而不是先压缩成受限的动作分类。
- 为新的 LangGraph workflow 增加最小可测试契约，确保调用方可以实例化图、执行两阶段节点并拿到结构化结果。

## 功能 (Capabilities)

### 新增功能
- `planner-langgraph-workflow`: 定义基于 LangGraph 的 planner workflow，以及由 `langchain.create_agent` 驱动的双节点 planner 契约。

### 修改功能

## 影响

- 受影响代码：`src/augury/planner/workflow.py`、`src/augury/planner/nodes/`、planner 共享类型以及与 tools 的接线方式。
- 受影响依赖：planner 将显式依赖 LangGraph 编排能力和 LangChain agent 构造能力。
- 受影响架构：planner 的“主流程编排”和“节点核心执行体”都会从手写占位逻辑升级为 LangGraph + `create_agent` 的固定组合，中间层也会从薄的任务概述升级为面向 DSL 翻译的 `TaskDraft`。
