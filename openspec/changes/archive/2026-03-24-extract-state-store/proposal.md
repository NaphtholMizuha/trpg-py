## 为什么

当前状态访问逻辑分散在 `trpg_py/engine/state.py`、`trpg_py/refs.py` 与 `executor/operations` 的调用点中，既有模块边界不清的问题，也让状态读写语义停留在底层的 `get_path/set_path` 风格。现在需要把状态存储能力收口为单一维护点，用更明确的批量/单项读写与修改接口支撑 engine 和其他模块。

## 变更内容

- 新增一个独立于 `engine` 的状态存储包，负责维护基于点路径的状态 map 访问能力。
- 对外仅暴露 `read`、`reads`、`write`、`writes`、`mod`、`mods` 六个状态接口，统一单项与批量读写、修改的调用方式。
- 将现有执行流程中的状态提交、引用解析、按路径取值逻辑迁移到新状态存储接口之上。
- **BREAKING**: 不再鼓励业务代码直接依赖 `trpg_py.engine.state` 中的路径工具；后续状态访问应收敛到新状态存储包公开接口。
- 保留必要兼容层，确保现有 `engine` 执行语义在迁移过程中不被破坏。

## 功能 (Capabilities)

### 新增功能
- `state-store`: 提供统一的点路径状态访问与修改接口，并作为 engine 外的共享状态存储抽象。

### 修改功能
无。

## 影响

- 受影响代码：`trpg_py/engine/state.py`、`trpg_py/engine/executor.py`、`trpg_py/engine/operations.py`、`trpg_py/refs.py`、`trpg_py/state.py`、`trpg_py/engine/__init__.py`
- 受影响 API：内部状态访问方式从路径工具函数迁移为状态存储接口
- 受影响系统：任务执行、变更提交、`$ref` 解析、按路径状态读取
