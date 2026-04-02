## 新增需求

### 需求:系统必须提供专门验证 task_node 生成 TaskDraft 的 smoke 脚本
系统必须在 `src/smoke/test_task.py` 中提供一个专门验证 `task_node` 将 DM 指令翻译为 `TaskDraft` 的手动 smoke 脚本，禁止要求开发者只能通过自动测试或临时脚本观察第一阶段任务稿。

#### 场景:开发者手动运行 task smoke
- **当** 开发者运行 `python src/smoke/test_task.py`
- **那么** 脚本必须调用真实 `TaskNode`
- **那么** 脚本必须输出可供人工检查的 `TaskDraft` 关键内容

### 需求:task smoke 脚本必须支持可配置指令与状态文件
系统必须允许 `src/smoke/test_task.py` 接受自定义 instruction，并且必须允许调用方显式指定状态文件路径，禁止把脚本固定死为单一硬编码示例且不可覆盖。

#### 场景:开发者传入自定义 instruction 和状态文件
- **当** 开发者使用命令行参数传入 instruction 或 state file
- **那么** 脚本必须使用传入值构造 `TaskNode` 的运行输入
- **那么** 脚本不得继续忽略这些覆盖参数

### 需求:task smoke 脚本必须暴露稳定的 TaskDraft 输出契约
系统必须让 `src/smoke/test_task.py` 的输出围绕 `TaskDraft` 关键字段组织，至少包含 `task`、`reads`、`judgments`、`writes`、`missing_info` 和 `assumptions`，禁止只输出无法稳定比较的一段自由文本摘要。

#### 场景:开发者查看默认文本输出
- **当** 开发者以人类可读模式运行 smoke 脚本
- **那么** 脚本必须展示 `TaskDraft` 的关键字段
- **那么** 开发者可以据此判断第一阶段任务稿是否合理

#### 场景:开发者请求 JSON 输出
- **当** 开发者使用 `--json` 运行 smoke 脚本
- **那么** 脚本必须输出可解析的 JSON
- **那么** JSON 内容必须能反映完整的 `TaskDraft` 结构化结果

## 修改需求

## 移除需求
