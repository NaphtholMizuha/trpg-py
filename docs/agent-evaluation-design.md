# Agent 系统评测设计

## 目标

为当前 TRPG agent 系统建立一套可持续运行的评测方案，用来回答三个问题：

1. 当前系统到底好不好用
2. 最近改动有没有把已有能力搞退化
3. 不同模型 / prompt /工作流版本，谁更稳

这里的“评测”不是单纯看 LLM 输出顺不顺眼，而是围绕当前项目真实架构定义：

- `planner`
- `executor`
- `resolver`
- `workflow`
- `commiter`

也就是说，评测目标必须贴近项目真正关心的结果：

- 任务是否被正确规划
- 执行结果是否结构化、可提交、符合上下文
- 同窗口冲突是否被正确裁决
- 最终 world-state 是否正确落地
- 成本、延迟、稳定性是否在可接受范围内

## 为什么现在需要正式评测

当前仓库已经具备不少“局部正确性”保障：

- `tests/unit/` 中已有类型归一化、fallback、window 逻辑等单元测试
- `test.py` 可以跑一条人工观察流程
- `TaskExecution` / `ExecutionResult` / `ResolutionResult` 都有结构化 schema

但还缺少真正意义上的 agent 评测体系。

当前缺口主要有：

- 没有标准化场景集
- 没有 gold expectation
- 没有把“看起来还行”转换成稳定指标
- 没有 provider / model 对比框架
- 没有回归阈值，无法作为改 prompt / 改工作流后的发布门槛

## 设计原则

- 评测以项目任务成功为中心，而不是以通用 LLM 指标为中心
- 优先定义可自动运行的评测，再辅以少量人工复核
- 区分“单 agent 能力”和“端到端 workflow 能力”
- 能定位问题归因到 `planner` / `executor` / `resolver` / `commiter`
- 支持不同 provider / model / prompt 版本横向对比
- 尽量减少随机因素，保证回归结果可解释

## 非目标

V1 评测系统不追求：

- 学术 benchmark 风格的通用 reasoning 排名
- 对所有开放式叙事输出做自动语义打分
- 一开始就覆盖所有跑团类型和规则系统
- 一开始就做复杂的人类偏好建模

V1 的目标更务实：

“让这个项目能稳定比较不同版本在关键场景下的表现，并及时发现退化。”

## 当前系统结构与评测边界

当前主流程是：

`planner -> task_approval -> executor -> window_review -> resolver -> commiter -> planner`

因此评测也应按对应层次来拆。

### Layer 1: 组件契约评测

对象：

- `DeepPlannerAgent.plan()`
- `ExecutorAgent.execute()`
- `ResolverAgent.resolve()`

关注点：

- 输出 schema 是否合法
- 关键字段是否齐全
- 是否满足当前代码约束
- fallback / sanitize 是否按预期工作

### Layer 2: 场景级 workflow 评测

对象：

- `create_workflow()` 编译后的整条工作流

关注点：

- 输入一个 DM 指令后，最终 world-state 是否正确
- 中间是否正确打开 / 关闭结算窗口
- 是否出现不该有的 stalled、脏 chain、错误写回

### Layer 3: 运行质量评测

对象：

- 整条 agent 调用过程

关注点：

- 成本
- 延迟
- 工具调用次数
- 结构化输出失败率
- fallback 触发率
- 运行稳定性

## 评测目标分解

### 1. Planner 评测

Planner 的核心不是“文案漂亮”，而是是否产出可执行的任务。

重点指标：

- `task_id` 是否存在
- `description/context` 是否非空
- `actor/target` 是否合理归一
- `write_targets` 是否只指向允许写回的字段级路径
- `context` 是否覆盖 executor 真正需要的旧值和规则背景
- 是否错误地把 executor 能解决的问题上抛给 DM

### 2. Executor 评测

Executor 的核心不是“会不会讲故事”，而是是否产出可提交结果。

重点指标：

- `ExecutionResult` 是否合法
- `field_changes` 是否只改上下文已出现的 key
- old/new 值是否与当前上下文一致
- 该掷骰时是否调用了 `evaluate`
- 不该掷骰时是否乱调用 `evaluate`
- narration-only 场景是否正确表达“仅打开窗口 / 未直接落地”

