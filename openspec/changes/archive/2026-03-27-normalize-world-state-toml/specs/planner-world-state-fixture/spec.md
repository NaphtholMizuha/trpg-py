# planner-world-state-fixture 规范

## 目的
定义 planner 默认 world state fixture 的文件表示、加载边界以及与运行时点路径 state 语义之间的关系。

## 需求
### 需求:默认 world state fixture 必须采用正常嵌套 TOML 表示
系统必须要求默认 `world_state.toml` 使用正常 TOML 层级结构来表达角色、环境和资源状态，禁止继续以“顶层键为点路径字符串”的扁平格式作为默认真相。

#### 场景:开发者查看默认 world state fixture
- **当** 开发者打开默认 `world_state.toml`
- **那么** 文件以嵌套表、内联表、数组或其他正常 TOML 结构组织状态
- **那么** 开发者无需先反向展开点路径键才能理解层级关系

### 需求:默认 world state fixture 载入后必须形成与现有点路径语义兼容的嵌套 state
系统必须保证默认 world state fixture 经过加载后形成与现有 `store`、`fetch_keys`、`reads` 和 engine 兼容的嵌套 state 结构，而不是把文件格式迁移扩散成新的运行时 state 契约。

#### 场景:从嵌套 TOML 加载默认 world state
- **当** 调用方通过 smoke 或 planner 默认入口读取 `world_state.toml`
- **那么** 载入结果是可被现有点路径访问语义消费的嵌套字典/列表结构
- **那么** 调用方仍然可以使用 `actors.goblin_1.ac` 之类的点路径访问其中数据

### 需求:仓库默认 world state 示例必须统一使用同一格式
系统必须要求仓库中的默认 world state 示例与测试夹具保持同一嵌套 TOML 约定，禁止默认 fixture 与测试 fixture 长期并存两套不同表示。

#### 场景:测试辅助生成默认 world state
- **当** 测试辅助或 smoke helper 生成默认 world state fixture
- **那么** 其文件内容与仓库默认 `world_state.toml` 使用同一嵌套 TOML 约定
- **那么** 开发者不会在真实默认示例与测试示例之间切换两种不同格式
