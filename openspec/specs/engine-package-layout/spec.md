## 目的
定义核心运行时逻辑在 `trpg_py` 包内的组织边界，以及 `trpg_py` 顶层与 `trpg_py.engine` 命名空间的公共导出契约。

## 需求

### 需求:核心运行时逻辑必须归入 engine 命名空间
系统必须将执行器、原子操作分发、状态路径访问和骰子运行时能力组织在 `trpg_py.engine` 命名空间下。新增核心运行时实现禁止继续以包根目录平铺模块作为唯一归属。

#### 场景:核心逻辑通过 engine 子模块组织
- **当** 开发者查看包内执行引擎相关实现
- **那么** 执行编排、操作处理、状态访问和骰子能力位于 `trpg_py.engine` 下
- **那么** 后续新增同类运行时能力有明确的 `engine` 落点

### 需求:公共 API 必须保留兼容导出
系统必须继续支持现有调用方从 `trpg_py` 顶层导入稳定公共 API，例如 `execute_task`、`validate_task_document`、`FixedDiceRoller` 和 `RandomDiceRoller`。将内部实现迁移到 `engine` 时，禁止因模块重组而破坏这些既有入口。

#### 场景:现有顶层导入仍然可用
- **当** 调用方执行 `from trpg_py import execute_task, FixedDiceRoller`
- **那么** 导入成功
- **那么** 调用方无需因为内部迁移而修改这类稳定入口

### 需求:engine 命名空间必须提供显式引擎入口
系统必须允许调用方通过 `trpg_py.engine` 访问核心运行时入口，以支持后续按子模块扩展与集成。该命名空间必须至少暴露执行器入口和引擎常用构件，而不是仅作为空目录存在。

#### 场景:调用方可以从 engine 访问执行器
- **当** 调用方执行 `from trpg_py.engine import execute_task`
- **那么** 导入成功
- **那么** 该入口可用于执行现有任务文档
