## 新增需求

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

## 修改需求

### 需求:端到端 smoke 必须支持测试员在 needs_human 时恢复规划
系统必须要求该脚本只在 planner 返回 `status=ready` 且包含 `task_document` 时继续调用 engine，但对于 `needs_human`，系统必须允许测试员输入审批或补充决策，并使用同一规划 thread 恢复 planner，而不是一律停止在第一次未 ready 结果。

#### 场景:planner 返回 needs_human
- **当** planner 返回 `status=needs_human`
- **那么** 脚本输出问题、缺口、可选项或恢复提示
- **那么** 脚本同时展示当前 graph 阶段或等价阶段摘要
- **那么** 脚本允许测试员输入审批、拒绝或结构化恢复负载
- **那么** 脚本使用同一 thread 或等价 graph state 恢复 planner，直到测试员退出、planner 返回 `ready` 或 planner 返回 `blocked`

### 需求:端到端 smoke 的默认终端展示必须具有高可读性
系统必须让该脚本的默认人类可读输出优先服务测试员快速理解当前阶段、关键结果和最终状态变化，禁止继续停留在难以扫描的大段原始 JSON 或杂乱日志输出。必要时系统可以使用 `rich` 提供更清晰的 panel、table 或高亮摘要，也可以使用 `loguru` 记录底层运行期日志，但日志不得取代测试员默认看到的主摘要。

#### 场景:测试员运行脚本并快速识别当前阶段
- **当** 测试员以默认人类可读模式运行该脚本
- **那么** 输出中必须清晰区分 `evidence_agent`、`dsl_agent`、HITL 和 execution 等阶段
- **那么** 测试员无需通读原始 JSON 即可知道当前停在哪个 graph 阶段

## 移除需求

无
