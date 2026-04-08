## 新增需求

### 需求:DSL 执行验证必须转移到自动化链路
系统必须将 lint 后的 DSL 执行验证迁移到 Resolution Agent 自动测试与固定评测中，禁止继续把 `src/smoke/test_dsl.py` 作为长期验证契约真相。

#### 场景:维护者验证 lint 通过后的 DSL 执行
- **当** 维护者需要验证一份 lint 通过的 `TaskDocument` 能否被真实 engine 执行
- **那么** 验证入口必须来自 Resolution Agent 自动测试、结构化执行报告或固定评测
- **那么** 系统不得再要求维护者依赖 `src/smoke/test_dsl.py` 作为长期标准路径

## 修改需求

## 移除需求

### 需求:test_dsl 必须能够把 lint 通过的 TaskDocument 交给真实 engine 执行
**Reason**: `test_dsl.py` 不再作为长期验证入口存在。
**Migration**: 将 lint 后执行验证迁移到 Resolution Agent 自动测试与固定评测。

### 需求:test_dsl 执行阶段必须使用真实 store state 并展示关键变化
**Reason**: 真实 state 变化观察面不再由 smoke 脚本承担长期契约。
**Migration**: 通过结构化执行报告、自动测试断言和评测日志展示状态变化。
