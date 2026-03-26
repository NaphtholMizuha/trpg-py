## 为什么

当前 `smoke/test_planner.py` 只能展示 planner 的最终三态结果，无法让开发者看见规划回合中的工具调用、结构化输出、修复反馈和最终校验失败原因。这样一来，`needs_human`、`blocked` 与“模型生成了非法 TaskDocument 但被重试后折叠”的情况很难区分，排查过程接近黑盒。

现在需要补充 planner smoke/debug 可观测性，让开发者能快速判断问题来自外部依赖、证据收集、结构化输出还是执行器校验，并避免把系统内部失败误解释为用户信息不足。

## 变更内容

- 为 planner 增加面向调试的可观测输出，覆盖规划回合、工具调用、结构化响应、修复反馈与最终校验结果。
- 扩展 `smoke/test_planner.py`，支持以更适合人工排查的方式展示调试信息，同时保留当前简洁摘要与 JSON 输出能力。
- 明确区分“真实需要人类澄清”和“系统未能产出合法 TaskDocument”等失败语义，避免误导调用方。
- 为 smoke/debug 可观测性补充测试，覆盖成功、修复、校验失败与外部依赖故障等代表性场景。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `agent-planner`: 扩展 planner 与 planner smoke 脚本的可观测性和失败解释能力，使开发者可以看到规划调试轨迹并区分澄清分支与内部产物失败。

## 影响

- `trpg_py/agent/planner.py` 的结果组织与调试元信息暴露方式
- `smoke/test_planner.py` 的 CLI 参数与人类可读输出/JSON 输出结构
- `tests/test_agent_planner.py` 与 `tests/test_smoke_scripts.py` 的覆盖范围
- 依赖 planner 三态结果的调用方调试体验与排障路径
