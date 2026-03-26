## 为什么

当前 `smoke/test_planner.py` 默认使用 fake agent、fake LLM 和脚本内伪造的工具链路，只是在本地构造三态结果，无法验证 `config/config.toml` 中的模型、接入点和 planner factory 配置是否真的可用，也无法验证 `search` 与 `fetch_keys` 是否按真实流程接通。既然这个脚本的定位是 smoke test，它应该优先帮助开发者验证“真实配置和真实工具能不能跑起来”，而不是只验证一个离线演示分支。

## 变更内容

- 将 `smoke/test_planner.py` 的默认行为改为读取 `config/config.toml` 并创建真实 planner。
- 要求 smoke 脚本直接走 `create_planner(...)` 的真实配置路径，而不是依赖 fake agent、fake LLM 或预制结构化响应。
- 要求 smoke 脚本在规划过程中使用真实 `search` 与真实 `fetch_keys` 工具链路，而不是注入假的工具对象。
- 保留对规划结果的可观察输出，但输出应来自真实调用结果，而不是脚本内部伪造。
- 在文档中明确 `smoke/test_planner.py` 的目标是验证真实 planner 配置与集成链路，不再把离线 fake 模式作为默认 smoke 路径。

## 功能 (Capabilities)

### 新增功能
<!-- 无 -->

### 修改功能
- `agent-planner`: 调整 planner smoke 脚本语义，要求默认通过统一配置测试真实 planner 与真实工具集成链路。

## 影响

- 受影响代码：`smoke/test_planner.py`、相关 README/使用说明、planner smoke 自动测试。
- 受影响系统：planner factory、项目统一配置到 smoke 脚本的接入路径、以及 planner 到 `search` / `fetch_keys` 的真实工具编排。
- 受影响验证方式：planner smoke 测试将从“离线伪造演示”转向“真实配置驱动的手动验证”。
