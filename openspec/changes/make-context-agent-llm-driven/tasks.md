## 1. 运行时接线

- [x] 1.1 为 Context Agent 增加可注入的模型调用依赖，并复用现有 planner 模型配置完成默认装配。
- [x] 1.2 增加 Context Agent prompt 的读取与渲染路径，让 `planner_context_agent_system/user` 真正进入运行时。
- [x] 1.3 以 `langchain.create_agent` 重构 Context Agent 的核心执行体，并保留现有 `ContextBundle` 输出契约。

## 2. 控制流与安全校验

- [x] 2.1 用 `create_agent` 的结构化输出和工具边界替换当前默认的 `_analyze_intent`/硬编码 ask 控制流，并限制 agent 只能请求 `grep`、`search`、`ask` 或结束动作。
- [x] 2.2 为模型非法输出、工具失败、超出轮次或模型调用异常补充结构化错误/阻塞处理。
- [x] 2.3 评估并收紧旧启发式 helper 的职责，只保留必要的预处理或 fallback 能力。

## 3. 评测与回归测试

- [x] 3.1 为 Context Agent 增加 fake agent 或 fake model 测试夹具，覆盖“先取证后完成”“直接 ask”“blocked/error”三类主路径。
- [x] 3.2 更新 focused eval 与相关辅助代码，展示 prompt 输入、模型轮次动作摘要以及最终 bundle/interrupt 结果。
- [x] 3.3 更新现有 Context Agent、runtime 和配置测试，使其验证 prompt 装载与 LLM 驱动链路，而不是旧启发式默认行为。
