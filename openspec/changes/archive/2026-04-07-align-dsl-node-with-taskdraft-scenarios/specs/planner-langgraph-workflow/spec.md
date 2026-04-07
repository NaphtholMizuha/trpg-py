## 新增需求

### 需求:dsl_node 必须只翻译 TaskDraft 而不是重新理解任务
系统必须要求 `dsl_node` 将 `TaskDraft` 作为翻译真相。系统禁止 `dsl_node` 在生成 `TaskDocument` 时重新补完任务结构、重新发明缺口解释，或覆盖 `task_node` 已确认的 judgments / evidence / states。

#### 场景:dsl_node 翻译已存在缺口的 TaskDraft
- **当** `dsl_node` 接收到一个包含 `missing_info` 的 `TaskDraft`
- **那么** `dsl_node` 必须把这些缺口及其默认值语义翻译进 `TaskDocument`
- **那么** `dsl_node` 不得自行重新判断这些缺口的默认处理
- **那么** `dsl_node` 不得把 `TaskDraft` 改写成新的任务理解版本

### 需求:TaskDraft 的 missing_info 必须包含默认值语义
系统必须要求 `TaskDraft.missing_info` 不再只是自由文本字符串列表，而应包含可供下游直接翻译的默认值或默认处理语义。系统禁止继续只给 `dsl_node` 一段模糊缺口描述再要求其自行推断默认行为。

#### 场景:范围法术缺失爆点时给出默认处理
- **当** `task_node` 发现某个范围法术任务缺少爆点或覆盖判定信息
- **那么** `missing_info` 必须显式说明该缺口
- **那么** `missing_info` 必须同时给出默认值或默认处理方向
- **那么** `dsl_node` 可以直接翻译该默认值语义，而无需重新猜测

#### 场景:缺失默认值语义时视为 TaskDraft 不完整
- **当** `TaskDraft.missing_info` 只包含自由文本描述而没有默认值或默认处理语义
- **那么** 系统不得把该 `TaskDraft` 视为对 `dsl_node` 完整可翻译的中间对象契约

### 需求:dsl_node 的 few-shot 必须复用 task_node 的任务类型原型
系统必须要求 `dsl_node` prompt 的 few-shot 使用与 `task_node` 一致的任务类型原型。系统禁止 `dsl_node` 维护一套与 `task_node` 脱节的独立场景分类。

#### 场景:dsl_node few-shot 覆盖主要任务类型
- **当** `dsl_node` prompt 使用 few-shot 教模型翻译 `TaskDraft`
- **那么** few-shot 必须覆盖与 `task_node` 对齐的主要任务类型原型
- **那么** 至少必须包括单体攻击、单体法术、范围法术、治疗或增益、状态或条件效果、纯状态查询等主要类别
- **那么** 每个 few-shot 的重点必须是展示“该类型的 TaskDraft 如何被翻译成 TaskDocument”

## 修改需求

## 移除需求
