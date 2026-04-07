## 新增需求

## 修改需求

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
- **那么** 节点不得依赖宿主预取的 `template_lookup` 或等价对象代替真实工具调用

#### 场景:dsl 节点以 template 作为合法骨架来源
- **当** `dsl_node` 需要为某类任务生成候选 `TaskDocument`
- **那么** 节点必须先识别当前任务属于哪一类高频任务族
- **那么** 节点必须由 agent 显式调用 `template` 工具获取对应 DSL 骨架
- **那么** 节点不得继续仅依赖 prompt 中内联的大段模板手册自行发明 DSL 结构

#### 场景:dsl 节点同时使用 template 和 lint
- **当** `dsl_node` 已获得 `template` 返回的 DSL 骨架
- **那么** 节点必须基于该骨架填充实例参数
- **那么** 节点仍必须在提交前调用 `lint`
- **那么** `template` 不得替代 `lint` 的最终守门职责

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
- **那么** `template` 的使用必须发生在 agent 的真实 tool-use 回路里，而不是宿主侧预处理阶段

## 移除需求
