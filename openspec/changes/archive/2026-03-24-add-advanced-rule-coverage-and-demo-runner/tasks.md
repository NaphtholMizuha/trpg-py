## 1. 规则分支补齐

- [x] 1.1 更新检定逻辑与测试，覆盖 `save nat1` 不自动失败以及 `ability/skill nat20` 不自动成功。
- [x] 1.2 更新伤害逻辑与测试，覆盖暴击只翻倍伤害骰不重复固定加值，以及 `on_save=none` 的免伤分支。
- [x] 1.3 为 `select.area` 的 `line`、`cone` 与 `target` 模板补充实现校验和回归测试。

## 2. Demo 案例与展示

- [x] 2.1 补充或调整 demo 案例，至少覆盖 skipped 步骤、暴击伤害和多种范围模板中的高价值展示场景。
- [x] 2.2 重构 `main.py` 的 demo 注册方式，支持以稳定顺序运行单个案例或全部案例。
- [x] 2.3 为 `main.py` 增加集成测试，覆盖 skipped 输出、自定义布局输出和 `all` 批量运行模式。

## 3. 文档与验证

- [x] 3.1 更新 README 中的 demo 运行说明，补充批量运行全部案例的用法。
- [x] 3.2 运行 `python -B -m unittest discover -s tests -v` 并确认新增与既有测试全部通过。
