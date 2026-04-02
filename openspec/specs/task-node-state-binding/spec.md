# task-node-state-binding 规范

## 目的
待定 - 由归档变更 fix-task-node-grep-multiple-entities 创建。归档后请更新目的。
## 需求
### 需求: TaskNode 必须在生成 reads/writes 前 grep 所有相关实体
TaskNode 在将 DM 指令翻译成 TaskDraft 时，如果 judgments 涉及多个实体（如 actor、target、weapon、spell 等），必须对每个实体分别执行 grep 查询以确认其确切状态路径。禁止在未获得 grep 证据的情况下将编造的路径写入 reads 或 writes。

#### 场景:主语与宾语均需 grep
- **当** DM 指令为 "Aldera 用火球术攻击 goblin"
- **那么** task_node 必须先 grep Aldera 的 spell_slots 和 spell_dc
- **并且** task_node 必须再 grep goblin 相关的 hp 和 dex/save 路径
- **并且** 只有在 grep 返回确切证据后，才能将这些路径写入 reads 或 writes

#### 场景:缺失实体路径时归入 missing_info
- **当** judgments 指出某目标需要进行豁免
- **并且** grep 查询未能返回该目标的 save 路径
- **那么** task_node 不得将该 save 路径写入 reads
- **并且** 应将缺失信息放入 missing_info

