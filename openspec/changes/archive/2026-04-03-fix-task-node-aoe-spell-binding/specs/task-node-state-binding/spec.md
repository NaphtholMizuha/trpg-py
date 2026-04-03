## 新增需求

### 需求:TaskNode 必须为范围法术绑定位置相关状态证据
TaskNode 在将范围法术或其他范围效果指令翻译成 `TaskDraft` 时，必须绑定 actor、目标或其他受影响对象的位置信息，只要这些位置是覆盖判定所需前提。禁止只绑定 save 与 hp 路径而跳过位置前提。

#### 场景:Fireball 需要 actor 与 target 位置
- **当** DM 指令为 “`Aldera用火球术攻击goblin`”
- **并且** `task_node` 已根据规则判断这是一个需要范围覆盖判定的法术
- **那么** task_node 必须尝试 grep 施法者位置与目标位置等状态证据
- **并且** 只有在这些位置前提已确认或已明确列为缺口后，任务稿才算完整

#### 场景:位置不足时进入 missing_info
- **当** judgments 表明某范围效果需要依赖位置、距离或覆盖关系
- **并且** grep 查询未能返回足够的位置状态证据
- **那么** task_node 不得假装覆盖对象已确定
- **并且** 应将缺失的位置或覆盖信息放入 `missing_info`

### 需求:TaskNode 必须为具名法术绑定法术身份对应的资源路径
TaskNode 在将具名法术任务翻译成 `TaskDraft` 时，必须把法术身份对应到施法者已知或已准备法术的默认环级，并据此绑定资源路径。禁止只因为某个法术位路径先被 grep 命中，就把它当作最终资源路径。

#### 场景:Fireball 不得误绑 1 环法术位
- **当** DM 指令为 “`Aldera用火球术攻击goblin`”
- **并且** 状态中存在 `actors.aldera.spells.level_3 = ["火球术"]`
- **那么** task_node 必须优先把 `actors.aldera.spell_slots.level_3.current` 视为默认资源路径
- **并且** task_node 不得仅因为 `level_1` 法术位先命中 grep 结果，就把 `level_1` 绑定为最终写路径

## 修改需求

## 移除需求
