## 新增需求

## 修改需求

### 需求:dsl 节点核心必须由 langchain.create_agent 驱动
系统必须要求 `src/augury/planner/nodes/dsl_node.py` 的核心执行体由 `langchain.create_agent` 创建的 agent 驱动，禁止绕过 agent 直接把中间对象硬编码成最终 DSL 作为最终实现。

#### 场景:dsl 节点把 lint 作为提交前检查
- **当** `dsl_node` 从 `TaskDraft` 生成候选 `TaskDocument`
- **那么** 节点必须把 `lint` 视为提交前检查工具，而不是纯可选附属工具
- **那么** 节点的默认成功标准必须是输出当前 `lint` 视角下的 `valid` TaskDocument`
- **那么** 节点必须为 agent 提供有限的 `lint` 工具调用预算，以支持受控的再次校验

#### 场景:dsl 节点不应把 lint invalid 当作理想终态
- **当** `dsl_node` 已经拿到某个 candidate 的 `lint invalid` 结果
- **那么** 节点不得把该 candidate 视为理想最终答案
- **那么** 节点必须至少把该结果作为继续修正或重新生成时的约束依据

#### 场景:dsl 节点提供 fallback lint
- **当** `dsl_node` 最终没有从 agent 响应中获得 `lint` 结果
- **那么** 节点必须执行至少一次 fallback lint
- **那么** 节点必须把 fallback 是否触发记录到可观察元数据中

## 移除需求
