# planner-execution-smoke 规范

## 目的
待定 - 由归档变更 add-planner-engine-smoke-test 创建。归档后请更新目的。
## 需求
### 需求:系统必须提供 planner 到 engine 的端到端 smoke 入口
系统必须提供一个位于 `smoke/` 目录下的手动可运行脚本，用于把 DM instruction 先交给 planner 生成 `TaskDocument`，再在 `status=ready` 时把该文档交给 engine 执行。系统禁止继续要求开发者手工在 `test_planner` 与 `test_engine` 之间搬运中间 `TaskDocument` 才能验证最终状态变化。

#### 场景:开发者一次运行观察 instruction 到状态变化
- **当** 开发者执行新的 planner+engine smoke 脚本并提供 instruction
- **那么** 脚本先调用真实 planner 获取结构化规划结果
- **那么** 若 planner 返回 `status=ready`，脚本继续执行该 `task_document`
- **那么** 输出中可见最终执行状态和关键 state 变更摘要

### 需求:端到端 smoke 必须支持测试员在 needs_human 时恢复规划
系统必须要求该脚本只在 planner 返回 `status=ready` 且包含 `task_document` 时继续调用 engine，但对于 `needs_human`，系统必须允许测试员输入审批或补充决策，并使用同一规划 thread 恢复 planner，而不是一律停止在第一次未 ready 结果。

#### 场景:planner 返回 needs_human
- **当** planner 返回 `status=needs_human`
- **那么** 脚本输出问题、缺口、可选项或恢复提示
- **那么** 脚本同时展示当前 graph 阶段或等价阶段摘要
- **那么** 脚本允许测试员输入审批、拒绝或结构化恢复负载
- **那么** 脚本使用同一 thread 或等价 graph state 恢复 planner，直到测试员退出、planner 返回 `ready` 或 planner 返回 `blocked`

### 需求:端到端 smoke 必须在 blocked 状态下停止执行
系统必须要求该脚本在 planner 返回 `status=blocked` 时直接输出错误并停止，禁止在 blocked 状态下继续调用 engine。除错误类型和错误信息外，脚本还必须让测试员能够发现本次 planner 运行对应的日志文件路径或等价定位信息，以便继续排查 blocked 根因。

#### 场景:planner 返回 blocked
- **当** planner 返回 `status=blocked`
- **那么** 脚本输出错误类型和错误信息
- **那么** 脚本不得继续调用 engine 执行
- **那么** 脚本输出中必须包含本次 planner 日志文件路径或等价定位提示

### 需求:端到端 smoke 必须支持可复现的骰子来源
系统必须让该脚本支持固定或可显式指定的骰子来源，以便开发者重复运行同一 instruction 时可以稳定观察相同的执行结果。系统禁止让该脚本只能依赖不可复现的真实随机结果。

#### 场景:开发者使用固定骰子复现一次攻击
- **当** 开发者为端到端 smoke 指定一组固定骰子值或等价的可控随机源
- **那么** engine 执行阶段使用该可控骰子来源
- **那么** 重复运行同一 instruction 时可以得到一致的最终状态变化摘要

### 需求:端到端 smoke 输出必须同时展示 planner 与 execution 摘要
系统必须让该脚本的人类可读输出和 JSON 输出同时包含 planner 阶段结果与 execution 阶段结果，便于开发者区分问题发生在规划、执行还是两者交界处。系统禁止只展示最终状态变化而隐藏 planner 的 `status`、`task_document` 或失败原因。若 planner 因缺失事实、重复失败主题或工具预算上限而提前收口，输出中还必须能让测试员区分这是正常收口而不是工具故障。

#### 场景:planner ready 后展示执行摘要
- **当** planner 返回 `status=ready` 且 engine 执行完成
- **那么** 输出中可见 planner 的 `task_id`、步骤数量或等价摘要
- **那么** 输出中可见 engine 的执行状态、步骤结果或已应用变更摘要

