## 上下文

`extract-state-store` 已经把状态访问语义收口到了 `trpg_py.store` 导出的一组接口上，但当前实现仍然落在单文件 `trpg_py/store.py` 中。与此同时，`trpg_py/engine/operations.py` 也已经同时承担了战斗操作注册表、目标选择、检定、伤害/治疗、效果/资源、路径模板和若干辅助逻辑，文件职责过于集中。

这次变更关注的是物理结构而非行为语义：我们希望一方面把 store 提升为真正的包布局，另一方面把 `engine` 细化为 `engine.core` 与 `engine.combat`，并把 combat 操作从单文件中拆散，同时尽量不影响既有调用方。

## 目标 / 非目标

**目标：**

- 将状态存储层重构为 `trpg_py/store/` 包。
- 在包内明确区分公开入口、核心路径访问实现和兼容辅助代码。
- 将 `trpg_py.engine` 细化为 `engine.core` 与 `engine.combat`。
- 将当前 `trpg_py/engine/operations.py` 拆分为多个 combat 模块。
- 保持 `trpg_py.store` 作为稳定导入入口。
- 保持 `trpg_py.engine` 作为稳定引擎入口。
- 保持 `trpg_py.state` 与 `trpg_py.engine.state` 的兼容行为。

**非目标：**

- 不在本次变更中改变 `read`、`writes`、`mods` 等接口的语义。
- 不重新设计 store 的路径规则、错误模型或批量接口协议。
- 不在本次变更中修改 combat 操作的规则结果与执行语义。
- 不在本次变更中移除全部兼容层。

## 决策

### 1. 用目录包替代单文件模块

`trpg_py/store/` 将成为 store 层的唯一实现宿主，公开入口放在 `__init__.py`。这样可以让“store 是一层能力”在目录结构上显式可见。

考虑过的替代方案：

- 继续保留 `trpg_py/store.py`
  - 优点：改动最小
  - 缺点：扩展性和结构清晰度都较差
- 仅新增 `store_helpers.py` 等文件但不建包
  - 优点：迁移成本较低
  - 缺点：仍然无法形成统一的 store 能力边界

### 2. 包内实现按职责拆分

建议至少拆成：

- `trpg_py/store/__init__.py`: 公开导出
- `trpg_py/store/core.py`: 点路径解析与读写修改实现
- `trpg_py/store/compat.py`: 供 `state` 兼容层复用的薄包装或别名

具体文件名可以微调，但职责边界应明确。

考虑过的替代方案：

- 把全部实现仍塞进 `__init__.py`
  - 优点：导入简单
  - 缺点：只是把单文件换了位置，并未改善可维护性

### 3. 将 engine 划分为 core 与 combat 两层

`engine.core` 承载任务执行器、引用解析、执行模型和骰子等通用运行时能力；`engine.combat` 承载 `select/check/damage/heal/resource/effect/state` 这些战斗步骤及其辅助逻辑。这样可以把“如何执行任务”和“战斗步骤代表什么”从目录结构上区分开。

考虑过的替代方案：

- 继续把所有 engine 代码平铺在 `engine/`
  - 优点：改动较小
  - 缺点：领域边界不明显，后续继续扩展只会让大文件增大
- 把 `combat` 提升为与 `engine` 并列的顶层包
  - 优点：领域感强
  - 缺点：会模糊它与执行引擎的关系，也更容易形成跨包循环依赖

### 4. combat 操作按职责拆分，而不是继续维护大号 operations.py

建议将 combat 层至少拆成：

- `engine/combat/operations.py`: 轻量注册表与分派入口
- `engine/combat/select.py`: 目标选择与范围判定
- `engine/combat/check.py`: 攻击、豁免、能力、技能检定
- `engine/combat/effects.py` 或 `resolution.py`: 伤害、治疗、效果、资源等写回相关逻辑

具体文件名可以调整，但目标是让维护者不必再在单个文件中定位全部战斗逻辑。

考虑过的替代方案：

- 仅把 helper 函数挪出去，保留单个 `operations.py`
  - 优点：改动更保守
  - 缺点：主文件仍承担过多职责，结构收益有限

### 5. 兼容层继续保留在旧入口，但实现收敛到新包布局

`trpg_py.state` 与 `trpg_py.engine.state` 继续存在，但只做转发；`trpg_py.operations` 等旧入口也可以在必要时继续转发到新的 engine 子包。这样我们既能得到更清晰的内部结构，又不会立刻破坏旧测试和调用方。

## 风险 / 权衡

- 文件移动可能引入循环导入 → 将兼容层保持为最薄转发，避免 store 包反向依赖它们
- 包级导出与内部模块同名后容易产生导入混淆 → 约定调用方只依赖 `trpg_py.store` 包级入口
- `engine.core` 与 `engine.combat` 边界若划分不清，可能出现交叉依赖 → 明确 core 只放通用运行时，combat 只放战斗语义
- 拆分 `operations.py` 时容易出现辅助函数归属摇摆 → 先按“选择 / 检定 / 写回效果”三块粗粒度拆分，再视需要细化
- 结构重组本身不会带来功能收益 → 通过更清晰的后续扩展空间来抵消这类纯整理成本

## 迁移计划

1. 创建 `trpg_py/store/` 包与包级导出。
2. 将 `trpg_py/store.py` 中的实现迁移到包内模块。
3. 创建 `trpg_py/engine/core/` 与 `trpg_py/engine/combat/` 包。
4. 将 executor、refs、models、dice 等通用运行时能力收拢到 `engine.core`。
5. 将 combat 相关操作迁移到 `engine.combat`，并把大号 `operations.py` 拆分为多个模块。
6. 让 `trpg_py.state`、`trpg_py.engine.state` 及必要旧入口转发到新的包实现。
7. 更新测试与导入，确认 `trpg_py.store` 和 `trpg_py.engine` 仍是稳定入口。
8. 删除或停用不再需要的旧单文件实现，避免双重实现。

## 开放问题

- `compat.py` 是否必要，还是由 `state.py` 直接转发到 `store.core` 即可？
- store 包内是否需要进一步区分路径解析和批量操作实现，还是先维持一个 `core.py` 即可？
- combat 层在首轮拆分时是按 `select/check/effects` 三块组织，还是直接拆到更细的 `damage/heal/resource/effect` 粒度？