### 3. Resolver 评测

Resolver 的核心是“同窗口裁决正确”，不是单字段覆盖得像不像。

重点指标：

- `ResolutionResult` 是否合法
- 是否只输出已知 path
- `source` / `discarded_by` 是否正确归一
- 冲突字段是否按 `priority/order` 处理
- 被取消的动作对应变更是否被 discard
- `resolution_summary` 是否非空且可读

### 4. Workflow 评测

Workflow 的核心是“端到端场景是否正确落地”。

重点指标：

- 最终 world-state 是否符合预期
- 窗口数量是否符合预期
- 是否在错误时机写回
- 是否遗漏后续 chain
- 是否出现 `executor_stalled`
- 是否在无效输出后仍能安全收口

### 5. 运行质量评测

重点指标：

- 单场景总耗时
- token / 调用成本
- 工具调用次数
- structured output fallback 次数
- 失败率
- 平均重试次数

## 推荐评测体系

推荐把评测分成四类。

## A. Schema / Sanity Eval

这是最基础的一层，主要保证 agent 输出不破坏系统契约。

输入：

- 一组固定输入样例

输出检查：

- Pydantic 校验是否通过
- sanitize 后是否仍保留有效结果
- path / key / operation 是否合法

这类评测成本低，适合每次 CI 都跑。

## B. Gold Scenario Eval

这是最重要的一层，围绕固定场景和预期结果做端到端验证。

每个场景应至少定义：

- 初始 world-state
- 用户输入
- 若有 interrupt，需要给出 DM 响应脚本
- 预期最终 state diff
- 预期窗口行为
- 允许的输出弹性

例如：

- `magic_missile_no_reaction`
- `magic_missile_with_shield`
- `magic_missile_with_shield_and_counterspell`
- `melee_attack_with_reaction`
- `spell_slot_consumption_only`

这层是未来最核心的回归基线。

## C. Regression / Stability Eval

同一场景多次运行，统计稳定性。

目的：

- 找出“偶发性坏输出”
- 区分稳定正确和偶然正确

适用场景：

- 不依赖随机掷骰的规划场景
- 可固定骰子结果的执行场景
- 模型升级前后的稳定性对比

建议统计：

- `pass@1`
- `pass_rate@N`
- 常见失败模式分布

## D. Human Review Eval

自动指标不能完全覆盖开放式质量，因此仍需要少量人工评审。

但人工评测要结构化，不能只靠“感觉不错”。

建议人工打分维度：

- 规则裁定是否可信
- 叙述是否清晰
- DM 交互是否自然
- 错误时的保守性是否合理
- 是否明显越权或自造规则

适合用于：

- 大改 prompt 后抽样复核
- 选择 provider / model
- 新增复杂 mechanic 后验收

## 评测对象与数据格式

推荐新增一个专门的评测数据目录：

`evals/`

建议结构：

```text
evals/
  planner/
    cases/
  executor/
    cases/
  resolver/
    cases/
  workflow/
    cases/
  fixtures/
    world_states/
  reports/
```

## Case Schema

建议统一用 JSON 或 YAML 描述测试样例。

### Planner Case

```json
{
  "case_id": "planner_magic_missile_basic",
  "input": "马利克对艾尔德拉施放魔法飞弹",
  "expect": {
    "actor": "Malik",
    "target": "Aldera",
    "must_include_write_targets": ["Aldera.combat.HP", "Malik.spell_slots.1环"],
    "must_not_require_dm_confirmation": true
  }
}
```

### Executor Case

```json
{
  "case_id": "executor_magic_missile_damage",
  "task": {
    "...": "TaskExecution payload"
  },
  "expect": {
    "success": true,
    "must_touch_paths": ["Aldera.combat.HP"],
    "must_not_touch_unknown_keys": true,
    "allow_narration_only": false
  }
}
```

### Resolver Case

```json
{
  "case_id": "resolver_shield_counterspell",
  "window": {
    "...": "ResolutionWindow payload"
  },
  "expect": {
    "final_paths": ["Aldera.combat.HP", "Malik.spell_slots.3环"],
    "discarded_paths": ["Aldera.spell_slots.1环"],
    "must_not_emit_unknown_paths": true
  }
}
```

