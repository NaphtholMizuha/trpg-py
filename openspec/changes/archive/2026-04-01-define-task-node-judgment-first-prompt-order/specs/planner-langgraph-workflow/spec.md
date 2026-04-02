## 新增需求

## 修改需求

### 需求:task_node prompt 必须明确指导 agent 使用 grep
系统必须要求 `task_node` 的 prompt 明确指导 agent 如何更好地使用 `grep`，禁止继续只依赖抽象高层描述让 agent 自由摸索。

#### 场景:task_node 需要从状态中发现实体与资源
- **当** `task_node` 处理需要使用 `grep` 的 instruction
- **那么** prompt 必须说明如何从自然语言实体、物品、法术或资源构造更合适的 `grep` 查询
- **那么** prompt 必须说明如何消费 `grep` 返回的 `key`、`value` 和 `sim`
- **那么** prompt 必须说明哪些低相关命中不应进入最终 `context_lines`

#### 场景:task_node prompt 使用 few-shot
- **当** `task_node` prompt 需要帮助 agent 学会稳定使用 `grep`
- **那么** prompt 可以包含 few-shot 示例
- **那么** few-shot 必须展示从 instruction 到 `grep` 使用再到任务稿取舍的代表性过程

### 需求:task_node prompt 必须采用 judgment-first 顺序
系统必须要求 `task_node` 的 prompt 明确采用 judgment-first 的内部顺序，禁止继续让 `judgments`、`reads`、`writes` 平行自由生成。

#### 场景:规则驱动任务生成 TaskDraft
- **当** `task_node` 处理法术、状态效果、豁免、反应或其他规则驱动任务
- **那么** prompt 必须先要求 agent 判断是否需要 search
- **那么** 如果需要，prompt 必须要求先 search，再形成 judgments
- **那么** prompt 必须要求 reads、writes、missing_info 和 assumptions 都围绕 judgments 再由 grep 绑定或补缺

#### 场景:根据 judgments 派生 reads 与 writes
- **当** `task_node` 已经形成 judgments
- **那么** prompt 必须要求 reads 覆盖 judgments 中声明的判定所需值
- **那么** prompt 必须要求 writes 覆盖 judgments 中声明的状态变更
- **那么** 无法绑定到 exact path 的部分必须进入 missing_info 或 assumptions，而不是直接猜测

## 移除需求
