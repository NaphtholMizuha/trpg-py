## 新增需求

## 修改需求

### 需求:dsl 节点核心必须由 langchain.create_agent 驱动
系统必须要求 `src/augury/planner/nodes/dsl_node.py` 的核心执行体由 `langchain.create_agent` 创建的 agent 驱动，禁止绕过 agent 直接把中间对象硬编码成最终 DSL 作为最终实现。

#### 场景:dsl 节点消费模板化 lint 诊断
- **当** `dsl_node` 获得 `lint` 返回的结构化 issues
- **那么** 节点必须能够消费其中的模板化诊断信息，而不只把 `message` 当成普通字符串
- **那么** 节点必须把这些模板化诊断视为生成或修正 DSL 的约束依据之一

#### 场景:dsl 节点以 lint valid 作为最终目标
- **当** `dsl_node` 生成最终 `TaskDocument`
- **那么** 节点必须把“返回当前 lint 视角下的 valid 结果”视为默认目标
- **那么** 节点不得把已经被 `lint` 判为 invalid 的 candidate 当作理想最终状态

## 移除需求
