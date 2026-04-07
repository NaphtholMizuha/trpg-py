## 1. 评测数据与案例清单

- [x] 1.1 新增端到端评测 fixture bundle，包含专用 world state 文件和默认案例 manifest
- [x] 1.2 在 manifest 中定义 10 条默认用户输入及其结构化 expectation 字段
- [x] 1.3 为 10 条案例补齐覆盖标签与说明，覆盖攻击、治疗、范围法术、缺信息和状态投影

## 2. 批量端到端评测入口

- [x] 2.1 新增批量评测脚本，逐条运行 instruction -> planner workflow -> engine execution
- [x] 2.2 让评测脚本为每条案例从同一初始 fixture 深拷贝独立 state，避免跨案例污染
- [x] 2.3 让评测脚本在 `ready` 时执行 engine，在 `needs_human` 时跳过 execution 并保留缺口信息
- [x] 2.4 为评测脚本补齐 CLI 参数，支持覆盖案例文件、状态文件、日志目录和 JSON 输出

## 3. 日志与自动评估

- [x] 3.1 定义单案例日志结构，记录 workflow 状态、TaskDraft、TaskDocument、lint、execution 和 state_changes
- [x] 3.2 实现基于 manifest expectation 的 evaluator，输出 per-case pass/fail 和 failure reasons
- [x] 3.3 实现整套案例的 summary 聚合，统计总案例数、通过数、失败数和每条案例摘要
- [x] 3.4 将单案例日志和 summary 写入稳定目录，便于后续 diff 与回归审查

## 4. 测试与验证

- [x] 4.1 为案例 manifest 解析、日志结构和 evaluator 汇总逻辑新增自动测试
- [x] 4.2 为批量评测入口新增脚本级测试，验证默认 10 案例、JSON 输出和失败分支
- [x] 4.3 运行一次默认端到端评测 smoke，确认 10 条案例都能产生日志与汇总
- [x] 4.4 审阅默认评测结果，确认显式成功案例、预期 `needs_human` 案例和状态变化摘要都符合设计
