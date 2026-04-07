## 新增需求

### 需求:task_node prompt 必须以执行不变量与缺口暴露为主线
系统必须要求 `task_node` 的 prompt 先识别任务的执行不变量、关键前提、受影响对象和潜在写回，再决定需要哪些工具证据。系统禁止继续把 upfront 任务分类当作主要推理入口。

#### 场景:task_node 处理规则与状态交织的任务
- **当** `task_node` 处理同时涉及规则形状、状态路径和资源绑定的任务
- **那么** prompt 必须优先引导模型明确执行目标、关键前提和安全可绑定的写回
- **那么** prompt 可以把任务原型当作辅助手段
- **那么** prompt 不得要求模型必须先完成固定任务分类后才能开始形成 `judgments`

#### 场景:task_node 暴露真实缺口
- **当** `task_node` 无法安全确认路径、覆盖范围、默认环级或受影响对象集合
- **那么** prompt 必须要求模型保留这种不确定性
- **那么** prompt 不得让模型用更像某个任务类别的表述来掩盖真实缺口

### 需求:dsl_node 必须基于 primitive 语义做 lowering 与组合
系统必须要求 `dsl_node` 根据 `TaskDraft` 的 judgments、reads、writes、evidence 和 states，理解每个 engine primitive 在执行链中的职责后再做 lowering。系统禁止继续把 `dsl_node` 默认约束为只能围绕少量任务族模板做机械填空。

#### 场景:dsl_node 生成多步 DSL
- **当** `dsl_node` 需要把一份复杂 `TaskDraft` 翻译成多步 `TaskDocument`
- **那么** 节点必须能够理解哪些步骤负责确定对象集合、哪些步骤负责生成判定结果、哪些步骤负责写回状态
- **那么** 节点必须能够在当前 engine 支持的 step type / kind 范围内自由合理地组合这些 primitive
- **那么** 节点不得因为某个高层任务族未完全命中模板而放弃合理的 primitive 组合

#### 场景:dsl_node 使用 template 收敛自由组合
- **当** `dsl_node` 在自由组合 primitive 的同时使用 `template`
- **那么** `template` 必须帮助节点确认合法 shape、默认骨架与常见错误
- **那么** 节点仍必须以 primitive 运行语义和 `TaskDraft` 真相为主
- **那么** 系统不得把 `template` 视为唯一允许的 primitive 组合来源

## 修改需求

### 需求:task_node 的 few-shot 必须展示位置获取且不得复用 Fireball 评测样例
系统必须要求 `task_node` prompt 中的 few-shot 仅在确有必要时作为辅助示例，用于展示如何发现关键前提、绑定状态证据和暴露缺口。系统禁止继续把“覆盖约 5-6 个任务类型原型”作为默认硬要求。系统仍然禁止直接把 `Fireball` 写入 few-shot 作为示例，以避免 smoke 与评测样例失真。

#### 场景:few-shot 作为可选辅助而非主入口
- **当** `task_node` prompt 使用 few-shot 教模型处理 TRPG 任务
- **那么** few-shot 可以只覆盖少量高价值代表性过程
- **那么** few-shot 的主要目的必须是示范如何识别前提、取证和暴露缺口
- **那么** few-shot 不得被规定为必须覆盖固定数量的任务类型原型

#### 场景:范围效果 few-shot 展示位置前提
- **当** `task_node` prompt 使用 few-shot 教模型处理范围效果任务
- **那么** few-shot 必须显式展示读取 actor / target 位置、再判断覆盖关系或暴露缺口的过程
- **那么** few-shot 不得只展示 save / hp / spell slot 绑定而省略位置前提

#### 场景:Fireball 仅作为测试和 smoke 样例
- **当** 系统需要通过 few-shot 教模型学习范围任务模式
- **那么** few-shot 不得直接使用 `火球术 Fireball` 作为示例
- **那么** `Fireball` 可以继续保留在 smoke 与测试中，作为对真实泛化行为的评测样例

### 需求:task_node prompt 必须采用 judgment-first 顺序
系统必须要求 `task_node` 的 prompt 以 `judgments` 为核心组织 `TaskDraft`，并让 reads、writes、missing_info 与 assumptions 围绕执行需求和证据缺口派生。系统禁止继续把固定的分类步骤、固定的 search 仪式或平行自由生成当作默认主流程。

#### 场景:规则驱动任务生成 TaskDraft
- **当** `task_node` 处理法术、状态效果、豁免、反应或其他规则驱动任务
- **那么** prompt 必须允许模型先形成 provisional judgments，再决定是否需要 search 或 grep
- **那么** prompt 不得要求 search 一定先于任何 judgments 出现
- **那么** prompt 必须要求 reads、writes、missing_info 和 assumptions 围绕 judgments 再由工具证据绑定或补缺

#### 场景:根据 judgments 派生 reads 与 writes
- **当** `task_node` 已经形成 judgments
- **那么** prompt 必须要求 reads 覆盖 judgments 中声明的判定所需值
- **那么** prompt 必须要求 writes 覆盖 judgments 中声明的状态变更
- **那么** 无法绑定到 exact path 的部分必须进入 missing_info 或 assumptions，而不是直接猜测

### 需求:task_node prompt 必须为规则检索选择查询模式
系统必须要求 `task_node` 在规则优先任务中保留规则术语锚点、避免规则身份漂移，并仅在缺少可靠术语时转向更语义化的检索。系统禁止继续把 `term`、`balanced`、`semantic` 三种查询模式当作每次都必须显式完成的前置分类仪式。

#### 场景:存在明确规则术语锚点
- **当** `task_node` 处理包含明确规则术语的规则优先任务
- **那么** prompt 必须要求 query 保留该规则术语锚点
- **那么** prompt 不得鼓励模型把具名法术或动作先改写成宽泛规则场景再检索

#### 场景:不存在可靠规则术语锚点
- **当** `task_node` 处理规则优先任务，但当前没有可靠规则术语锚点
- **那么** prompt 必须允许模型使用更语义化的规则场景描述
- **那么** prompt 必须要求模型在规则身份不明确时保守处理
- **那么** prompt 不得要求模型先完成固定的三选一查询模式判定才能继续 reasoning

## 移除需求
