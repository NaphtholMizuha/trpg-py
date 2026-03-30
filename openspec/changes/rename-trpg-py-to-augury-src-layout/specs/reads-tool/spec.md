## 新增需求

## 修改需求

### 需求:reads 工具必须驻留在 agent.tools 命名空间
系统必须在 `augury.agent.tools` 命名空间下提供名为 `read` 的工具能力，并且该能力必须可以被 Python 调用方直接导入和使用，而不是仅作为 planner 内部私有辅助逻辑存在。

#### 场景:调用方从 agent.tools 使用 read
- **当** 开发者为 planner 或其他 agent 组装工具集
- **那么** 可以从 `augury.agent.tools` 访问 `read` 工具实现
- **那么** 调用方不需要自行封装状态值读取逻辑

### 需求:reads 工具必须支持可手动运行的 smoke 脚本
系统必须提供一个位于 `src/smoke/test_reads.py` 的可手动运行脚本，用于让开发者直接观察 `reads` 的值读取、无命中和错误边界，而不是只能通过单元测试断言理解该工具行为。

#### 场景:开发者运行 reads smoke 脚本
- **当** 开发者在本地执行 `src/smoke/test_reads.py` 或等价命令
- **那么** 脚本会展示至少一次命中值读取结果
- **那么** 脚本会展示至少一次无命中结果
- **那么** 开发者可以从输出中看出 `reads` 的输入输出边界

### 需求:reads smoke 脚本必须支持正常嵌套 TOML 作为默认状态来源
系统必须让 `src/smoke/test_reads.py` 读取正常嵌套 TOML world state fixture 作为默认状态来源，禁止继续假设默认 fixture 顶层键本身就是点路径字符串。

#### 场景:开发者运行 reads smoke 脚本
- **当** 开发者执行 `src/smoke/test_reads.py` 且默认状态文件为 `config/world_state.toml`
- **那么** 脚本可以直接消费嵌套 TOML 解析结果作为 state
- **那么** `reads` 工具仍然使用既有点路径输入读取对应值

## 移除需求
