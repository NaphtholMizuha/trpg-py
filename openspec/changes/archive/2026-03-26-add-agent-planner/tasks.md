## 1. Planner 接口与模型

- [x] 1.1 在 `trpg_py.agent` 下新增 planner 模块，定义结构化输入参数（DM 指令、上下文、工具配置）
- [x] 1.2 定义 planner 三态输出模型（`ready/needs_human/blocked`）及对应字段约束
- [x] 1.3 约定 `needs_human` 的问题载荷结构（问题文本、缺口说明、候选假设）
- [x] 1.4 引入并配置 Deep Agents（`deepagents`）运行入口，建立 planner factory
- [x] 1.5 在 factory 中实现统一配置项：`model/base_url/api_key/timeout/max_retries/interrupt_on`
- [x] 1.6 在 factory 中实现统一解析优先级（调用参数 > 环境变量 > 默认值）并补充输入校验

## 2. 证据收集与推理流程

- [x] 2.1 实现 planner 的“先取证再提问”循环，接入 `search` 与 `fetch_keys`
- [x] 2.2 实现工具结果分支处理，显式区分 `ok/no_match/error`
- [x] 2.3 实现 LLM 主导不确定性判定逻辑，并暴露 `missing_info` 与 `assumptions`
- [x] 2.4 为工具调用增加回合上限与超时控制，超限时进入 `needs_human` 或 `blocked`
- [x] 2.5 基于 Deep Agents 配置 HITL 中断/恢复点，确保澄清分支可回到规划流程

## 3. TaskDocument 生成与校验闭环

- [x] 3.1 为 planner 产物建立 JSON Schema 结构校验
- [x] 3.2 接入 `validate_task_document` 进行执行器语义校验
- [x] 3.3 实现校验失败后的自动修复重试流程
- [x] 3.4 在修复无法收敛时回退到 `needs_human`，并返回可解释失败原因

## 4. 集成与边界

- [x] 4.1 确保 planner 仅返回规划结果，不直接执行 engine 或提交状态写入
- [x] 4.2 在 `trpg_py.agent` 暴露 planner 公共入口并保持与现有 tools API 风格一致
- [x] 4.3 补充与 `fetch_keys`、`search` 的集成测试替身，避免外部依赖耦合测试

## 5. 验证与文档

- [x] 5.1 增加 planner 行为测试：`ready` 成功产出、`needs_human` 触发、`blocked` 故障分支
- [x] 5.2 增加校验闭环测试：Schema 失败、语义失败、修复成功与修复失败
- [x] 5.3 增加 Deep Agents 集成测试，覆盖工具编排与 HITL 中断恢复
- [x] 5.4 增加 planner factory 测试，覆盖配置优先级、参数透传与错误分支
- [x] 5.5 编写 planner 使用说明，包含三态语义、Deep Agents 约束、factory 配置方式、HITL 触发原则和已知限制
