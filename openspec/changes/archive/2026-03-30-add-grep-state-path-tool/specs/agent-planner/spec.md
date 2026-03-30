## 新增需求

## 修改需求

### 需求:planner 必须通过 search 和 fetch_keys 获取证据
planner 必须将 `search`、`grep`、`list` 与 `read` 作为状态与规则取证工具链，并通过工具调用结果驱动后续推理分支。对于需要从自然语言线索定位状态路径的场景，planner 必须优先使用 `grep` 根据关键词检索相关叶子路径候选，而不是先围绕未知 prefix 机械试探 `list`。对于需要读取具体状态值的场景，planner 必须进一步优先使用批量 `read` 一次性确认一组候选路径上的当前值，而不是把同类确认拆成大量零散单路径读取。`list` 继续作为补充型路径导航工具，用于在 `grep` 无法收敛时观察某个已知范围下的结构。对于候选 `TaskDocument` 的合法性收口，planner 必须能够进一步使用 `lint` 工具执行只读自检，但 `lint` 不得替代 `search`、`grep`、`list` 与 `read` 的取证职责，也不得演化为无限自修循环。

#### 场景:planner 使用 search 补充规则证据
- **当** DM 指令涉及规则判断（如攻击、豁免、伤害）
- **那么** planner 可以调用 `search` 检索规则原文
- **那么** 规则结论建立在检索证据之上

#### 场景:planner 使用 grep 补充状态路径证据
- **当** planner 需要根据实体名、字段名或动作线索定位相关状态路径
- **那么** planner 必须优先调用 `grep` 检索相关叶子路径候选
- **那么** planner 无需先猜中正确 prefix 才能进入路径发现流程

#### 场景:planner 使用 list 作为补充结构导航
- **当** `grep` 无法缩小候选范围，或 planner 需要观察某个已知 root 下的结构
- **那么** planner 可以调用 `list` 枚举该范围下的路径
- **那么** `list` 不得继续承担默认主路径发现职责

#### 场景:planner 使用批量 read 补充状态值证据
- **当** planner 已经通过 `grep` 或 `list` 发现一组同类候选路径并需要确认其当前值
- **那么** planner 必须优先使用一次批量 `read` 读取这些路径
- **那么** planner 不得把该组值确认机械拆成多次单路径读取

#### 场景:planner 使用 lint 收口候选文档
- **当** planner 已具备足够规则证据和状态路径证据并准备返回 `ready`
- **那么** planner 可以调用 `lint` 对候选 `TaskDocument` 做只读合法性校验
- **那么** `lint` 的结果只用于校验候选文档，不得被当作规则证据或状态事实来源
- **那么** 若没有新的状态或规则证据，planner 不得仅靠重复 `lint` 无限修补

### 需求:planner 必须在提问前优先完成可用工具取证
系统必须要求 planner 在触发 HITL 之前尽可能完成 `search`、`grep`、必要时的 `list` 以及必要的批量 `read` 取证尝试，避免因未检索、未发现候选路径或未读取关键值造成过早提问。对于 `grep`、`list` 或 `read` 已明确返回 `status=no_match` 的事实，planner 必须把它视为“当前 state 中没有对应路径或值证据”的信号。若 `grep` 无命中，planner 可以回退到 `list` 做有限补充导航；若 `list` 或 `read` 已给出建议路径，planner 仅可沿建议做有限修正，而不得机械重复原失败请求。

#### 场景:先 grep/read 取证后提问
- **当** DM 指令初看存在歧义
- **当** planner 仍可通过 `grep`、`list` 或批量 `read` 获取更多状态证据
- **那么** planner 必须先完成这些取证尝试
- **那么** 只有工具取证后仍无法收敛到单一可执行方案时才触发 `needs_human`

#### 场景:grep 无命中后回退 list
- **当** planner 使用 `grep` 检索状态路径且返回 `status=no_match`
- **那么** planner 可以回退到 `list` 观察某个已知范围下的结构
- **那么** planner 不得围绕同一关键词主题无限重复 `grep`

#### 场景:no_match 经过有限修正后仍失败
- **当** `grep`、`list` 或 `read` 返回 `status=no_match`
- **当** planner 已做过一次有限补充检索或建议修正仍未找到所需事实
- **那么** planner 必须把该事实视为当前 state 缺失
- **那么** planner 不得继续围绕原主题无限试探

## 移除需求
