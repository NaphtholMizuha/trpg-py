## 为什么

上一轮变更已经补上了第一批高风险边界测试，但仍有一些对规则可信度影响很大的分支没有被正式钉住，例如非攻击检定中的天然 1/天然 20 语义、暴击只翻倍伤害骰、`on_save=none` 的免伤分支，以及 `line` / `cone` 这类范围模板。同时，`main.py` 现在一次只能跑一个 demo，不利于集中展示“系统已经支持哪些案例、输出是否足够让人信服”。

## 变更内容

- 扩展规则覆盖，补齐剩余高价值 Top 8 分支：`save nat1`、`ability/skill nat20`、暴击伤害只翻倍骰子、`on_save=none`、`line` 范围、`cone` 范围，以及 `main.py` 对 `skipped` 和自定义布局案例的展示测试。
- 让 `main.py` 支持一次运行全部已注册 demo 案例，输出稳定顺序的汇总展示。
- 为这些分支补充更贴近人类阅读的 demo 场景和集成测试，让演示不仅能跑，还能帮助理解与建立信任。

## 功能 (Capabilities)

### 新增功能

- `demo-runner`: 定义 `main.py` 的 demo 运行能力，包括单案例运行、批量运行全部案例，以及面向人类可读输出的展示约束。

### 修改功能

- `dnd5e-combat-operations`: 明确非攻击检定中的天然 20/1 语义、暴击伤害的骰子与固定加值处理、`on_save=none` 的伤害分支，以及 `line` / `cone` / `target` 范围模板支持。

## 影响

- `trpg_py/operations.py` 中检定、伤害和范围选择分支
- `main.py` 的 demo 注册与批量执行逻辑
- `tests/test_checks.py`、`tests/test_operations.py`、`tests/test_main.py`
- `examples/` 中的演示案例与 `README.md` 的运行说明
