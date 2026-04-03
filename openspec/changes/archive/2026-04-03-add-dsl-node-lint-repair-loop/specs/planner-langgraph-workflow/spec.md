## 新增需求

## 修改需求

### 需求:dsl 节点核心必须由 langchain.create_agent 驱动
系统必须要求 `src/augury/planner/nodes/dsl_node.py` 的核心执行体由 `langchain.create_agent` 创建的 agent 驱动，禁止绕过 agent 直接把中间对象硬编码成最终 DSL 作为最终实现。

#### 场景:dsl 节点生成 TaskDocument
- **当** 第二阶段节点接收到第一阶段产出的中间对象
- **那么** 节点必须通过 `langchain.create_agent` 产出的 agent 执行核心推理
- **那么** 节点必须输出可被 lint 或执行链路直接消费的 TaskDocument DSL
- **那么** 节点必须把第一阶段的任务稿当作主要输入来源，而不是重新把原始 DM 指令当作唯一真相

#### 场景:dsl 节点根据 lint 结果修复候选文档
- **当** `dsl_node` 的首轮候选 `TaskDocument` 未通过 lint
- **那么** repair 回路必须保持在 `dsl_node` 内部，由 agent 以 ReAct/tool-use 形式调用 `lint`
- **那么** 系统不得为了 repair 新增外层 LangGraph 节点或新的 planner 阶段
- **那么** 节点必须能够读取当前 candidate 和对应的结构化 lint issues
- **那么** 节点必须在有限预算内尝试修复该 candidate，而不是只能返回首轮失败结果
- **那么** 节点提示词必须明确约束 `lint` 的调用次数和停止条件
- **那么** 节点在 repair 阶段应尽量保留已合法的步骤，而不是无谓重写整份文档

## 移除需求
