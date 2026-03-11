{changes_desc}

当前状态摘要:
{state_text}

{type_specific_prompt}

工作流程：
1. 使用工具查询需要的信息（fetch_keys/read/search）
2. 分析状态变更是否触发连锁
3. 用自然语言输出连锁检测结果（不要输出JSON）

如果没有连锁反应，直接输出"无连锁反应"。