## 上下文

当前 Context Agent 虽然已经接入了统一的 `ask` tool 和 interrupt/resume 语义，但 ask 的触发策略仍有一部分写死在宿主代码里。`_ask_for_actor_if_needed`、`_ask_for_target_if_needed` 和 `_ask_for_area_point_if_needed` 会先由 `_analyze_intent(...)` 产出若干布尔或分类信号，再由 Python 分支决定是否 ask 以及 ask 什么。

这会导致两个错位。第一，模型并没有真正掌握 ask 触发权，很多 ask 只是代码在“发现某个缺口类型”后替模型做了决定。第二，测试和 eval 也更容易围绕这些分支编写，逐渐把 `_ask_for_*` 这类实现细节固化成长期契约。随着 `ask` 已经被定义成可中断工具，这种分层已经不合适了。长期边界应该是：模型负责判断是否 ask 以及 ask 内容，代码只负责提供 ask 工具、承接中断恢复、校验结构化结果。

这次变更的核心不是“换一种 ask 分支写法”，而是把 ask 策略从宿主实现中整体拿掉，让 Context Agent 真正通过模型推理决定是否澄清。

## 目标 / 非目标

**目标：**
- 删除 Context Agent 中按 actor、target、area point 等缺口类型拆开的代码级 ask 触发函数。
- 让 ask 的触发、问题文本、选项和默认值来自模型输出，而不是来自宿主代码模板。
- 保留 `_analyze_intent(...)` 或后续等价逻辑对上下文的归纳能力，但把它降级为模型可消费的分析材料，而不是 ask 决策器。
- 调整 prompt、eval 和测试，让它们验证“模型是否在合适的时候 ask”，而不是“某个 if 分支是否被命中”。

**非目标：**
- 本次不否定结构化 ask 请求本身；保留 `AskRequest` / `AskResponse` 契约。
- 本次不移除 interrupt/resume 语义，也不回退到 ask request emitter 模式。
- 本次不要求一次性重写整个 Context Agent 为完全不同的运行时框架。
- 本次不保证模型从此一定更少 ask；本次关注的是 ask 决策边界，而不是 ask 数量优化。

## 决策

### 决策 1：移除 `_ask_for_*` 策略函数，改为模型直接输出 ask 决策

`_ask_for_actor_if_needed`、`_ask_for_target_if_needed`、`_ask_for_area_point_if_needed` 的共同问题不是代码重复，而是它们把 ask 策略编码进了宿主分支。实现上应移除这类函数，改为让模型在读取意图、世界状态、已有 ask 响应和必要分析材料后，直接决定：
- 继续取证
- 返回 `ready` / `blocked`
- 或调用 `ask`

选择理由：
- 这让 ask 真正成为 agent 决策，而不是代码预设补丁。
- 这消除了“触发 ask 的真实逻辑究竟在 prompt 里还是在 Python 分支里”的双重真相。
- 这使测试可以围绕外部行为断言，而不必绑死具体缺口类别。

备选方案：
- 保留 `_ask_for_*`，只把函数名改得更抽象。未采用，因为策略仍然在代码里。
- 保留 `_ask_for_*` 但把模板挪到配置文件。未采用，因为这只是把硬编码从 Python 挪到静态配置，没有把决策权交还给模型。

### 决策 2：宿主代码只保留协议层能力，不保留业务 ask 策略

宿主代码保留的职责应限于：
- 提供 `ask` tool 调用入口
- 在 ask 触发时生成 pending interrupt
- 在恢复时把 `AskResponse` 回填给 agent
- 校验 ask 请求与回答的结构合法性

宿主代码不应再保留的职责包括：
- 根据 `actor_missing` 直接 ask
- 根据 `target_resolution_needed` 直接 ask
- 根据命中特定法术名和位置缺失规则直接 ask

选择理由：
- ask 既然是工具，宿主只应负责工具协议，而不是工具策略。
- 这能防止未来继续在代码里积累更多“某某场景特殊 ask”分支。

备选方案：
- 允许少量“高价值特例”继续在代码里判断。未采用，因为这会快速重新滑回策略散落在宿主代码中的旧模式。

### 决策 3：将 `_analyze_intent(...)` 的产物改为模型输入材料，而不是直接驱动 ask

当前 `_analyze_intent(...)` 会输出 `actor_missing`、`target_resolution_needed`、`missing_point` 等信号。它们仍然可能有价值，因为模型推理可以利用这些中间归纳结果更稳定地理解当前缺口。但这些字段的地位必须改变：
- 可以作为模型上下文的一部分
- 不能再被宿主代码直接拿来决定 ask