#### 场景:JSON 输出包含收口原因
- **当** 开发者以 JSON 模式运行该脚本且 planner 未进入 execution 阶段
- **那么** 返回体必须包含 planner 阶段的结构化结果
- **那么** 返回体必须包含缺失事实、预算耗尽或等价收口原因
- **那么** 调用方可以基于该 JSON 自动断言 planner 没有陷入无限工具循环

### 需求:端到端 smoke 的默认终端展示必须具有高可读性
系统必须让该脚本的默认人类可读输出优先服务测试员快速理解当前阶段、关键结果和最终状态变化，禁止继续停留在难以扫描的大段原始 JSON 或杂乱日志输出。必要时系统可以使用 `rich` 提供更清晰的 panel、table 或高亮摘要，也可以使用 `loguru` 记录底层运行期日志，但日志不得取代测试员默认看到的主摘要。若脚本生成或关联了 planner 文件日志，系统必须以不破坏主摘要可读性的方式提示该日志位置。

#### 场景:测试员运行脚本并快速识别当前阶段
- **当** 测试员以默认人类可读模式运行该脚本
- **那么** 输出中必须清晰区分 planner、HITL 和 execution 等阶段
- **那么** 测试员无需通读原始 JSON 即可知道当前停在哪个阶段

#### 场景:blocked 时提示日志位置但不淹没主摘要
- **当** planner 返回 `status=blocked` 或测试员需要继续排查 planner 阶段问题
- **那么** 默认输出可以提示本次 planner 日志文件路径或日志目录
- **那么** 该提示不得替代主错误摘要，也不得把默认输出退化为大段日志正文

### 需求:planner 到 engine 的端到端 smoke 必须支持正常嵌套 TOML world state
系统必须让 planner + engine 端到端 smoke 入口读取正常嵌套 TOML 的默认 world state fixture，而不是继续绑定到扁平点路径键格式。

#### 场景:开发者运行 planner + engine smoke
- **当** 开发者执行 `smoke/test_planner_engine.py` 且使用默认 world state 文件
- **那么** 脚本能在新的嵌套 TOML fixture 下成功加载默认 state
- **那么** 后续 planner 与 engine 仍基于既有点路径 state 语义运行

### 需求:端到端 smoke 必须把 needs_human 视为 staged planner 的 HITL 暂停
系统必须让 planner + engine 端到端 smoke 与 staged planner 对齐：`needs_human` 表示 graph 暂停并等待人类输入，而不是该次 smoke 的终止。脚本必须允许测试员在同一 thread 或等价 graph state 上恢复 planner。

#### 场景:staged planner 在 evidence_agent 阶段暂停
- **当** `evidence_agent` 返回 `status=needs_human`
- **那么** 脚本展示该阶段的证据小结、缺口和问题
- **那么** 脚本允许测试员输入恢复负载
- **那么** 脚本在同一 thread 或等价 graph state 上恢复 planner

#### 场景:staged planner 在 dsl_agent 阶段暂停
- **当** `dsl_agent` 返回 `status=needs_human`
- **那么** 脚本展示当前 graph 阶段与剩余问题
- **那么** 测试员恢复后脚本继续同一条规划工作流
- **那么** 脚本不得把该情况当作普通终止

### 需求:端到端 smoke 必须覆盖 planner 在缺失事实场景下的快速收口
系统必须让 planner + engine 端到端 smoke 能够验证：当 planner 在 world state 中找不到关键法术、法术位或状态路径时，会在有限工具调用内可解释地收口，而不是长时间重复取证。

#### 场景:缺失法术位时 planner 快速收口
- **当** 测试员运行 planner + engine smoke，指令依赖当前 world state 中不存在的关键法术位或已知法术
- **那么** planner 阶段必须在有限工具调用内返回可解释结果
- **那么** 输出中必须可见该缺失事实或预算耗尽的原因
- **那么** 脚本不得继续在同一阶段长时间重复相同主题的工具取证

