## 1. 默认 world state

- [x] 1.1 参考其他分支中更丰富的 `world_state.txt` 内容，在 `config/` 下新增默认 `world_state.toml`，并采用点分路径平铺 key
- [x] 1.2 扩展 `trpg_py.config` 与 `config/config.toml`，声明 planner smoke 默认 world state 文件路径
- [x] 1.3 让 `smoke/test_planner.py` 加载该 world state 文件并转换为当前 planner 可消费的嵌套 state

## 2. HITL 交互

- [x] 2.1 调整 `smoke/test_planner.py`，在非 JSON 模式命中 `resume.thread_id` 时进入交互式等待，而不是直接结束
- [x] 2.2 为交互式 resume 设计最小可用输入流程，并在同一 `thread_id` 上继续调用 planner

## 3. 验证与文档

- [x] 3.1 为配置加载与 smoke 脚本增加测试，覆盖 world state 路径解析、平铺 key 展开和 HITL 交互路径
- [x] 3.2 更新 README 或相关说明，说明默认 world state 来源以及 smoke 脚本如何在 HITL 中继续等待用户输入
