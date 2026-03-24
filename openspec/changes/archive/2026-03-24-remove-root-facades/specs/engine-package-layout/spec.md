## 新增需求

## 修改需求

### 需求:公共 API 必须保留兼容导出
系统必须继续支持调用方从 `trpg_py` 顶层导入稳定公共 API，例如 `execute_task`、`validate_task_document`、`FixedDiceRoller` 和 `RandomDiceRoller`。系统禁止要求调用方通过额外的根目录 facade 模块访问这些稳定入口。

#### 场景:现有顶层导入仍然可用
- **当** 调用方执行 `from trpg_py import execute_task, FixedDiceRoller`
- **那么** 导入成功
- **那么** 调用方无需因为内部迁移而修改这类稳定入口

#### 场景:顶层稳定入口不依赖额外 facade 模块
- **当** 开发者整理 `trpg_py` 包结构
- **那么** 顶层稳定 API 由 `trpg_py.__init__` 统一提供
- **那么** 不需要再维护 `trpg_py.executor` 或 `trpg_py.dice` 这类根目录转发模块

## 移除需求

### 需求:公共 API 必须保留兼容导出
**Reason**: 现有需求把“顶层稳定导出”与“保留根目录兼容转发模块”混在同一个要求里，无法表达新的方案 A 边界。
**Migration**: 继续使用 `from trpg_py import ...` 获取稳定公共 API；需要内部实现时改为从 `trpg_py.engine...` 或 `trpg_py.store...` 导入，不再依赖额外的根目录模块。
