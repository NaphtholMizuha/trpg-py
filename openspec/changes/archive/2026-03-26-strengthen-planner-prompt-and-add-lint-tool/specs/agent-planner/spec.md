## 新增需求

### 需求:planner prompt 必须显式教授 TaskDocument DSL
系统必须让 planner 使用的提示词显式描述合法 `TaskDocument` 的最小结构、允许的步骤 `type/kind` 组合、引用约定和至少一个代表性规范示例，禁止仅以“生成 TaskDocument”之类的抽象描述要求模型自行猜测 DSL。

#### 场景:planner 根据显式 DSL 约束规划攻击动作
- **当** planner 处理类似“哥布林攻击 hero_1”的 DM 指令
- **那么** prompt 中必须向模型暴露 `task_id`、`version`、`context`、`policy`、`steps` 以及步骤级 `id/type/kind/args` 等最小骨架
- **那么** prompt 中必须明确合法步骤类型与引用方式，而不是允许模型自由发明 `action`、`actor` 等替代字段
- **那么** prompt 中必须提供至少一个符合当前引擎 DSL 的规范示例

### 需求:planner 在返回 ready 前必须能够使用 lint 做候选文档自检
系统必须允许 planner 在准备返回 `status=ready` 前将候选 `TaskDocument` 提交给 `lint` 工具做只读校验，并根据结构化校验结果修复或降级，而禁止把所有合法性发现都推迟到最终兜底校验之后。

#### 场景:planner 用 lint 收口候选任务文档
- **当** planner 已完成规则与状态路径取证并生成候选 `TaskDocument`
- **那么** planner 必须能够调用 `lint` 对该候选文档执行只读校验
- **那么** 若 `lint` 返回非法结果，planner 必须根据错误结果修复文档或转入 `needs_human/blocked`
- **那么** 若 `lint` 返回合法结果，planner 才可以继续进入最终 `ready` 输出流程

## 修改需求

### 需求:planner 必须通过 search 和 fetch_keys 获取证据
planner 必须将 `search` 与 `fetch_keys` 作为基础信息工具，并通过工具调用结果驱动后续推理分支。planner 禁止在可调用工具前提下跳过取证直接凭空生成关键规则结论或关键路径引用。对于候选 `TaskDocument` 的合法性收口，planner 必须能够进一步使用 `lint` 工具执行只读自检，但 `lint` 不得替代 `search` 与 `fetch_keys` 的取证职责。

#### 场景:planner 使用 search 补充规则证据
- **当** DM 指令涉及规则判断（如攻击、豁免、伤害）
- **那么** planner 可以调用 `search` 检索规则原文
- **那么** 规则结论建立在检索证据之上

#### 场景:planner 使用 fetch_keys 补充状态路径证据
- **当** planner 需要引用状态路径生成步骤参数
- **那么** planner 可以调用 `fetch_keys` 枚举候选路径
- **那么** 产出的路径引用与 state 点路径语义保持一致

#### 场景:planner 使用 lint 收口候选文档
- **当** planner 已具备足够规则证据和状态路径证据并准备返回 `ready`
- **那么** planner 可以调用 `lint` 对候选 `TaskDocument` 做只读合法性校验
- **那么** `lint` 的结果只用于校验候选文档，不得被当作规则证据或状态事实来源
