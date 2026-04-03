## 新增需求

### 需求:smoke 目录必须为 dsl_node 提供独立的手动验证入口
系统必须在 `src/smoke/` 目录下为 `dsl_node` 提供独立的手动验证脚本入口，禁止要求开发者只能通过自动测试、临时 Python 片段或完整 planner workflow 才能观察 `TaskDraft -> TaskDocument` 的翻译结果。

#### 场景:开发者单独验证 dsl_node 输出
- **当** 开发者需要检查一份现成 `TaskDraft` 会被 `dsl_node` 翻译成什么 `TaskDocument`
- **那么** 可以直接在 `src/smoke/` 下找到独立的 `dsl_node` smoke 入口
- **那么** 该入口必须与其他 smoke 脚本保持一致的目录语义

### 需求:dsl_node smoke 脚本必须默认读取 test_task_draft 样例
系统必须让 `dsl_node` smoke 脚本默认读取仓库内的 `output/test_task_draft.json` 作为输入样例，禁止要求开发者每次运行时都必须手工构造内联 `TaskDraft` 或提供必填参数。

#### 场景:开发者直接运行 dsl_node smoke 脚本
- **当** 开发者在未提供输入文件参数的情况下执行 `src/smoke/test_dsl.py`
- **那么** 脚本必须读取 `output/test_task_draft.json`
- **那么** 脚本必须将该文件解析为结构化 `TaskDraft`

### 需求:dsl_node smoke 脚本必须展示 DSL 与 lint 结果
系统必须让 `dsl_node` smoke 脚本输出生成的 `TaskDocument` 与对应 `lint_result`，禁止只展示输入摘要、prompt 文本或单独的成功失败标记。

#### 场景:人类可读模式检查 dsl 输出
- **当** `src/smoke/test_dsl.py` 以默认人类可读模式运行成功
- **那么** 输出中必须可以看到生成的 `task_document`
- **那么** 输出中必须可以看到 `lint_result` 的状态

#### 场景:JSON 模式用于最小自动验证
- **当** 调用方使用 `--json` 运行 `src/smoke/test_dsl.py`
- **那么** 脚本必须输出可解析 JSON
- **那么** JSON 中必须同时包含 `draft`、`task_document` 和 `lint_result`

## 修改需求

## 移除需求