### Workflow Case

```json
{
  "case_id": "workflow_magic_missile_shield_counterspell",
  "initial_world_state": "fixtures/world_states/counterspell.toml",
  "user_input": "马利克对艾尔德拉施放魔法飞弹",
  "interrupt_script": [
    {
      "type": "resolution_window_review",
      "resume": {
        "action": "append_same_window_action",
        "user_input": "艾尔德拉用反应施放护盾术",
        "priority": 5
      }
    },
    {
      "type": "resolution_window_review",
      "resume": {
        "action": "append_same_window_action",
        "user_input": "马利克用反应施放法术反制",
        "priority": 4
      }
    },
    {
      "type": "resolution_window_review",
      "resume": {
        "action": "close_window"
      }
    }
  ],
  "expect": {
    "final_state": {
      "Aldera.combat.HP": "35/44",
      "Aldera.spell_slots.1环": "3/4",
      "Malik.spell_slots.3环": "1/2"
    },
    "window_count": 1,
    "must_not_stall": true
  }
}
```

## 评分模型

V1 不建议一开始就做单一总分，而是使用“门槛 + 分项分”。

原因：

- 这个项目的失败常常是硬失败，不适合被平均掉
- schema 非法、错写 key、错误落地，比 narration 差一些严重得多

推荐分成：

### Hard Gates

任何一个没过，都算该 case fail：

- 结构化输出非法
- 产生未知 path
- 写回不存在的 key
- 最终 state 与 gold diff 冲突
- 出现未预期的 `executor_stalled`

### Soft Scores

通过 hard gate 后，再计软分：

- narration 可读性
- resolution_summary 质量
- 工具调用经济性
- token / 延迟表现

## 指标定义

建议至少产出以下核心指标。

### Correctness

- `schema_pass_rate`
- `gold_case_pass_rate`
- `state_diff_accuracy`
- `window_resolution_accuracy`
- `path_legality_rate`

### Robustness

- `stability_pass_rate`
- `fallback_rate`
- `stall_rate`
- `tool_error_rate`

### Efficiency

- `avg_latency_ms`
- `p95_latency_ms`
- `avg_tool_calls`
- `avg_token_usage`
- `avg_cost_usd`

### UX / Review

- `human_rule_confidence`
- `human_dm_clarity_score`

## 如何减少随机性

当前系统有两个主要随机源：

1. LLM 本身的不稳定输出
2. `evaluate` 里的掷骰随机数

为保证评测可解释，建议 V1 做以下处理。

### 1. Executor / Workflow eval 支持固定骰子

推荐给 `LogicEngine` 或 `EvaluateTool` 增加可注入 seed，或测试模式下替换为 deterministic evaluator。

目的：

- 避免同一个 case 因骰点不同而无法比较
- 把评测重点放在 agent 决策正确性，而不是随机结果本身

### 2. 保留多次运行评测

即使固定骰子，也建议对同一 case 连续运行多次，观察模型输出稳定性。

## 数据采集建议

评测 harness 应记录每个 case 的：

- case_id
- provider
- model
- prompt/version 标识
- 起止时间
- 最终 pass/fail
- 分项指标
- 失败原因
- 关键中间产物快照

关键中间产物建议包括：

- Planner 输出的 `TaskExecution`
- Executor 输出的 `ExecutionResult`
- Resolver 输出的 `ResolutionResult`
- 最终 state diff

不建议默认存整段完整消息历史，除非 case fail 或显式开启 debug。

## 推荐实现结构

建议新增：

`src/evals/`

推荐模块：

- `src/evals/cases.py`
- `src/evals/runner.py`
- `src/evals/scorers.py`
- `src/evals/reporting.py`
- `src/evals/fixtures.py`

### `runner.py`

负责：

- 读取 case
- 调用 planner / executor / resolver / workflow
- 收集中间结果
- 交给 scorer 打分

### `scorers.py`

负责：

- 做 hard gate 判定
- 做 soft score 计算
- 生成失败原因

### `reporting.py`

负责：

- 输出终端表格
- 导出 JSON 报告
- 导出按 case 聚合的失败摘要

## 与现有代码的集成建议

### 1. 复用 `test.py` 的交互脚本思路，但不要直接在其上堆逻辑

