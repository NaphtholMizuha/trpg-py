## 1. 默认失败摘要

- [x] 1.1 调整 `smoke/test_planner.py` 的 `needs_human` 失败摘要逻辑，在 `task_document_validation` 场景下直接展示具体校验失败原因
- [x] 1.2 确认默认摘要优先复用已有结构化字段，不要求用户必须开启 `--debug`

## 2. 验证与说明

- [x] 2.1 为 smoke 脚本增加或更新测试，覆盖非 debug 模式下的 `task_document_validation` 失败详情输出
- [x] 2.2 更新相关说明，明确默认 smoke 输出已经会显示“为什么不是合法 TaskDocument”
