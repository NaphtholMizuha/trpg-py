## 新增需求

## 修改需求

## 移除需求

### 需求: 系统必须将手动集成测试脚本集中放入 smoke 目录
**Reason**: smoke 目录不再是长期验证契约。
**Migration**: 将验证入口迁移到 `src/tests/` 与版本化评测目录，而不是保留 `smoke/`。

### 需求: 系统必须将根目录 test 前缀脚本迁移出根目录
**Reason**: 旧 smoke 布局将整体退出长期真相。
**Migration**: 将相关脚本迁移为自动测试、评测入口或直接删除。

### 需求: smoke 目录必须与自动测试发现目录职责分离
**Reason**: smoke 目录本身将不再作为长期职责目录存在。
**Migration**: 用 `src/tests/` 与版本化评测目录区分自动测试和固定案例回归。

### 需求:smoke 目录必须为 task_node 提供独立的手动验证入口
**Reason**: `task_node` smoke 将被删除。
**Migration**: 通过自动测试或新的委派式运行时评测验证上下文采集行为。

### 需求:smoke 目录必须为 dsl_node 提供独立的手动验证入口
**Reason**: `dsl_node` smoke 将被删除。
**Migration**: 通过自动测试或新的委派式运行时评测验证求解行为。

### 需求:dsl_node smoke 脚本必须默认读取 test_task_draft 样例
**Reason**: `test_dsl.py` 不再作为长期入口存在。
**Migration**: 将样例输入迁移到自动测试 fixture 或版本化 eval case。

### 需求:dsl_node smoke 脚本必须展示 DSL 与 lint 结果
**Reason**: DSL 与 lint 观察面不再通过 smoke 脚本表达长期规范。
**Migration**: 通过结构化测试断言、评测日志或 Resolution Agent 结果输出替代。
