## 为什么

当前 `grep` 工具依赖 `limit` 截断返回结果，这会把排序责任推给调用方，并导致高噪音查询在前几条结果里塞满无关命中。现在更需要的是先把所有命中按相关性排好序，再由上层决定是否截取前若干条。

## 变更内容

- 修改 `grep` 工具，使其默认行为不再要求或依赖固定 `limit`。
- 为 `grep` 工具增加相关性排序，让命中结果按更贴近查询表达式的相关程度返回。
- 将 `grep` 的返回项从整行字符串升级为结构化对象，至少包含 `key`、`value` 和 `sim`。
- 保留调用方按需传入 `limit` 的能力，但它应当作用在排序后的结果上，而不是先天决定扫描深度。
- 调整 `task_node` 提示词，明确教会 agent 如何构造更有效的 `grep` 查询与如何消费结构化命中结果，可使用 few-shot 和文字规则。
- 调整 smoke 和测试，使其围绕“排序质量”而不是“默认固定截断”进行验证。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `grep-tool`: `grep` 的返回语义从“按展平顺序命中并截断、返回整行字符串”调整为“先按相关性排序、返回结构化命中，再可选截断”。
- `planner-langgraph-workflow`: `task_node` 的提示词约束将更新为更明确地指导 agent 使用 `grep` 进行状态发现与证据消费。

## 影响

- 受影响代码：`src/augury/planner/tools/grep.py` 及所有依赖 `grep` 返回顺序的调用方。
- 受影响 prompt：`config/prompts/planner_task_node_system.txt` 与 `config/prompts/planner_task_node_user.txt`。
- 受影响测试：`src/tests/test_agent_grep.py`、`src/smoke/test_grep.py` 以及与 planner 相关的 smoke/test。
- 受影响行为：调用方将看到更相关的结果优先出现，并且可以直接消费 `key`、`value` 与 `sim`，而不必再自行拆解整行字符串。
