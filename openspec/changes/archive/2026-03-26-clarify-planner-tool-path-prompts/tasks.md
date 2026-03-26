## 1. Prompt Path Semantics

- [x] 1.1 更新 `config/prompts/planner_system.txt` 与 `config/prompts/planner_user.txt`，显式区分 `fetch_keys`/`reads` 的裸 store 路径和 `TaskDocument` `$ref` 的命名空间路径
- [x] 1.2 调整 prompt 中的 canonical example 或相邻路径示例，展示 `actors...` 工具路径如何映射为最终 `state.actors...` 引用

## 2. Prompt Regression Coverage

- [x] 2.1 更新 `tests/test_agent_planner.py`，断言默认 prompt 明确包含工具路径与 `$ref` 路径的区分说明
- [x] 2.2 更新相关 smoke 或 prompt 测试，覆盖提示词不会再把 `state.actors...` 当作 `fetch_keys` / `reads` 的工具参数示例

## 3. Smoke Verification

- [x] 3.1 运行 planner smoke 场景复核“哥布林用弯刀攻击 aldera”不再因路径命名空间混淆而错误要求 DM 提供现成 state 路径
- [x] 3.2 如 smoke 仍未收敛，记录剩余失败是否来自 prompt 之外的问题，避免把实现缺陷误判为提示词问题

说明：当前环境中的 real smoke 未在超时窗口内完成；进一步诊断显示 `search` 工具返回 `APIConnectionError: Connection error.`，且本地 `http://localhost:6333` 不可达，因此剩余阻塞更像是真实检索/外部依赖问题，而不是 prompt 仍在把 `state.` 前缀误用于 `fetch_keys` / `reads`。
