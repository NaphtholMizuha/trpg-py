## 新增需求

### 需求:task_node prompt 必须为规则检索选择查询模式
系统必须要求 `task_node` 在规则优先任务中调用 `search` 前，先判断当前任务是否存在明确规则术语，并在 `term`、`balanced`、`semantic` 三种查询模式中选择其一。系统禁止继续把所有规则检索都统一改写为 HyDE 风格自然语言查询。

#### 场景:存在明确规则术语且只需定位条目
- **当** `task_node` 处理包含明确规则术语的规则优先任务，且当前只需要确认规则条目身份
- **那么** prompt 必须引导 agent 选择 `term` 模式
- **那么** query 必须保留规则术语原词
- **那么** query 禁止被改写成宽泛的规则场景描述

#### 场景:存在明确规则术语且需要少量结算细节
- **当** `task_node` 处理包含明确规则术语的规则优先任务，且当前 judgments 还需要少量结算信息
- **那么** prompt 必须引导 agent 选择 `balanced` 模式
- **那么** query 必须保留规则术语锚点
- **那么** query 只能补充当前 judgments 真正需要确认的少量规则点

#### 场景:不存在可靠规则术语锚点
- **当** `task_node` 处理规则优先任务，但指令或 judgments 中没有可靠的规则术语锚点
- **那么** prompt 必须引导 agent 选择 `semantic` 模式
- **那么** query 可以使用中文自然语言描述规则场景
- **那么** agent 不得假装已经确认某个具体规则名称

### 需求:task_node prompt 必须区分规则身份证据与结算证据
系统必须要求 `task_node` 在消费 search 结果时区分“规则身份定位”与“规则结算理解”两类证据，禁止把语义相似但身份不明的规则命中直接当作目标规则本体。

#### 场景:术语命中用于确认规则身份
- **当** `task_node` 使用 `term` 或 `balanced` 模式命中了与术语锚点一致的规则条目
- **那么** prompt 必须引导 agent 优先将该结果视为规则身份证据
- **那么** agent 不得让其他仅语义相似的结果轻易覆盖该规则身份

#### 场景:语义命中只用于补充结算细节
- **当** `task_node` 使用 `semantic` 模式，或在 `balanced` 模式下获得更多语义相关结果
- **那么** prompt 必须引导 agent 将这些结果主要用于补充结算细节
- **那么** 如果规则身份仍不明确，agent 必须保守处理并把不确定性留在 `missing_info` 或 judgments 之外

## 修改需求

### 需求:task_node prompt 必须采用 judgment-first 顺序
系统必须要求 `task_node` 的 prompt 明确采用 judgment-first 的内部顺序，禁止继续让 `judgments`、`reads`、`writes` 平行自由生成。

#### 场景:规则驱动任务生成 TaskDraft
- **当** `task_node` 处理法术、状态效果、豁免、反应或其他规则驱动任务
- **那么** prompt 必须先要求 agent 判断是否需要 search
- **那么** 如果需要，prompt 必须要求先判断是否存在明确规则术语，再选择 `term`、`balanced` 或 `semantic`
- **那么** prompt 必须要求在 search 之后形成 judgments
- **那么** prompt 必须要求 reads、writes、missing_info 和 assumptions 都围绕 judgments 再由 grep 绑定或补缺

#### 场景:根据 judgments 派生 reads 与 writes
- **当** `task_node` 已经形成 judgments
- **那么** prompt 必须要求 reads 覆盖 judgments 中声明的判定所需值
- **那么** prompt 必须要求 writes 覆盖 judgments 中声明的状态变更
- **那么** 无法绑定到 exact path 的部分必须进入 missing_info 或 assumptions，而不是直接猜测

## 移除需求
