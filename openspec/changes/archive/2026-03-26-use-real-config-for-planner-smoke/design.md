## 上下文

`smoke/test_planner.py` 目前虽然位于 `smoke/` 目录下，但默认行为仍是构造 fake agent、fake LLM、fake tool 和预制三态响应。这样的脚本更接近离线示例，而不是 smoke test，因为它无法帮助开发者确认 `config/config.toml` 中的 planner 模型、接入点、API key、超时、重试和工具配置是否真的接通，也无法验证 planner 到 `search` / `fetch_keys` 的真实调用链。

planner 的真实接入入口已经统一收敛在 `trpg_py.agent.create_planner(...)` 和 `trpg_py.config` 中，因此 smoke 脚本最有价值的职责，是用最小示例 state 和 DM 指令触发一次真实 planner 规划，并把真实返回的 `ready / needs_human / blocked` 结果打印出来。

## 目标 / 非目标

**目标：**
- 让 `smoke/test_planner.py` 默认通过 `config/config.toml` 构造真实 planner。
- 让 smoke 脚本验证真实 planner factory、真实模型配置，以及真实 `search` / `fetch_keys` 工具接入链路。
- 保留人类可读摘要和 `--json` 输出，方便观察真实规划结果。
- 让失败模式可见，便于开发者区分“配置问题”“依赖不可用”“规划返回 needs_human”。

**非目标：**
- 不要求 CI 必须跑通真实在线 planner 调用。
- 不要求 smoke 脚本伪造 `ready / needs_human / blocked` 三态以覆盖所有演示分支。
- 不修改 planner 核心输出契约或 factory 配置优先级。

## 决策

### 决策 1：`smoke/test_planner.py` 默认只走真实配置路径
- 选择：脚本默认读取 `config/config.toml` 并调用 `create_planner(config_path=..., state=...)`。
- 原因：这是唯一能验证项目真实 planner 配置是否可用的路径，也符合 smoke test 的定义。
- 备选方案：保留 fake 为默认、把真实调用放到 `--live`。
- 不选原因：这会继续把“离线演示”伪装成“smoke test”，无法满足验证真实配置的目标。

### 决策 2：脚本必须使用真实 `search` 与真实 `fetch_keys`
- 选择：脚本通过 `create_planner(...)` 走默认工具构造路径，让 planner 自己接入真实 `search` 和真实 `fetch_keys`。
- 原因：用户要验证的是“真正使用时会走的整条链路”，如果脚本仍注入 fake tool，就无法发现真实检索或状态路径发现的接线问题。
- 备选方案：只让模型真实，工具继续注入 dummy/fake 实现。
- 不选原因：这只能验证半条链路，仍不符合 smoke test 目的。

### 决策 3：脚本输出只展示真实调用返回，不在脚本内伪造结构化结果
- 选择：摘要和 JSON 输出都来自真实 `PlannerResult`。
- 原因：开发者需要看到真实 planner 的结果，而不是脚本预设的 happy path。
- 备选方案：保留 fake 场景分支作为三态演示。
- 不选原因：会弱化 smoke 脚本的验证价值，并让“脚本能跑”与“配置能跑”混淆。

### 决策 4：自动测试改为验证真实配置与真实工具接线，而不是验证 fake 场景表演
- 选择：自动测试通过 patch `create_planner` 的边界来验证脚本确实读取配置并走默认工具构造路径，但不在测试里发起真实外网请求。
- 原因：这样既能保持自动测试稳定，又能保证脚本设计指向真实 planner + 真实工具链路。
- 备选方案：自动测试直接依赖 fake agent 场景。
- 不选原因：测试会继续保护错误的脚本设计方向。

## 风险 / 权衡

- [真实 smoke 依赖外部模型、检索服务和状态工具可用] → 文档明确这是手动 smoke 路径；脚本应把错误清晰打印为 `blocked` 或异常信息，帮助开发者定位配置或依赖问题。
- [自动测试不能直接访问真实远端] → 自动测试只验证脚本是否走真实 planner 构造路径，不验证外部服务可用性。
- [真实 planner 返回状态不可预测] → 文档不再承诺脚本内置三态演示，而是承诺展示真实返回状态；开发者可通过不同输入观察结果。

## Migration Plan

1. 移除 `smoke/test_planner.py` 中 fake agent、fake LLM、fake tool 和预制响应逻辑。
2. 将脚本入口改为默认读取 `config/config.toml` 并构造真实 planner，同时使用默认真实工具接线。
3. 更新 README 和 smoke 使用说明，去掉将 fake 结果当作默认 smoke 演示的描述。
4. 调整自动测试，使其验证真实配置与真实工具接线路径及输出行为。

## Open Questions

- 是否需要给 `smoke/test_planner.py` 增加一个显式的 `--state-file` 参数，用于替换内置示例 state，以便测试更多真实场景。
