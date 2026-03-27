## 1. Planner 收口语义

- [x] 1.1 更新 planner prompt，明确 `list/read` 的 `status=no_match` 表示当前 state 中没有该事实，并限制 suggestions 后的重复试探次数
- [x] 1.2 更新 planner prompt，要求对同类候选值优先使用批量 `read`，避免机械拆成多次单路径读取
- [x] 1.3 调整 planner 对 `lint` 的使用策略与文案，确保其只作为候选 `TaskDocument` 的最终校验而不是新的探索循环入口

## 2. Runtime 护栏

- [x] 2.1 在 planner runtime 中实现单轮工具调用次数硬上限，并让预算值来自现有配置入口
- [x] 2.2 在 planner runtime 中跟踪重复失败主题（相同 bare path、prefix 或等价缺失事实），并在重复 `no_match` 后强制收口
- [x] 2.3 为预算耗尽或重复失败收口补充结构化错误/调试信息，使调用方能区分缺失事实、工具故障与护栏触发

## 3. Tool 与 Smoke 接线

- [x] 3.1 调整 `list/read` 相关 planner 集成逻辑和测试夹具，覆盖“建议修正一次后仍无命中即视为没有”的行为
- [x] 3.2 更新 planner smoke 与 planner+engine smoke 的输出和断言，覆盖批量 `read`、缺失法术位/法术快速收口与预算耗尽原因
- [x] 3.3 运行相关单元测试与 smoke 入口，验证 planner 不再围绕同一缺口长时间重复工具调用
