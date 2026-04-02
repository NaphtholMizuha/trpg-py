# planner-workflow 规范

## 目的
待定 - 由归档变更 add-two-stage-planner-workflow 创建。归档后请更新目的。
## 需求
### 需求:planner 必须提供位于 planner 根目录的 workflow 入口
系统必须在 `src/augury/planner/` 根目录下提供新的 planner workflow 入口模块，作为新的 planner 编排真相；禁止把 workflow 主入口散落到节点模块或工具模块中。

#### 场景:调用方装配新的 planner workflow
- **当** 调用方需要实例化新的 planner
- **那么** 可以从 `src/augury/planner/` 根目录的 workflow 入口模块获取新的 planner 主流程
- **那么** 该入口负责串联两阶段节点而不是在调用方处手工拼接

### 需求:planner 必须在 nodes 目录下拆分两个阶段节点文件
系统必须在 `src/augury/planner/nodes/` 下使用两个独立文件实现两阶段 ReAct 节点，禁止把两个阶段继续塞回单个大文件。

#### 场景:第一阶段和第二阶段位于不同文件
- **当** 开发者查看新的 planner 节点实现
- **那么** 第一阶段节点位于 `src/augury/planner/nodes/` 下的独立文件
- **那么** 第二阶段节点位于 `src/augury/planner/nodes/` 下的另一个独立文件

### 需求:第一阶段节点必须把 DM 指令转换为半结构化任务概述
系统必须要求第一阶段 ReAct 节点消费 DM 指令并产出半结构化任务概述，禁止直接在第一阶段输出最终 TaskDocument DSL。

#### 场景:第一阶段处理 DM 指令
- **当** 第一阶段节点接收到一条 DM 指令
- **那么** 它必须输出可供第二阶段消费的半结构化任务概述
- **那么** 它不得跳过该中间层直接输出最终 TaskDocument

### 需求:第二阶段节点必须把任务概述翻译为 TaskDocument DSL
系统必须要求第二阶段 ReAct 节点消费第一阶段输出的任务概述并翻译为 TaskDocument DSL，禁止重新把原始 DM 指令当作唯一输入来源。

#### 场景:第二阶段生成 TaskDocument
- **当** 第二阶段节点接收到半结构化任务概述
- **那么** 它必须基于该概述生成 TaskDocument DSL
- **那么** 它的输出必须可被后续 lint 或执行链路直接消费

### 需求:workflow 必须以明确的中间对象在两阶段之间传递状态
系统必须在第一阶段和第二阶段之间使用明确的中间对象传递状态，禁止仅通过自由文本字符串松散传递上下文。

#### 场景:workflow 将第一阶段输出传给第二阶段
- **当** workflow 收到第一阶段节点的结果
- **那么** 它必须以明确的中间对象把结果传给第二阶段
- **那么** 第二阶段无需重新从零解析一段自由文本

