## 上下文

当前 planner 只有两类可见诊断信息：一类是工具层通过 `loguru` 打到终端的输入/输出摘要，另一类是 `debug` 模式下由 planner 返回的轮次摘要。它们能帮助判断 planner 是否调用了 `search`、`fetch_keys`、`reads` 或 `lint`，但还无法稳定解释最棘手的 `blocked` 场景，尤其是结构化输出解析失败这类在 `agent.invoke(...)` 内部直接抛出的异常。

这类失败现在会在 `planner.plan()` 中被统一压缩为异常类型和错误字符串，而 `StructuredOutputValidationError` 这类异常本身携带的 `tool_name`、底层 `source` 和 `ai_message` 等关键上下文没有被保留下来。结果就是：开发者即使重现了 blocked，也常常看不到“模型到底返回了什么脏结构化输出”，只能依赖偶发复现和终端瞬时日志。

这次变更要把 planner 运行诊断升级成正式能力，并按两个阶段落地：

- 第一阶段：补齐 run 级文件日志、轮次与异常边界日志，优先解决 blocked 根因不可追的问题。
- 第二阶段：补齐更细的 prompt/response/repair 快照，并让 smoke 入口自动把本次运行对应的日志文件位置暴露给开发者。

## 目标 / 非目标

**目标：**
- 为每次 planner 运行自动生成可定位的详细日志文件，并统一写入项目内 `logs/` 目录。
- 在 blocked 尤其是结构化输出失败场景下，保留足够的原始诊断上下文，帮助开发者判断问题来自模型、网关、结构化输出策略还是 planner 自身修复逻辑。
- 以两阶段方式定义日志覆盖范围，让实现可以先交付高价值的 blocked 诊断，再逐步扩展到轮次级细粒度快照。
- 让 `smoke/test_planner.py` 与 `smoke/test_planner_engine.py` 在不牺牲默认高可读摘要的前提下，帮助开发者找到本次运行对应的日志文件。

**非目标：**
- 不在本次设计中引入外部 tracing 平台、LangSmith 或可视化工作流追踪。
- 不在本次设计中改变 planner 的 `ready / needs_human / blocked` 三态契约。
- 不在本次设计中要求把完整 world state、全部消息历史或完整 token 级原始数据都写入日志。
- 不在本次设计中重写工具层已有的 `loguru` 摘要日志约定。

## 决策

### 决策: 使用按次运行的 planner 文件日志，而不是单一追加日志

planner 将为每次运行创建独立日志文件，路径位于项目内 `logs/planner/` 下，并带有日期目录、时间戳与 run 标识，以便开发者把一次 blocked 与一份具体日志稳定对应起来。独立日志文件比单一追加文件更适合手动排障，因为它避免不同运行之间互相污染，也不需要开发者先从混合日志里切割本次会话。

考虑过的替代方案：
- 单一 `planner.log` 追加写入：实现最简单，但在并发、重试和多次 smoke 调试下很快变得难以检索。
- 完全依赖终端 `stderr` 输出：无需文件管理，但 blocked 的关键上下文仍然会随着终端滚动丢失。

### 决策: 在 planner 核心层定义 run 级日志事件，在 smoke 层负责暴露日志位置

日志事件应由 planner 核心层产生，因为只有这一层同时知道请求元数据、轮次边界、修复反馈、结构化输出校验与最终 blocked 原因。smoke 入口负责把“本次日志文件在哪里”展示给开发者，但不负责定义 planner 的核心日志语义。

这样可以避免日志能力只存在于 `smoke/` 脚本中，导致库内直接调用 `create_planner()` 时再次变成黑盒。

考虑过的替代方案：
- 只在 smoke 脚本里拼接日志：对手动调试有帮助，但库调用场景仍然缺少同等诊断能力。
- 只在 planner 内默默落日志、不在 smoke 暴露路径：日志确实存在，但开发者仍然不知道该看哪一个文件。

### 决策: 第一阶段优先记录 run 元数据、轮次边界和 blocked 异常上下文

第一阶段聚焦最高价值的诊断信息：

