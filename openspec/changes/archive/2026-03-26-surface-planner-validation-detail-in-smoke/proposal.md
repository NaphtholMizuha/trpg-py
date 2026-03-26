## 为什么

当前 `smoke/test_planner.py` 在 `needs_human + task_document_validation` 场景下，默认只打印泛化问题和 `reason`，开发者仍然看不见“为什么这个产出的 `TaskDocument` 不合法”。虽然这些细节已经存在于结构化结果里，但必须额外开启 `--debug` 或手动翻 JSON，日常调 prompt 和排障仍然很费劲。

现在需要把这类内部校验失败的具体原因直接暴露到 smoke 的默认人类可读输出里，让开发者一眼区分“确实缺业务信息”和“模型产物不符合合法 TaskDocument 约束”。

## 变更内容

- 调整 `smoke/test_planner.py` 的默认人类可读摘要，让 `needs_human + task_document_validation` 时直接展示具体校验失败原因。
- 明确约束 smoke 输出优先复用已有结构化失败信息，而不是要求调用方必须开启 `--debug` 才能理解失败原因。
- 为默认摘要路径补充测试，覆盖内部文档校验失败与普通澄清场景，避免输出再次退化为黑盒。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `agent-planner`: planner smoke 脚本的默认人类可读输出需要显式展示 `TaskDocument` 校验失败的具体原因，而不是只显示泛化的 `needs_human` 问题。

## 影响

- `smoke/test_planner.py` 的默认失败摘要格式
- 可能涉及 `PlannerResult` 中已有失败字段在 smoke 层的消费方式
- `tests/test_smoke_scripts.py` 以及相关使用说明
