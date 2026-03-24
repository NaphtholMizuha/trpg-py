## 为什么

当前引擎已经支持单体选择、范围查找和范围模板，但还缺少“目标选取是否合法”的规则层校验。对于近战攻击、远程攻击和以选点为起点的法术，仅能算出命中目标还不够，系统还必须先判断目标或施法点是否超出允许距离。

## 变更内容

- 为选择类步骤补充目标选取距离校验能力。
- 明确 `select.target` 的距离校验基于 `source_position -> target_position`。
- 明确 `select.area` 的距离校验基于 `source_position -> origin`。
- 约定目标或选点超距时，选择步骤必须失败，而不是返回空 `target_ids`。
- 为任务 JSON 增加显式声明 targeting 校验输入的结构，允许后续实现调整现有示例和执行报告。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `dnd5e-combat-operations`: 选择类原子操作需要支持目标选取距离校验，并区分单体选目标与范围选点两种测距语义。
- `dnd5e-resolution-execution`: 任务文档需要支持显式声明 targeting 校验输入，并在执行报告中区分超距失败与合法但空结果。

## 影响

- 受影响代码主要包括 `trpg_py/operations.py`、`trpg_py/executor.py`、`trpg_py/models.py` 和示例任务文档。
- `main.py` 的人类可读输出可能需要增加选择失败原因展示。
- 现有 `select.target` 和 `select.area` 的 JSON 结构会扩展新的 targeting 字段。
