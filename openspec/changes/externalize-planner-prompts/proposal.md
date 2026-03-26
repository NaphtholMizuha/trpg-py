## 为什么

当前 planner 的 system/user prompt 直接内嵌在 `trpg_py/agent/planner.py` 中，调试和迭代都需要改 Python 代码，既不利于快速试验文案，也让 prompt 变更和业务逻辑耦合过紧。

同时，如果只是把 prompt 文件单独拆出去但不纳入 `config/config.toml`，新的 prompt 目录位置和文件选择仍会变成隐式约定，继续形成分散的长期默认真相。

## 变更内容

- 将 planner 的 system prompt 和 user prompt 从 `planner.py` 中提取为 `config/` 目录下可直接编辑的 `.txt` 模板文件。
- 扩展统一项目配置，让 `config/config.toml` 显式声明 planner prompt 目录以及默认模板文件，而不是在代码中硬编码 prompt 路径。
- 让 planner 在运行时通过统一配置加载 prompt 模板，并对缺失文件、非法路径或未解析占位符快速失败。
- 为 prompt 外置与配置接入补充测试和文档，确保后续调 prompt 不必再改 planner 代码。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `project-config`: 统一配置需要覆盖 planner prompt 目录与模板文件定位，避免 prompt 资源脱离 `config.toml` 管理。
- `agent-planner`: planner 需要从外置文本模板加载 system/user prompt，而不是继续使用内嵌字符串。

## 影响

- `trpg_py/agent/planner.py` 的 prompt 构建与模板渲染逻辑
- `trpg_py/config.py` 的类型化配置模型、路径解析与配置校验
- `config/config.toml` 与新增的 prompt 文本模板文件
- `tests/test_agent_planner.py`、`tests/test_project_config.py`、可能涉及的 smoke/README 文档
