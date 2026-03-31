## 为什么

当前仓库在 `src/augury/planner/` 下只保留了工具与少量支撑类型，还没有新的 planner 主流程骨架。为了继续实现新的规划器，需要先明确 workflow 入口、两阶段节点边界以及目录组织约束，否则后续实现很容易把节点职责、工具访问和文件布局重新混在一起。

## 变更内容

- 新增新的两阶段 planner workflow，放在 `src/augury/planner/` 目录下，由一个明确的 workflow 入口负责串联两个 ReAct 节点。
- 在 `src/augury/planner/nodes/` 下拆分两个独立节点文件，分别承载第一阶段“DM 指令 -> 半结构化任务概述”和第二阶段“任务概述 -> TaskDocument DSL”的 ReAct 节点。
- 明确 planner 目录内 workflow、nodes、runtime guard、task document 与 tools 之间的边界，避免再把 orchestration、节点逻辑和工具实现混放在单个文件。
- 为新的 planner workflow 增加对应的可测试契约，确保两阶段节点的输入输出和调用顺序稳定。

## 功能 (Capabilities)

### 新增功能
- `planner-workflow`: 定义新的两阶段 planner workflow、节点目录布局以及 workflow 与 nodes 的职责边界。

### 修改功能

## 影响

- 受影响代码：`src/augury/planner/` 下的新 workflow 入口、`src/augury/planner/nodes/` 节点文件、相关类型与运行时支撑。
- 受影响架构：planner 将从“只有 tools 和零散支撑文件”升级为“workflow + nodes + tools”的稳定目录结构。
- 受影响后续实现：planner 的 Intent 阶段与 DSL 阶段将以独立节点文件演进，后续再接工具和状态机时会有明确落点。
