## 1. 目录与装配

- [x] 1.1 在 `src/` 下新增与 `augury/`、`tests/` 平级的 `eval/` 目录，并补最小模块说明或初始化文件
- [x] 1.2 复用现有 state loader 与默认 fixture 路径，整理 Context Agent eval 脚本的默认输入来源
- [x] 1.3 明确并固化主 agent 委派给 Context Agent 的默认 payload 结构，避免脚本维护旁路输入协议

## 2. Context Agent Eval 脚本

- [x] 2.1 新增一个可手动运行的 Context Agent eval 脚本，直接调用 Context Agent 而不是完整 planner workflow
- [x] 2.2 为脚本添加 instruction、state 文件和输出格式等参数，支持默认运行与显式覆盖
- [x] 2.3 在脚本默认输出中展示 `status`、`instruction`、`normalized_instruction`、`action`、`resolved_entities`、`rule_evidence`、`state_evidence`、`citations`、`unresolved_gaps` 和 `notes`
- [x] 2.4 为脚本补完整 bundle 输出模式，确保开发者可以查看或复制完整结构化结果

## 3. 自动测试与验证

- [x] 3.1 为 Context Agent eval 脚本补自动测试，覆盖默认 payload 构造与关键输出字段
- [x] 3.2 验证脚本在默认 fixture state 下可以稳定产出真实 `ContextBundle`
- [x] 3.3 验证脚本的覆盖参数可以替换 instruction 或 state 文件且不破坏输入契约

## 4. 文档与收口

- [x] 4.1 更新 README 或相关开发者文档，说明 `src/eval/` 的职责和 Context Agent eval 脚本的使用方式
- [x] 4.2 运行相关自动测试与手动脚本自检，确认项目对 Context Agent 的观察入口不再依赖临时脚本或旧 smoke 路径
