请合并以下 ResolutionWindow：

窗口ID: {window_id}
根任务ID: {root_task_id}
根描述: {root_description}
窗口状态: {status}

字段路径提示:
{path_hints}

共享上下文:
{shared_context}

窗口内容:
{window_json}

要求:
1. 先理解每个 run 的动作含义，再判断 run 之间的关系
2. 优先把每个 run 的变更理解成三类：`resource_costs`、`primary_effects`、`contingent_effects`
3. `priority` 数字越小，表示事件越早发生；`priority` 数字越大，表示事件越晚发生
4. 默认先检查“相邻 priority 层”的 run 是否直接相互影响；不要轻易让一个 run 跳过中间层，直接推翻更远 priority 的结果
5. 非相邻 priority 的 run 默认视为不直接相互影响
6. 只有当文本中非常明确地表明“该动作就是针对那个更远层的目标施法/目标 run”时，才允许认定非相邻 priority 的 run 彼此影响
7. 更晚发生的 run 只能推翻与自己直接冲突的更早字段变更，不能无依据地取消无关结果
8. 默认情况下，`resource_costs` 不应因为后续效果被抵消就自动回滚；只有规则或文本明确说明“成本返还 / 不消耗”时，才可以丢弃对应成本
9. 最终只输出 `ResolutionResult`
10. 优先填写 `final_resource_costs` / `final_primary_effects` / `final_contingent_effects`
11. 优先填写 `discarded_resource_costs` / `discarded_primary_effects` / `discarded_contingent_effects`，并给出明确 `reason`
12. `final_field_changes` 与 `discarded_field_changes` 可以视为上述分类结果的合并视图
13. 不要编造新的字段路径；只能使用 window 中已经出现过的变更路径
14. 不要推进窗口外的世界演化；窗口外的后续发展写进 `dm_suggestions`
15. 当前 schema 没有最终的 chains 输出字段；如果某些后续 chain 需要 DM 关注，请写进 `dm_suggestions`
