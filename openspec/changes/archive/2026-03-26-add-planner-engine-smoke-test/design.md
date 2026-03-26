## 上下文

当前仓库已经有两个相邻但割裂的手动验证入口：
- `smoke/test_planner.py` 负责把 DM instruction 交给真实 planner，并展示 `ready / needs_human / blocked` 等结构化结果。
- `smoke/test_engine.py` 负责执行预先准备好的 `TaskDocument` demo，并展示步骤结果与状态变更。

当我们想验证“这条指令最终会不会真的改对 state”时，开发者需要先跑 planner、手工取出 `task_document`、再拼到 engine 入口里继续验证。这不仅慢，也让 planner 与 executor 之间的交界问题缺少一条稳定、可复现的 smoke 链路。

这次变更同时涉及 planner 入口、engine 执行与 smoke 输出设计，因此适合单独设计，而不是把逻辑零散塞进现有两个脚本之一。

## 目标 / 非目标

**目标：**
- 提供一个新的手动 smoke 入口，从 instruction 出发，调用真实 planner，并在 `status=ready` 时继续执行 engine。
- 让开发者在一次运行中看到 planner 结果、执行状态、以及最终 state 变更摘要。
- 让测试员无需阅读大段原始 JSON 或零散日志，也能快速看懂当前停在 planner、HITL 还是 execution 的哪个阶段。
- 支持可控骰子来源，保证端到端 smoke 至少在本地与测试中可复现。
- 对 `needs_human` / `blocked` 做清晰处理：`needs_human` 时脚本收集测试员输入并继续规划，`blocked` 时停止且不误执行 engine。

**非目标：**
- 不替代 `smoke/test_planner.py` 的纯规划调试职责。
- 不替代 `smoke/test_engine.py` 的 demo 仓库与批量案例职责。
- 不改变 planner 输出契约、engine 执行契约或 `TaskDocument` 结构。
- 不要求该脚本默认覆盖所有复杂战斗规则；它只需要提供一条稳定的端到端验证路径。

## 决策

### 决策 1：新增独立 smoke 入口，而不是继续扩展 `test_planner.py`

虽然可以在 `test_planner.py` 里加一个“执行 ready 结果”的开关，但那会把“规划调试”和“端到端执行验证”两种职责继续揉在同一个脚本中。新增独立入口可以让纯 planner smoke 保持简洁，同时让新脚本自由定义 execution summary、骰子参数和最终 state 变更展示格式。

考虑过的替代方案：
- 直接扩展 `test_planner.py`：入口更少，但脚本职责会变得模糊，输出分支也更复杂。
- 让 `test_engine.py` 接受 instruction：会把 planner 依赖硬塞进本来以 demo 为中心的 engine 入口。

### 决策 2：复用现有 planner state 加载与 engine 结果摘要逻辑，而不是重写一套

新脚本应尽量复用现有 `test_planner.py` 的配置/world state 加载方式，以及 `test_engine.py` 已有的人类可读执行摘要模式。这样可以减少三份 smoke 入口之间的长期漂移，也方便开发者在输出上形成稳定心智模型。

考虑过的替代方案：
- 完全独立实现：短期更快，但后续容易和现有 smoke 输出风格分叉。
- 过早抽成共享模块：如果现在抽象过重，反而可能为了复用而牺牲脚本可读性。

### 决策 3：执行阶段只在 planner 最终返回 `ready` 时继续，但 `needs_human` 要允许测试员交互恢复

端到端 smoke 的关键边界是：planner 先产出 `TaskDocument`，只有在 `status=ready` 且存在合法 `task_document` 时，脚本才调用 engine。若 planner 返回 `needs_human`，脚本应展示问题并允许测试员输入审批或补充决策，然后用同一 thread 继续 planner；若 planner 返回 `blocked`，脚本应直接输出错误并停止。这样既保留 planner 的 HITL 语义，也避免把“不该执行”的状态伪装成 engine 问题。