`test.py` 更适合人工观察，不适合作为长期评测主入口。

建议新增独立 CLI，例如：

`python -m src.evals.runner workflow`

或新增：

`python test.py eval workflow`

但底层应是新的 eval runner，而不是把 `test.py` 改成巨石脚本。

### 2. 复用现有 Pydantic 类型做 gold 对比

当前已有：

- `TaskExecution`
- `ExecutionResult`
- `ResolutionWindow`
- `ResolutionResult`

评测系统应优先直接基于这些类型做断言，而不是自己发明第二套 schema。

### 3. Workflow eval 需要支持 interrupt 脚本

因为当前工作流包含：

- `task_approval`
- `resolution_window_review`

所以 workflow runner 必须支持“预录制 interrupt 响应”。

这会是端到端评测能否自动化的关键。

## 失败归因

评测系统不能只告诉我们“挂了”，还要能尽量告诉我们“挂在哪一层”。

建议按以下优先级归因：

1. `planner_contract_failure`
2. `executor_contract_failure`
3. `resolver_contract_failure`
4. `workflow_interrupt_failure`
5. `commiter_state_mismatch`
6. `runtime_failure`

例如：

- planner 没给出可写字段，就不该只报最终 state 错
- resolver 输出了未知 path，就不该只归类为 workflow fail

## 报告形式

V1 建议至少输出两种报告。

### 1. 终端摘要

例如：

```text
Eval Summary
- provider: deepseek
- model: deepseek-chat
- total cases: 20
- passed: 16
- failed: 4
- gold_case_pass_rate: 80.0%
- avg_latency_ms: 4120
- fallback_rate: 15.0%
```

### 2. JSON 报告

适合后续做版本对比和趋势图。

建议路径：

`evals/reports/<timestamp>-<provider>-<model>.json`

## 推荐首批场景集

V1 不要贪多，建议先做 10 到 15 个高价值 case。

推荐优先覆盖：

1. 单步攻击命中并扣血
2. 单步攻击未命中
3. 法术位消耗但无直接伤害
4. 治疗法术恢复 HP
5. 魔法飞弹无反应
6. 魔法飞弹被护盾术抵消
7. 护盾术被法术反制
8. 同路径字段冲突由 resolver 取舍
9. narration-only 执行结果不应误写回
10. 非法 path 应被 sanitize / 跳过
11. planner actor/target 中文归一
12. resolver 丢弃项 reason 正确生成

## 分阶段实施建议

### Phase 1

建立最小评测骨架：

- 定义 case schema
- 实现 planner / executor / resolver 单点评测
- 生成 JSON 报告

### Phase 2

建立 workflow 评测：

- 支持 interrupt 脚本
- 支持固定 world-state fixture
- 做 final state diff 断言

### Phase 3

建立稳定性和 provider 对比：

- 同 case 多次运行
- 多模型横向评估
- 记录 cost / latency / fallback

### Phase 4

引入人工复核层：

- 抽样失败 case
- 抽样边界 case
- 结构化人工打分

## Open Questions

### 1. narration 要不要做自动语义评分？

建议 V1 不做。先把结构正确性和 state 正确性做好，narration 先只做人审抽样。

### 2. workflow eval 是否必须走真实 LLM？

建议两层都要：

- 一层 mock / deterministic，验证工作流机制
- 一层真实模型，验证 agent 效果

### 3. 是否要把评测结果纳入 CI？

建议：

- schema / unit / deterministic eval 进入 CI
- 真实 LLM eval 先做手动或 nightly 跑

## 推荐结论

这套 agent 系统的评测，不应该定义成“模型答得像不像人”，而应定义成：

“在固定场景下，Planner / Executor / Resolver / Workflow 是否稳定地产出合法、可审计、最终 world-state 正确的结果，并且成本与延迟可接受。”

因此最合适的 V1 方案是：

- 先建立 `planner/executor/resolver` 单点评测
- 再建立带 interrupt script 的 workflow 场景评测
- 用 hard gate 把结构和状态正确性卡死
- 用软指标观察 narration、延迟、成本和 fallback

这会比单纯的人眼试跑更慢一点，但会真正让这个项目具备“可持续迭代而不回退”的基础设施。
