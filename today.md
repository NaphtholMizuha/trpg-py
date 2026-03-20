# 今日改动记录

## 工作流与响应机制

- 将工作流从旧的反应子图思路继续推进为扁平化主线，主流程围绕 `planner -> dm_decision -> context_builder -> resolution_builder -> decision_point_check -> resolution_runner / executor` 运行。
- 引入并强化 `DecisionPoint` 语义，统一用“决策窗口”表达可响应时机，弱化 D&D 专有“反应”命名。
- 增加阶段化结算骨架，主任务可在不同 timing 上打开决策窗口。
- 修复主任务在被响应打断后重复审批的问题：任务首次批准后会记录审批状态，恢复执行时跳过再次审批。
- 尝试支持“响应动作上的再响应”：`decision_response` 任务如果带有嵌套决策点，会先进入 `decision_point_check`，而不是直接进入 `executor`。
- 对 `negate_consequence` 增加硬保护：响应任务返回该 effect 时，会直接清空主任务待落地的结果阶段变更，避免响应成功后伤害仍然落地。

## Planner / Executor / 上下文

- 为 Planner 增加中文 `search` 查询约束，优先检索中文规则书 RAG 文档。
- 为 Planner 增加一层后处理：如果主任务里提前写死了“护盾术会被法术反制打断”之类的嵌套响应结果，会尝试剥离这类叙述，并转成真正的嵌套决策点。
- 引入 `context_builder` 节点，执行前由工作流统一读取 KV 状态并注入 `_execution_context`，保持 planner / executor 权限边界。
- `ExecutorAgent` 继续保持不直接读 KV，只消费注入后的执行上下文。

## CLI 与测试脚本

- 将 `test.py` 从基础 `argparse` 交互升级为 `Typer + Rich` 风格 CLI，改善场景展示、审批提示、决策窗口展示和交互输入体验。
- `minimax` 提供商在 `test.py` 中恢复为使用 MiniMax 官方接口：
  - `base_url = https://api.minimaxi.com/v1`
  - `api_key = MINIMAX_API_KEY`
  - 模型名调整为 `MiniMax-M2.5`
- 更新 `counterspell` 场景说明，使之反映当前目标是“支持二层响应”。

## 日志与噪音处理

- 修复 `loguru` 在第三方日志（如 `fastembed`）缺少 `extra[name]` 时抛出 `KeyError: 'name'` 的问题，改为 formatter 内部兜底。
- 处理 checkpoint / msgpack 反序列化告警的方向，减少运行时刷屏。

## Token 优化

- 压缩 `search` 工具返回：
  - 默认 `limit` 从 3 降到 2
  - 不再返回 `parent_content`
  - 正文做截断
- 压缩 `read` 工具返回：每个 KV value 只返回截断预览。
- 将 Planner / Executor 的 ReAct 最大轮数从 10 收紧到 4。
- 回退了对 `fetch_keys` 的预览化裁剪，恢复全量返回，避免丢失 key 发现能力。

## 废弃代码清理

- 删除旧 `PlannerAgent` 文件。
- 删除旧 `reaction_subgraph` 文件。
- 删除 `PotentialReaction` 兼容别名。
- 删除 `create_reaction_check_node()` 旧兼容入口。
- 清理部分遗留的旧命名文案。

## 当前已知问题

- `shield` 场景虽然已接入 `negate_consequence` 的硬保护，但仍需继续用实际日志确认“成功响应后绝不落地伤害”是否完全稳定。
- `counterspell` 场景的嵌套响应骨架已接通，但还需要继续验证：
  - 主任务不应提前宣判“法术反制结果”
  - 应在护盾术响应任务上真正弹出马利克的法术反制窗口
  - 法术反制成功后，被打断的护盾术不应继续落地
- `execution_context` 仍然偏肥，后续可继续做结构化瘦身以降低 token 开销。

## 下次建议优先做的事

1. 重新跑 `shield` 与 `counterspell` 场景，核对最新行为日志。
2. 继续把“响应动作上的再响应”做实，而不是依赖 LLM 在主任务里预判结果。
3. 缩减 `execution_context`，作为下一步最稳的 token 优化点。
