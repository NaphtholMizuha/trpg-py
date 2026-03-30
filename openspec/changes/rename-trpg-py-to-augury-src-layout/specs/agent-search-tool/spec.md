## 新增需求

## 修改需求

### 需求:agent search 工具必须驻留在 agent.tools 命名空间
系统必须在 `augury.agent.tools` 命名空间下提供规则搜索工具能力，并且该能力必须可以被 Python 调用方直接导入和使用，而不是只作为某个 agent 框架内部的匿名回调存在。

#### 场景:调用方从 agent.tools 使用搜索能力
- **当** 开发者为 planner agent 组装工具集
- **那么** 可以从 `augury.agent.tools` 访问搜索工具实现
- **那么** 不需要直接依赖 Qdrant 客户端细节来完成一次规则检索

### 需求:search 工具必须提供可手动运行的集成测试脚本
系统必须提供一个位于 `src/smoke/test_search.py` 的可手动运行脚本，用于让开发者直接验证 search 工具的真实检索效果，而不是只依赖自动化测试或底层客户端调用。该脚本的人类可读输出必须优先展示当前知识库的来源字段和章节路径，便于开发者核对命中是否与 `rag.md` 中定义的 schema 一致。

#### 场景:开发者手动验证 search 效果
- **当** 开发者在本地执行 `src/smoke/test_search.py` 并提供 query 或其他参数
- **那么** 脚本调用系统现有 search 能力完成一次检索
- **那么** 输出中可以观察命中、无命中或错误等结构化结果

#### 场景:smoke 输出展示当前知识库来源字段
- **当** `src/smoke/test_search.py` 以人类可读模式打印命中结果
- **那么** 输出必须能够展示 `title`、`doc_type`、`book`、`path`
- **那么** 输出必须在存在时展示 `section_titles`
- **那么** 输出不得继续只依赖 `file`、`locator`、`type` 等旧字段作为主要来源摘要

## 移除需求
