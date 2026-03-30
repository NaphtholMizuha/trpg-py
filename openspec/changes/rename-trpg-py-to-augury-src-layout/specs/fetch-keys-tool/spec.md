## 新增需求

## 修改需求

### 需求:fetch_keys 工具必须驻留在 agent.tools 命名空间
系统必须在 `augury.agent.tools` 命名空间下提供名为 `list` 的路径枚举工具能力，并且该能力必须可被 Python 调用方直接导入和使用。

#### 场景:调用方从 agent.tools 使用 list
- **当** 开发者为 planner agent 组装工具集
- **那么** 可以从 `augury.agent.tools` 访问 `list` 工具实现
- **那么** 调用方不需要直接编写 state 遍历逻辑

### 需求:系统必须提供可运行的 fetch_keys 演示测试脚本
系统必须提供一个位于 `src/smoke/test_fetch_keys.py` 的可直接运行测试脚本，用于让开发者直接观察 `store.keys` 与 `agent.tools.fetch_keys` 的核心行为，而不是仅依赖单元测试断言。

#### 场景:开发者运行演示脚本观察 fetch_keys 功能
- **当** 开发者在本地执行 `src/smoke/test_fetch_keys.py` 或等价命令
- **那么** 脚本会展示至少一次全量路径枚举结果
- **那么** 脚本会展示至少一次按范围枚举结果
- **那么** 开发者可以从脚本输出看出新能力的功能边界

### 需求:fetch_keys 演示脚本不必须接入统一项目配置
系统必须允许 `src/smoke/test_fetch_keys.py` 这类用于展示 `fetch_keys` 行为的仓库脚本继续使用脚本局部默认输入、fixture 文件或命令行参数，禁止把统一项目配置当作该演示脚本可运行性的强制前置条件。

#### 场景:开发者运行 fetch_keys 演示脚本
- **当** 开发者在本地执行 `src/smoke/test_fetch_keys.py` 或等价命令
- **那么** 脚本可以在不读取统一项目配置的前提下展示 `fetch_keys` 的核心行为
- **那么** 演示脚本仍然满足观察全量枚举与按范围枚举的目标

## 移除需求
