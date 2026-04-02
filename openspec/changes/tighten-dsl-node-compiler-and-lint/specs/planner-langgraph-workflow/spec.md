## 新增需求

## 修改需求

### 需求:dsl 节点核心必须由 langchain.create_agent 驱动
系统必须要求 `src/augury/planner/nodes/dsl_node.py` 的核心执行体由 `langchain.create_agent` 创建的 agent 驱动，禁止绕过 agent 直接把中间对象硬编码成最终 DSL 作为最终实现。

#### 场景:dsl 节点生成 TaskDocument
- **当** 第二阶段节点接收到第一阶段产出的中间对象
- **那么** 节点必须通过 `langchain.create_agent` 产出的 agent 执行核心推理
- **那么** 节点必须输出可被 lint 或执行链路直接消费的 TaskDocument DSL
- **那么** 节点必须把第一阶段的任务稿当作主要输入来源，而不是重新把原始 DM 指令当作唯一真相
- **那么** 节点生成的步骤类型与步骤 kind 必须限定在当前 engine 支持的 DSL 词表内
- **那么** 节点不得发明引擎不支持的高层 workflow 术语作为 step type 或 kind

### 需求: 两个 agent 节点必须具有不同的工具边界
系统必须对两个 agent 节点施加不同的 tools 边界：第一阶段节点负责任务理解与上下文获取，第二阶段节点负责 DSL 翻译与校验，禁止默认让两个节点共享完全相同的工具集合。

#### 场景:workflow 装配两个节点
- **当** workflow 装配 task 节点与 dsl 节点
- **那么** task 节点必须作为单一 agent 自主使用受限的上下文收集工具集合完成检索与任务起草
- **那么** task 节点的默认工具边界应服务于生成合适的任务上下文，而不是暴露单独的 query planning 阶段
- **那么** task 节点禁止默认获得 `read` 权限
- **那么** dsl 节点必须获得面向 DSL 生成与校验的工具集合
- **那么** dsl 节点生成候选 DSL 时必须能够消费 lint 级错误反馈，而不是只看到单一模糊失败摘要

## 移除需求