考虑过的替代方案：
- 对 `needs_human` 一律停止：会让端到端 smoke 无法覆盖真实的 HITL 恢复链路。
- 对 `needs_human` 自动补默认回答继续：会掩盖真实 planner 缺口，也引入隐式假设。
- 对非 ready 状态仍尝试执行：违反现有 planner 三态契约。

### 决策 4：骰子来源必须可控且可显式指定

因为这个脚本的目标是观察最终 state 变化，执行阶段必须支持固定骰子序列或等价的可重复随机源。否则 smoke 成败会被随机波动掩盖，无法稳定判断 planner 产物和 executor 逻辑是否一致。

考虑过的替代方案：
- 永远使用真实随机：更接近真实运行，但不适合 smoke 复现和自动测试。
- 完全固定单一骰子模板：简单，但不利于后续扩展不同 instruction 的验证。

### 决策 5：优先提供更强的人类可读终端展示，必要时引入 `rich`，保留 `loguru` 处理运行期日志

这个脚本的核心使用者是手动运行 smoke 的测试员，因此默认输出应优先优化“扫一眼就知道发生了什么”。设计上应把 planner 阶段、HITL 阶段和 execution 阶段清晰分段，并突出最终 `task_id`、执行状态、关键步骤和已应用变更。若标准 `print` 难以维持清晰度，可以优先使用 `rich` 做终端排版；若需要保留运行期诊断，则继续使用 `loguru` 记录底层日志，但不应让测试员默认面对原始日志洪流。

考虑过的替代方案：
- 继续使用纯文本顺序打印：实现简单，但随着 planner 与 execution 信息叠加，输出很快会变得难扫读。
- 只输出 JSON：适合机器断言，但不适合作为人工 smoke 的默认体验。
- 默认打印大量 `loguru` 日志：适合排障，不适合作为测试员主视图。

## 风险 / 权衡

- [端到端脚本会比现有 smoke 更慢] → 保持它是单条 instruction 的手动验证入口，而不是批量测试替代品。
- [planner 与 engine 输出揉在一起后可读性下降] → 在输出中显式分段展示 planner 阶段与 execution 阶段摘要。
- [HITL 交互让脚本流程更复杂] → 复用现有 planner smoke 的 thread/resume 交互模式，避免再发明一套输入协议。
- [引入 `rich` 或额外展示层会增加维护成本] → 只在 smoke 入口层使用轻量展示封装，不把展示库渗透进 planner 或 engine 核心逻辑。
- [真实 planner 依赖外部模型/检索，导致脚本易受环境影响] → 保留当前 smoke 设计思路，允许 JSON 输出和自动测试通过 fake planner / controlled payload 覆盖脚本逻辑。
- [三份 smoke 入口长期漂移] → 优先复用现有 state 加载和执行摘要模式，必要时再抽共享辅助函数。

## 迁移计划

1. 新增独立的 planner+engine smoke 脚本，先打通 instruction -> planner -> execute_task 的主链路。
2. 为脚本加入 JSON 与更高可读性的人类可读摘要输出，必要时接入 `rich` 或配套展示辅助，并补充固定骰子参数。
3. 接入 `needs_human` 的测试员输入与 resume 链路，保证脚本可以在同一轮 smoke 中继续规划直到 `ready`、`blocked` 或用户退出。
4. 为脚本补自动测试，覆盖 ready 执行、`needs_human` 恢复、`blocked` 停止，以及最终状态变更摘要。
5. 保持现有 `test_planner.py` 与 `test_engine.py` 不移除，只在文档或命名上明确三者职责差异。

## 开放问题

- 新脚本应命名为 `test_planner_execute.py`、`test_planner_engine.py`，还是其他更清晰的名字。
- 固定骰子序列应通过 CLI 直接传入，还是先提供一个简单默认值并允许可选覆写。
- 终端展示应优先选 `rich` 的 panel/table 风格，还是保持纯文本默认并仅在复杂摘要处局部使用 `rich`。
