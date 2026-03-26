## 1. 脚本真实化

- [x] 1.1 移除 `smoke/test_planner.py` 中 fake agent、fake LLM、fake tool、预制场景响应与默认离线分支。
- [x] 1.2 让 `smoke/test_planner.py` 默认读取 `config/config.toml` 并通过 `create_planner(...)` 构造真实 planner 与真实工具链路。
- [x] 1.3 保留人类可读摘要与 `--json` 输出，但确保它们只展示真实 planner 返回结果。

## 2. 验证与文档

- [x] 2.1 更新 README 和 smoke 使用说明，明确 `smoke/test_planner.py` 用于验证真实 planner 配置链路。
- [x] 2.2 调整或新增自动测试，验证脚本读取真实配置并调用真实 planner 与真实工具入口，而不是依赖 fake 响应。
- [x] 2.3 手动运行或模拟验证 planner smoke 脚本的成功与失败输出路径，确保错误信息对配置排障可读。
