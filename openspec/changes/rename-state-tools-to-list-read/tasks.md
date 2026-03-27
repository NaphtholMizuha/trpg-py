## 1. 重命名状态工具

- [x] 1.1 将 `trpg_py.agent.tools` 中面向 planner 的路径枚举工具公开名改为 `list`，并同步更新描述、导出入口与默认注册
- [x] 1.2 将 `trpg_py.agent.tools` 中面向 planner 的值读取工具公开名改为 `read`，并同步更新描述、导出入口与默认注册
- [x] 1.3 明确旧 `fetch_keys` / `reads` helper 或导出是否保留兼容别名，并实现对应迁移策略

## 2. 增强 no-match 建议路径

- [x] 2.1 为 `list` 设计并实现 `status=no_match` 时的建议路径返回结构
- [x] 2.2 为 `read` 设计并实现 `status=no_match` 时的建议路径返回结构
- [x] 2.3 实现基于当前 state 点路径集合的建议排序逻辑，并限制建议数量与输出噪声
- [x] 2.4 更新 `list` / `read` 的 loguru 日志摘要，使无命中场景可观察建议数量或样本

## 3. 接入 planner 与 smoke 入口

- [x] 3.1 将 planner 默认工具集、prompt 模板与相关文案从 `fetch_keys` / `reads` 更新为 `list` / `read`
- [x] 3.2 调整 planner 相关日志、调试输出与 smoke 人类可读摘要，使其统一使用 `list/read/search/lint` 心智模型
- [x] 3.3 让 planner 在 `list` / `read` 返回建议路径时能够继续收敛取证，而不是机械重复原失败路径

## 4. 测试与验证

- [x] 4.1 更新工具层单元测试，覆盖 `list` / `read` 的命中、无命中、建议路径与错误语义
- [x] 4.2 更新 planner、prompt、日志与 smoke 测试断言，覆盖新工具名与建议路径行为
- [x] 4.3 手动运行相关 smoke 入口，验证默认输出、JSON 输出和 no-match 场景都能正确展示 `list/read` 语义
