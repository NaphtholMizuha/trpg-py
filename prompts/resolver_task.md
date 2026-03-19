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
2. `priority` 数字越小，表示事件越早发生；`priority` 数字越大，表示事件越晚发生
3. 更晚发生的 run 只能推翻与自己直接冲突的更早字段变更，不能无依据地取消无关结果
4. 最终只输出 `ResolutionResult`
5. `final_field_changes` 只保留最终仍然生效的字段变更
6. `discarded_field_changes` 只填写被判定为不生效的字段变更，并给出明确 `reason`
7. 不要编造新的字段路径；只能使用 window 中已经出现过的 `field_changes.path`
8. 不要推进窗口外的世界演化；窗口外的后续发展写进 `dm_suggestions`
9. 当前 schema 没有最终的 chains 输出字段；如果某些后续 chain 需要 DM 关注，请写进 `dm_suggestions`
