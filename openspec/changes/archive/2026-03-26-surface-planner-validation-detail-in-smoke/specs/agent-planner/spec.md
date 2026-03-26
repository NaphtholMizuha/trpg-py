## 新增需求

## 修改需求

### 需求:planner smoke 脚本必须展示真实规划结果
系统必须让 `smoke/test_planner.py` 的输出直接来源于真实 planner 调用结果，禁止把预制 `ready`、`needs_human` 或 `blocked` 响应当作 smoke 输出真相。对于 `needs_human` 中由内部 `TaskDocument` 校验失败触发的场景，默认人类可读摘要也必须展示具体失败原因，禁止只剩泛化问题和抽象 reason。

#### 场景:脚本输出真实 planner 结果
- **当** planner smoke 脚本完成一次规划调用
- **那么** 人类可读摘要或 JSON 输出必须展示真实返回的 `status`
- **那么** 若返回 `ready`，输出中必须可见真实 `task_document` 摘要或正文
- **那么** 若返回 `needs_human` 或 `blocked`，输出中必须可见真实问题列表或错误信息

#### 场景:默认摘要展示内部文档失败原因
- **当** planner smoke 脚本返回 `status=needs_human` 且 `reason=task_document_validation`
- **那么** 非 `--debug` 的默认人类可读输出必须展示最后一次文档校验失败原因
- **那么** 调用方无需切换到 JSON 或 `--debug` 才能知道该产物为何不是合法 `TaskDocument`

### 需求:planner 输出必须包含可解释的缺口与假设信息
planner 在 `needs_human` 或存在推断前提时，必须返回结构化 `missing_info` 和 `assumptions` 等解释字段，禁止只返回不可审计的最终结论。若根因来自内部修复或文档校验失败，系统必须额外提供与该内部失败对应的解释字段或调试信息，而不能把 `missing_info` 退化为对用户无意义的占位值。

#### 场景:planner 返回澄清上下文
- **当** planner 需要 DM 补充法术环位或目标选择
- **那么** 返回体列出对应 `missing_info`
- **那么** 返回体说明若不澄清将导致的决策分歧

#### 场景:planner 返回内部失败上下文
- **当** planner 最终未能产出合法 `TaskDocument`
- **那么** 返回体必须保留与该失败对应的可读错误信息或解释字段
- **那么** smoke 脚本可以直接复用该信息生成默认失败摘要

## 移除需求
