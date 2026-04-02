## 1. Grep Ranking

- [x] 1.1 重构 `grep` 命中收集逻辑，先收集完整命中集合，再执行排序。
- [x] 1.2 为扁平化命中行实现轻量相关性打分，并保证同分结果保持稳定顺序。
- [x] 1.3 将排序后的命中结果改为结构化对象，至少返回 `key`、`value` 和 `sim`。

## 2. API Semantics

- [x] 2.1 调整 `grep` 的 `limit` 语义，使其仅作用于排序后的结果截断。
- [x] 2.2 更新 `grep` 的工具描述、输入文案和日志摘要，使其反映“结构化结果 + 排序后可选截断”的真实行为。
- [x] 2.3 更新 planner 或 smoke 调用方，使其直接消费 `key/value/sim` 而不是整行字符串。

## 3. TaskNode Prompting

- [x] 3.1 更新 `planner_task_node_system` 和 `planner_task_node_user` prompt，明确指导 agent 更好地使用 `grep`。
- [x] 3.2 在 `task_node` prompt 中加入 few-shot 示例，展示如何从 instruction 使用 `grep` 并筛选结构化命中。

## 4. Validation

- [x] 4.1 更新 `grep` 单测，验证高噪音查询时更相关的结果会排在前面。
- [x] 4.2 更新 `grep` 单测，验证显式 `limit` 只会截断排序后的结果。
- [x] 4.3 更新 `grep` 单测或 smoke，验证每条命中都包含 `key`、`value` 和 `sim`。
- [x] 4.4 更新 smoke 或相关 planner 测试，验证调用方在不依赖低 `limit` 的情况下也能拿到更有用的前几条结果。
- [x] 4.5 更新 planner smoke 或测试，验证 `task_node` prompt 能更稳定地利用结构化 `grep` 结果。
