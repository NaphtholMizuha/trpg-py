## 为什么

当前状态存储能力已经形成独立层，但物理结构仍停留在单文件 `trpg_py/store.py` 加兼容层 `trpg_py/state.py` 的形态；与此同时，`engine` 目录内部也还没有进一步区分通用执行框架与战斗领域逻辑，`trpg_py/engine/operations.py` 已经承担了过多职责。现在需要把与 store 相关的代码整理为独立包，并同时把引擎内部重构为 `engine.core` 与 `engine.combat`，顺手拆分大号 `operations.py`。

## 变更内容

- 将当前单文件 `trpg_py/store.py` 重构为 `trpg_py/store/` 包。
- 把 store 相关实现与导出按照职责拆分到包内模块中，例如核心读写逻辑、兼容导出、包级入口。
- 将 `engine` 进一步划分为通用引擎层 `engine.core` 与战斗领域层 `engine.combat`。
- 将当前 `trpg_py/engine/operations.py` 拆分为多个按职责划分的 combat 模块，而不是继续由单文件承载选择、检定、伤害、效果和路径推断等逻辑。
- 调整调用方导入路径，使其依赖新的 `trpg_py.store` 包入口和新的 `engine` 包布局，而不是依赖单文件实现细节。
- 保持 `read`、`reads`、`write`、`writes`、`mod`、`mods` 的公开接口和现有语义不变。
- 保留必要兼容层，避免因文件布局变化破坏现有调用方与测试。

## 功能 (Capabilities)

### 新增功能
- `store-package-layout`: 提供一个结构化的 `store` 包布局，用于承载状态存储实现、公开导出与兼容入口。

### 修改功能
- `engine-package-layout`: 将 `engine` 细化为 `engine.core` 与 `engine.combat`，并要求 combat 相关操作逻辑不再集中在单个 `operations.py` 文件中。

## 影响

- 受影响代码：`trpg_py/store.py`、`trpg_py/state.py`、`trpg_py/engine/state.py`、`trpg_py/engine/__init__.py`、`trpg_py/engine/executor.py`、`trpg_py/engine/operations.py`、`trpg_py/operations.py`、相关测试与导出模块
- 受影响 API：主要是模块布局与导出组织方式；公开 store 接口语义保持不变，`trpg_py.engine` 的内部组织更细化
- 受影响系统：状态存储层、兼容导出层、引擎包结构约定、combat 操作模块边界
