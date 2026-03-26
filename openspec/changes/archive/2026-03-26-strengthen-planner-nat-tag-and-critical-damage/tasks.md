## 1. Prompt Guidance

- [x] 1.1 更新 `config/prompts/planner_user.txt`，把 DnD5e 攻击规划模式明确成默认保留 `tags=["nat"]`
- [x] 1.2 更新 `config/prompts/planner_user.txt` 的攻击伤害示例或规则说明，明确把 `result.attack_roll.outcome == crit_success` 映射到 `damage.apply.is_critical`
- [x] 1.3 视需要同步调整 `config/prompts/planner_system.txt`，确保系统级提示不会弱化上述攻击暴击语义

## 2. Regression Coverage

- [x] 2.1 为 planner prompt 测试补断言，覆盖攻击规划示例显式包含 `tags=["nat"]`
- [x] 2.2 为 planner prompt 测试补断言，覆盖攻击后的 `damage.apply` 显式包含 `is_critical` 映射
- [x] 2.3 复核现有 lint 或 smoke 相关测试，补充不会因提示词重构而丢失暴击语义的守护

## 3. Smoke Verification

- [x] 3.1 使用固定骰子重新运行 planner+engine smoke，确认天然 20 攻击产出 `crit_success`
- [x] 3.2 使用固定骰子重新运行 planner+engine smoke，确认暴击时伤害步骤会扩骰而不是只结算普通伤害
- [x] 3.3 在变更记录中补充真实 smoke 复核结论或阻塞说明，便于后续归档

## Verification Notes

- 2026-03-26：运行 `uv run smoke/test_planner_engine.py --roll 20 --roll 4 --roll 4 --roll 4 --roll 4`，planner 返回 `ready`，执行阶段显示 `attack_roll` 输出 `outcome=crit_success`，`apply_damage` 结算为 `1d6` 暴击扩骰 `[4, 4] + 2 = 10`，`actors.aldera.hp.current` 从 `30` 变为 `20`。
