## 上下文

当前 `dsl_node` 的行为已经比最初好很多：在 prompt 和 schema 收紧之后，它开始生成 `select/check/damage/resource` 这类项目内 primitive，而不再优先发明 `read/calculate/write`。但 smoke 也说明单次生成还不够稳：
- `check.save` 会漏掉 `dice`
- `damage.apply` 仍可能发明当前 engine 不支持的参数键
- `when` 可能仍然使用项目外条件表达方式
- `path` 和 `$ref` 的语义边界仍可能混用

这些问题有一个共同特点：它们都非常适合被 `lint` 识别，也非常适合被第二轮修复，而不一定需要从头重新理解整个任务。继续让人类手动多跑几次 smoke 当然能发现这些问题，但系统其实已经具备了做“局部修复编译回路”的基础：
- `dsl_node` 已经能生成结构化候选文档
- `lint` 已经能返回结构化 issues
- smoke 已经能观察当前候选文档与 lint 结果

因此，这次变更的重点不是再扩大 DSL 词表，也不是重构 `TaskDraft`，而是把已有反馈闭环真正接上。

## 目标 / 非目标

**目标：**
- 让 `dsl_node` 在首轮 candidate 不通过 lint 时自动进入 repair 回路。
- 让这个 repair 回路以内置在 `dsl_node` 中的 ReAct/tool-use 形式运行，而不是扩展成新的外层图流转。
- 让 repair 阶段显式读取 `lint` 的结构化 issues，而不是重新自由生成整份文档。
- 为 repair 回路设置有限预算，避免无限重试。
- 让提示词明确约束 `lint` 工具的调用次数与停止条件。
- 让 smoke 和自动测试可以观察 repair 回路是否发生、发生了几轮以及最终结果。

**非目标：**
- 不要求第一版 repair loop 解决所有复杂语义问题。
- 不在这次变更里发明新的 engine primitive。
- 不把 `dsl_node` 变成长期多代理系统；第一版保持单节点、有限预算、同步回路。
- 不为 repair 新增新的 LangGraph workflow 节点或 planner 阶段。
- 不要求 `lint` 具备完整的根因分析能力；只要能提供足够结构化的修复线索即可。

## 决策

### 决策 1：repair loop 必须作为 `dsl_node` 内部的 ReAct 回路实现

- 选择原因：repair 仍然属于 `dsl_node` 的编译职责，不应该提升为新的 LangGraph 阶段。把 `lint` 作为 agent 在 node 内部可调用的工具，更符合“会自检的编译代理”这个模型。
- 方案：外部 workflow 仍保持 `task_node -> dsl_node -> end`。`dsl_node` 内部由 `langchain.create_agent` 创建的 agent 通过 ReAct 方式生成候选文档、调用 `lint`、观察 issues 并修复。
- 替代方案：在 workflow 里新增 `lint_node` / `repair_node`，或由 Python 外层循环显式编排每一轮。
- 未选择原因：会把编译器内部细节泄漏到外层图结构，也会削弱 agent 对工具反馈的直接消费能力。

### 决策 2：提示词必须显式约束 `lint` 的最小/最大调用次数与停止条件

- 选择原因：如果只允许“可以调用 lint”，模型可能不调用、过度调用，或者不知道预算耗尽时该如何收束。
- 方案：prompt 必须明确规定：
  - 最终返回前必须调用 `lint`
  - 首轮 `lint` 不通过时，可以继续调用 `lint` 进行 1 到 2 轮修复验证
  - 达到预算上限后必须停止，并返回最后 candidate
  - 一旦 `lint` 返回 `valid` 必须立刻停止
- 替代方案：只在代码里做外层计数，不把调用预算写进提示词。
- 未选择原因：这会让 agent 的工具使用策略不透明，也不符合 ReAct 主导的设计目标。

### 决策 3：repair 阶段必须显式区分于首轮生成阶段

- 选择原因：首轮生成的任务是“从 TaskDraft 降级到 DSL”，而 repair 的任务是“尽量保留合法部分，只修复 lint 明确指出的问题”。这两种认知模式不一样。
- 方案：为 repair 提供独立消息结构或独立 prompt 段，至少包含：
  - 原始 `TaskDraft`
  - 当前 candidate `TaskDocument`
  - `lint` 的结构化 issues
  - 明确要求尽量保留已合法步骤，不要无谓重写整份文档
- 替代方案：简单重复调用首轮 prompt，并附上一句“请修复”。
- 未选择原因：容易让模型每轮都重新生成整份文档，降低收敛性。

### 决策 4：repair loop 只承诺修“参数契约和局部 DSL 形式错误”

- 选择原因：当前 smoke 暴露的错误主要是 primitive 参数模板和表达形式错误，这正是 repair 最擅长的区域。
- 方案：第一版 repair 主要面向：
  - 缺少必需参数
  - 不支持的 step type / kind
  - path/ref 语义误用
  - `when` 表达式形状错误
  - damage / resource / save 参数键不符合当前 engine 契约
- 替代方案：同时让 repair 回路重写整个任务结构和语义规划。
- 未选择原因：这会和 `task_node` / 首轮 lowering 再次职责重叠。

### 决策 5：repair 回路结果必须对 smoke 可见

- 选择原因：如果系统内部 silently 修复，开发者会很难判断是 prompt、lint 还是 repair 让结果通过。
- 方案：`src/smoke/test_dsl.py` 的输出应包含：
  - 是否触发 repair
  - 进行了几轮
  - 最终 lint 状态
  - 最终 candidate
  - 如未通过，最终 issues
- 替代方案：只输出最后一版文档，不暴露 repair 过程。
- 未选择原因：会让调试变得不透明。

## 风险 / 权衡

- [风险] repair 回路可能每轮都重写整份文档，导致本应收敛的问题反而漂移
  - 缓解措施：repair prompt 显式要求保留已合法部分，并限制轮数。

- [风险] `lint` 的 issues 还不够细，repair 回路可能拿到模糊反馈
  - 缓解措施：第一版先依赖当前已有 issues；若 smoke 发现某类错误仍难修，再回头细化 lint。

- [风险] smoke 输出会变长
  - 缓解措施：优先展示轮次、最终状态和最终文档，把中间信息压成摘要。

## Migration Plan

1. 为 `dsl_node` 增加 repair 回路状态和预算控制。
2. 在 prompt 中加入 `lint` 工具调用预算、停止条件和 repair 策略约束。
3. 定义 repair 阶段的输入消息格式或 repair prompt 片段。
4. 更新测试，验证：
  - lint 非法时会进入 repair
  - agent 会按提示词约束调用 `lint`
  - 通过时会提前停止
  - 超过预算时返回最后 candidate 和最终 issues
5. 更新 smoke 输出，让 repair 回路可观察。

## Open Questions

- repair 阶段是复用现有 prompt 文件并插入 repair section，还是单独增加 repair prompt 模板更合适？
- smoke 是否需要显示每一轮 candidate 的 diff，还是只显示轮次和最终结果？
- 当 lint 返回的问题涉及“结构本身不完整”而不是局部参数错误时，repair 是否应该直接放弃并交给人类？