- run 标识、instruction、thread_id、模型与关键配置摘要
- 每轮开始与结束、输入模式、是否进入修复
- 工具调用相关摘要与最终 planner 状态
- `StructuredOutputValidationError` 等 blocked 异常的细节，包括异常来源、schema/tool 名称，以及底层 `ai_message` 的可序列化摘要

第一阶段不要求完整 prompt 或完整消息上下文全部落盘，但必须足以解释“为什么 blocked”。

考虑过的替代方案：
- 一开始就记录所有 prompt/response 细节：信息最全，但实现与噪音都更大，不利于优先交付 blocked 根因诊断。
- 继续只记录 `str(exc)`：兼容性最好，但仍无法解决用户当前最痛的排障缺口。

### 决策: 第二阶段扩展到轮次级 prompt/response 快照与修复轨迹

第二阶段在第一阶段基础上补充更细粒度的运行快照，包括：

- 渲染后的 prompt 摘要或安全截断文本
- 每轮原始响应类型与结构化响应快照
- validation feedback、repair round 轨迹与最终修复状态
- smoke 入口对日志文件路径的自动提示

这些内容会写入文件日志，而不是默认塞进普通终端主摘要中，以维持 smoke 输出的可读性。

考虑过的替代方案：
- 只保留现有 `debug` 负载，不新增文件日志：JSON 调试可测，但无法覆盖 invoke 内部直接抛异常的黑盒区间。
- 将完整快照直接并入 `PlannerResult`：调用方可直接读取，但会扩大结果契约并带来明显噪音。

### 决策: 对结构化输出异常做专门日志分支，而不是继续统一异常处理

LangChain 的 `StructuredOutputValidationError` 除了错误字符串，还包含 `tool_name`、底层 `source` 与 `ai_message`。planner 将对这类异常进行专门日志记录，以便把“结构化输出为何非法”写入文件日志。对其他普通异常则继续保留统一处理路径，但也会记录 run/round 上下文。

考虑过的替代方案：
- 保持统一 `except Exception` 日志格式：实现简单，但最关键的结构化输出上下文仍然会被压扁。
- 为所有 provider 异常都硬编码细分处理：理论上更全，但复杂度高，第一阶段先聚焦最常见且价值最高的 structured output 失败。

## 风险 / 权衡

- [日志中包含 prompt 或模型返回片段，可能过于冗长或泄露不必要上下文] → 第一阶段以摘要和可序列化截断信息为主，第二阶段再谨慎扩展更细快照。
- [每次运行独立创建 sink 可能导致并发或资源清理问题] → 使用 run 级生命周期管理，确保每次运行结束后正确移除临时 sink。
- [不同 provider / gateway 的 `ai_message` 结构不稳定] → 采用 best-effort 序列化策略，优先记录 `content`、`tool_calls`、`response_metadata` 等稳定字段，无法序列化时回退到可读摘要。
- [新增文件日志后，开发者仍然不知道去哪里看] → 由 smoke 入口在 blocked、debug 或普通运行摘要中提示本次日志文件路径或日志目录提示。
- [日志能力只对 smoke 有用，普通库调用不易发现] → 核心日志事件放在 planner 层，smoke 只负责暴露路径，不垄断日志功能。

## Migration Plan

1. 定义 planner run 级日志路径约定和 run 标识生成策略。
2. 在 planner 核心层补充第一阶段日志事件：run 元数据、轮次边界、blocked 异常详情、最终状态。
3. 在 smoke 入口层补充日志路径提示或摘要展示，确保开发者能找到对应日志文件。
4. 扩展第二阶段日志覆盖：prompt/response 快照、repair 轨迹、结构化响应摘要。
5. 为 planner、smoke 脚本和日志工具行为补充测试，并更新 README 中的调试说明。

## Open Questions

- 是否需要把“本次 planner 日志路径”作为结构化字段暴露给 `PlannerResult`，还是仅由 smoke 入口展示即可？
- 第二阶段的 prompt/response 快照应记录完整文本，还是默认采用长度限制和字段白名单？
- 是否需要为日志文件增加未来可扩展的清理/保留策略，还是先只定义生成与定位约定？
