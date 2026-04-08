## 1. Eval 交互编排

- [x] 1.1 盘点当前 Context Agent eval 脚本与 CLI ask adapter 的接线点，明确哪里仍停留在“只展示 ask_requests”
- [x] 1.2 修改 eval helper，使其在交互式 CLI 场景下真正调用统一 ask adapter 采集 `AskResponse`
- [x] 1.3 保持非交互模式可预测：继续输出 `ask_requests`，但显式跳过回答采集而不阻塞

## 2. 输出与结果模型

- [x] 2.1 更新 Context Agent eval 的人类可读输出，使其同时展示 ask 请求和 ask 回答
- [x] 2.2 更新完整输出 / JSON 输出，确保已采集的 `AskResponse` 能以结构化形式留档
- [x] 2.3 明确文案或结果字段，避免用户误解为 eval 已自动继续执行 planner 或 resolution

## 3. 测试与验证

- [x] 3.1 为默认选项确认路径添加自动测试，确保 CLI ask 会生成正确 `AskResponse`
- [x] 3.2 为自定义输入路径添加自动测试，确保 ask 回答能被完整记录和展示
- [x] 3.3 为非交互模式添加自动测试，确保脚本不会阻塞且仍保留 `ask_requests`
- [x] 3.4 运行相关测试和一次手动 eval 自检，确认 ask 交互闭环在 Python CLI 中可用
