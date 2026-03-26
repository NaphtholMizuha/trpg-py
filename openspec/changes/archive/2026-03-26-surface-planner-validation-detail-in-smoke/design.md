## 上下文

planner 现在已经会在内部校验失败时返回：

- `reason = "task_document_validation"`
- 泛化的人类问题文案
- `error.type / error.message`
- 若开启 `debug`，还会带 `debug.failure_message` 与轮次级 `validation_error`

问题不在于 planner 完全没有失败信息，而在于默认的 `smoke/test_planner.py` 人类可读输出没有把这些现成字段展示出来。结果就是开发者即使已经拿到真实 smoke 结果，仍然需要重新运行 `--debug` 或切 JSON 才能知道模型到底违反了什么约束。

## 目标 / 非目标

**目标：**
- 让 smoke 脚本在非 `--debug` 下也能直接展示 `task_document_validation` 的具体失败原因。
- 优先复用现有结构化字段，避免为默认摘要再发明第二套失败数据结构。
- 保持普通 `needs_human` 场景输出简洁，不把所有调试细节都默认展开。

**非目标：**
- 不在本次设计中重写 planner 的 debug 负载结构。
- 不在本次设计中默认打印完整无效 `TaskDocument` 或完整 prompt。
- 不在本次设计中改变 `ready / needs_human / blocked` 三态契约。
- 不在本次设计中要求所有失败场景都默认展开完整轮次轨迹。

## 决策

### 决策: 默认 smoke 摘要优先展示已有 `error.message`

对于 `needs_human` 且 `reason=task_document_validation` 的场景，默认人类可读输出将直接展示已有的 `error.message`，因为它已经是 planner 在非 debug 路径下保留下来的最后一次校验失败原因。

这样可以在不改变 planner 主结果结构的情况下，让默认 smoke 输出立即可用，并避免让 `debug.failure_message` 成为唯一可见入口。

考虑过的替代方案：
- 强制要求用户加 `--debug`：实现最少，但不能满足“默认一眼看懂失败原因”的诉求。
- 新增顶层 `validation_detail` 字段：语义更显式，但在已有 `error.message` 可复用的前提下会增加重复字段。

### 决策: 仅对内部文档失败强化默认摘要，不默认展开全部 debug 轨迹

默认输出会聚焦展示：

- `reason`
- 真实失败原因摘要
- 必要时的 `error.type`

更细的轮次轨迹、修复反馈和每轮 `validation_error` 仍然由 `--debug` 负责。这样既满足默认排障需求，也避免把普通 smoke 输出变得过长。

考虑过的替代方案：
- 默认打印完整 debug 轨迹：排查更全，但会显著增加日常噪音。
- 默认打印无效 `TaskDocument` 全文：可能有帮助，但信息量过大，也不一定比最终校验错误更好读。

## 风险 / 权衡

- [某些 `needs_human` 场景同时带有 `error`，但并非内部文档失败] → 通过 `reason=task_document_validation` 或等价内部失败语义收窄默认强化展示范围。
- [仅显示最后一次错误，仍不足以解释完整修复过程] → 保留 `--debug` 作为更深层诊断入口。
- [输出字段命名不清晰] → 延续现有 `reason/detail/error` 风格，避免再引入新的摘要概念。

## Migration Plan

1. 调整 `smoke/test_planner.py` 的失败摘要逻辑，优先在内部文档校验失败场景展示具体错误信息。
2. 补充 smoke 脚本测试，覆盖非 debug 模式下的校验失败输出。
3. 更新简短说明，明确默认摘要已经能看到“为什么不是合法 TaskDocument”，更深轨迹继续使用 `--debug`。

## Open Questions

- 默认摘要是否只打印 `error.message`，还是同时附带 `error.type` 更有助于排障？
- 对于未来其他内部失败语义，是否也要沿用同一套默认摘要强化规则？
