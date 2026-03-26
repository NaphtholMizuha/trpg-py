## 为什么

当前 `smoke/test_planner.py` 使用脚本内联的极简 state，只包含少量 actor 字段和一个 `to_hit` 数值，无法像真实桌游场景那样给 planner 足够的世界信息。这会让 planner 经常在取证阶段就因为缺少攻击细节、装备、状态或环境信息而退回 `needs_human`，难以真实验证 prompt、规则检索和规划闭环。

同时，planner 现在虽然已经支持 HITL `resume`，但 `smoke/test_planner.py` 在被中断后只打印 `resume.thread_id` 并结束进程，开发者还要手动再次构造 `--thread-id` / `--resume-json` 重新运行，交互链路割裂，和“在烟雾测试里观察真实人工审批流程”的目标不一致。

## 变更内容

- 参考其他分支中更丰富的 `world_state.txt` 样式，为本分支提供一份位于 `config/` 下的默认 `world_state.toml`，并使用点分路径平铺 key 承载更完整的世界状态。
- 扩展统一配置，让 `config/config.toml` 显式声明 planner smoke 默认 world state 文件，而不是继续把 demo state 硬编码在 `smoke/test_planner.py` 中。
- 让 `smoke/test_planner.py` 默认从该 world state 文件加载状态，并转换为当前 planner / fetch_keys 可消费的嵌套 state 结构。
- 让 `smoke/test_planner.py` 在命中 HITL 时进入交互式等待，接收用户输入并在同一进程内继续 `resume`，而不是直接结束程序。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `project-config`: 统一配置需要覆盖 planner smoke 默认 world state 文件来源，避免脚本默认状态继续隐藏在代码中。
- `agent-planner`: planner smoke 脚本需要使用更真实的默认 world state，并在 HITL 中断后支持同进程交互式 resume。

## 影响

- `config/config.toml` 与新增的 `config/world_state.toml`
- `trpg_py.config` 的类型化配置模型与路径解析
- `smoke/test_planner.py` 的 state 加载方式与 HITL 交互流程
- `tests/test_project_config.py`、`tests/test_smoke_scripts.py` 以及相关 README/使用说明
