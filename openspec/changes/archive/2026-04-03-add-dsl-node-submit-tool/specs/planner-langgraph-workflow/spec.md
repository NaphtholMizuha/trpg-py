## 新增需求

## 修改需求

### 需求:dsl 节点核心必须由 langchain.create_agent 驱动
系统必须要求 `src/augury/planner/nodes/dsl_node.py` 的核心执行体由 `langchain.create_agent` 创建的 agent 驱动，禁止绕过 agent 直接把中间对象硬编码成最终 DSL 作为最终实现。

#### 场景:dsl 节点生成 TaskDocument
- **当** 第二阶段节点接收到第一阶段产出的中间对象
- **那么** 节点必须通过 `langchain.create_agent` 产出的 agent 执行核心推理
- **那么** 节点必须输出可被 lint 或执行链路直接消费的 TaskDocument DSL
- **那么** 节点必须把第一阶段的任务稿当作主要输入来源，而不是重新把原始 DM 指令当作唯一真相
- **那么** 节点必须继续通过 `response_format=TaskDocumentSchema` 提交最终结构化结果
- **那么** 系统不得为了修复当前问题移除 `dsl_node` 的结构化输出协议

#### 场景:dsl 节点使用 lint 作为诊断工具
- **当** `dsl_node` 在提交最终 `TaskDocument` 之前需要检查候选 DSL 是否符合当前 engine 契约
- **那么** 节点可以调用 `lint` 工具获取诊断信息
- **那么** 系统不得要求 `lint` 必须充当新的外层 workflow 阶段
- **那么** 系统不得默认要求 `lint` 必须充当固定预算、固定轮次的控制流工具
- **那么** 节点最终仍必须通过结构化输出协议一次性提交最终文档

## 移除需求