也就是说，分析结果应从“策略开关”降级为“推理支架”。

选择理由：
- 这允许保留一部分确定性解析收益，而不重新把 ask 策略写死。
- 这比彻底移除所有分析逻辑更现实，也更利于逐步迁移。

备选方案：
- 彻底删除 `_analyze_intent(...)`。未采用，因为当前 agent 仍依赖这部分归纳来稳定组织证据与状态。

### 决策 4：prompt 必须明确 ask 的判定责任属于模型

当前 `planner_context_agent_user.txt` 已经写了“当你已经能把问题收敛成明确的 DM 澄清请求时，优先产出结构化 ask_requests”。这次还需要进一步强调：
- ask 是否必要由模型判断
- 只有在现有证据不足以安全 grounding 时才 ask
- 不得因为“看见 actor/target/position 字段缺口”就机械地产生 ask

提示词要把 ask 定位为模型在多种可行动作中的一种，而不是默认 fallback。

选择理由：
- 如果不在 prompt 层显式重申责任边界，删除 `_ask_for_*` 后模型可能仍然缺少清晰的 ask 策略约束。
- 这能让行为真相回到提示词和模型输出，而不是隐藏在宿主分支中。

备选方案：
- 只改代码，不改 prompt。未采用，因为这样会把 ask 策略从显式代码变成隐式漂移，长期更难维护。

### 决策 5：测试和 eval 必须从“命中特定 ask 分支”转向“观察 ask 是否由模型决定”

自动测试需要避免继续依赖以下实现细节：
- `_ask_for_actor_if_needed` 一定存在
- 火球术缺位置一定由代码立即发出 `area_point`
- 目标歧义一定由固定分支构造 `target_disambiguation`

更合适的断言是：
- 在证据不足时，agent 能返回结构化 ask 或其他合法阻塞结果
- ask 出现时，interrupt/resume 仍然成立
- ask 请求格式合法且能驱动恢复

选择理由：
- 否则每次实现重构都会被旧测试拖回代码策略分支。
- eval 应观测外部语义，而不是内部 if/else 路径。

备选方案：
- 继续用当前回归测试固定 ask 的具体问题 ID 和触发前提。未采用，因为这会把实现细节升级成协议。

## 风险 / 权衡

- [删除代码级 ask 策略后，模型行为可能变得更发散] → 通过更明确的 prompt 契约、结构化 ask schema 和回归样例来收敛。
- [保留 `_analyze_intent(...)` 作为支架仍可能被重新滥用为策略开关] → 在实现和测试中明确禁止任何分析字段直接驱动 ask。
- [现有测试可能大量失败，因为它们把 ask 分支当成长期真相] → 将测试重写为外部行为断言，并把少量稳定字段限制在协议层而非策略层。
- [模型可能在某些原本由代码兜底的场景下选择不 ask] → 允许返回 `blocked` 或其他结构化结果，只要这来自模型判断且符合规范。

## 迁移计划

1. 先更新 prompt 和 spec，明确 ask 决策权属于模型而非宿主代码。
2. 重构 `ContextAgent.run(...)` 与相关控制流，移除 `_ask_for_actor_if_needed`、`_ask_for_target_if_needed`、`_ask_for_area_point_if_needed`。
3. 将现有意图分析结果改为模型输入材料或内部归纳结果，不再直接触发 ask。
4. 更新 eval 与自动测试，移除对特定 ask 分支和固定问题模板的实现级依赖。
5. 运行回归测试，确认 interrupt/resume 与 ask 协议仍然成立。

回滚策略：
- 若模型驱动 ask 在短期内过于不稳定，可暂时保留分析结果作为 prompt 输入增强，而不是恢复 `_ask_for_*` 策略函数。
- 若个别场景出现明显退化，可通过 prompt 或 few-shot 收敛，而不是重新把场景特判写回宿主代码。

## 开放问题

- `_analyze_intent(...)` 最终是保留为纯内部工具，还是进一步外显成模型可见的结构化 scratchpad。
- ask 的 `question_id` 是否仍应保持部分稳定命名，还是完全允许模型自由生成后再做协议层规范化。
- 对于“模型选择不 ask 但返回 blocked”的场景，eval 应该如何定义正向预期，避免再次滑回“必须 ask 某个问题”的固定答案。
