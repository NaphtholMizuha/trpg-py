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

#### 场景:dsl 节点默认工具预算覆盖一次模板纠偏
- **当** `dsl_node` 在默认配置下运行
- **那么** 默认工具预算必须至少能够覆盖一次 `template` 误查后的保守回退
- **那么** 默认工具预算必须至少能够覆盖后续一次 `lint` 提交前校验
- **那么** 系统不得继续把默认预算设置为只够理想一次命中的路径

## 移除需求
