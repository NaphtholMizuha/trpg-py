# smoke-test-layout 规范

## 目的
待定 - 由归档变更 reorganize-integration-test-scripts 创建。归档后请更新目的。
## 需求
### 需求: 系统必须将手动集成测试脚本集中放入 smoke 目录
系统必须将仓库中供开发者手动运行的集成测试脚本集中放入根目录下的 `smoke/` 目录，禁止继续将这类脚本长期散落在仓库根目录。

#### 场景:新增手动集成脚本
- **当** 开发者需要新增一个可手动运行的 engine、tool 或 planner 验证脚本
- **那么** 该脚本必须创建在 `smoke/` 目录下
- **那么** 该脚本不得作为根目录长期入口存在

### 需求: 系统必须将根目录 test 前缀脚本迁移出根目录
系统必须将仓库根目录下以 `test` 开头的手动集成脚本迁移到 `smoke/` 目录，禁止在完成迁移后继续同时维护根目录与集成测试目录两套长期入口。

#### 场景:收敛现有根目录手动脚本
- **当** 仓库根目录存在以 `test` 开头的手动运行脚本
- **那么** 这些脚本迁移到 `smoke/` 目录
- **那么** 系统不得继续保留等价的根目录长期脚本入口

### 需求: smoke 目录必须与自动测试发现目录职责分离
系统必须将 `smoke/` 视为“手动执行的集成验证入口”目录，而不是默认自动测试发现目录，禁止将其与 `tests/` 的职责混淆。

#### 场景:开发者区分手动脚本与自动测试
- **当** 开发者查看 `smoke/` 与 `tests/` 两个目录
- **那么** 可以明确区分前者用于手动运行验证，后者用于自动测试套件
- **那么** 手动脚本目录不会隐式替代自动测试目录语义

### 需求:smoke 目录必须为 task_node 提供独立的手动验证入口
系统必须在 `src/smoke/` 目录下为 `task_node` 提供独立的手动验证脚本入口，禁止要求开发者通过修改其他 smoke 脚本或临时创建一次性文件来观察 `TaskDraft` 生成结果。

#### 场景:新增 task_node 手动验证入口
- **当** 开发者需要手动验证 `task_node` 把指令翻译为 `TaskDraft` 的结果
- **那么** 可以直接在 `src/smoke/` 下找到独立脚本入口
- **那么** 该入口必须与其他 smoke 脚本保持一致的目录语义

### 需求:smoke 目录必须为 dsl_node 提供独立的手动验证入口
系统必须在 `src/smoke/` 目录下为 `dsl_node` 提供独立的手动验证脚本入口，禁止要求开发者只能通过自动测试、临时 Python 片段或完整 planner workflow 才能观察 `TaskDraft -> TaskDocument` 的翻译结果。

#### 场景:开发者单独验证 dsl_node 输出
- **当** 开发者需要检查一份现成 `TaskDraft` 会被 `dsl_node` 翻译成什么 `TaskDocument`
- **那么** 可以直接在 `src/smoke/` 下找到独立的 `dsl_node` smoke 入口
- **那么** 该入口必须与其他 smoke 脚本保持一致的目录语义
- **那么** 该入口展示的最终 `TaskDocument` 必须来自 `dsl_node` 的结构化输出结果

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

#### 场景:开发者观察 dsl 到 engine 的执行结果
- **当** `src/smoke/test_dsl.py` 获得了结构化输出成功且 lint 通过的 `TaskDocument`
- **那么** 脚本输出必须继续展示执行阶段结果
- **那么** 脚本输出必须继续展示关键 state 变化摘要，而不只是停在 DSL 与 lint

#### 场景:开发者观察 dsl_node repair 回路
- **当** `dsl_node` smoke 入口在首轮生成后进入 lint-repair 回路
- **那么** 脚本输出必须能让开发者观察是否触发了 repair
- **那么** 脚本输出必须能让开发者观察最终轮次和最终 lint 结论
