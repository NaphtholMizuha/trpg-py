请执行以下任务:

任务ID: {task_id}
任务描述: {description}
行动者: {actor}
目标: {target}
DM批注: {dm_notes}

任务详情:
{context}

执行上下文:
{execution_context}

要求:
1. 只推进当前 `active_step_id`
2. 只返回已经成为既成事实的 `field_changes`
3. 只更新当前步骤的 `step_updates`
4. 不要输出 `proposed_fragment`
5. 不要输出 `missing_info`
6. 如果当前步骤无法推进，返回空变更

输出必须是 JSON，字段固定为：
- `success`
- `narration`
- `field_changes`
- `step_updates`
- `triggered_chains`

示例:
```json
{{
  "success": true,
  "narration": "当前步骤已执行",
  "field_changes": [],
  "step_updates": [
    {{"step_id": "step_1", "status": "completed", "note": "步骤完成"}}
  ],
  "triggered_chains": []
}}
```
