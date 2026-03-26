## 上下文

当前 planner 只有两段 prompt 文本，但它们承担了核心规划约束、工具使用提示和结构化输出语义。由于这些内容写死在 `trpg_py/agent/planner.py` 的 `_build_system_prompt()` 与 `_build_user_prompt()` 中，任何文案微调都必须修改代码、运行测试并重新阅读实现细节，调试成本明显高于纯配置型文本。

项目此前已经建立了统一配置入口，并明确要求新的项目级默认行为先进入 `trpg_py.config` 与 `config/config.toml`。因此这次不适合新增一个游离于统一配置之外的 `prompts/` 约定，而应把 prompt 资源的位置和默认选择也纳入统一配置治理。

## 目标 / 非目标

**目标：**
- 把 planner 的 system/user prompt 提取为 `config/` 下的文本模板，便于直接调试和版本管理。
- 让 `config/config.toml` 成为 prompt 目录和默认模板文件的唯一项目级真相。
- 让 planner 继续支持动态上下文注入，例如 instruction、context JSON、policy JSON、tool budget 和 repair feedback。
- 对 prompt 文件缺失、路径错误和模板占位符问题提供快速失败与可读错误。

**非目标：**
- 不在本次设计中引入完整模板引擎、条件分支语法或多环境 prompt 继承系统。
- 不在本次设计中改变 planner 的三态协议、工具链路或校验闭环。
- 不在本次设计中把 search/fetch_keys 的提示词体系一并重构。
- 不在本次设计中新增第二份 TOML 或额外的配置加载入口。

## 决策

### 决策: 在 `config/` 下新增 planner prompt 目录，并由 `config.toml` 显式声明它

prompt 模板文件将放在仓库 `config/` 目录下的专用子目录，例如 `config/prompts/`。但代码不会直接假定这个目录名，而是通过 `config/config.toml` 中的 planner prompt 配置读取：

- prompt 目录路径
- system prompt 文件名或相对路径
- user prompt 文件名或相对路径

这样即使未来需要切换到另一组 prompt 文件，也只需要修改统一配置，而不必继续在 `planner.py` 中硬编码目录约定。

考虑过的替代方案：
- 只约定 `config/prompts/` 固定目录，不进 TOML：实现最省事，但仍然让 prompt 目录成为代码隐式真相。
- 把 prompt 文本直接写进 TOML 多行字符串：单文件集中，但阅读和调试体验不如独立文本文件，且不利于长文本维护。

### 决策: 使用轻量级占位符模板，而不是引入完整模板引擎

system/user prompt 文件仍然是纯文本，但允许使用有限占位符，例如：

- `{{tool_budget}}`
- `{{instruction}}`
- `{{context_json}}`
- `{{policy_json}}`
- `{{validation_feedback}}`

planner 在运行时只负责把这些命名占位符替换为字符串，不引入 Jinja2 之类的新依赖。这样足以支持当前动态内容，同时降低模板行为不透明和转义规则复杂化的风险。

考虑过的替代方案：
- 继续在代码里拼接动态段落，只把静态前缀外置：能减少模板复杂度，但 user prompt 仍有大量文案残留在代码里。
- 引入完整模板引擎：扩展性强，但超出当前需求，也会增加依赖和调试面。

### 决策: prompt 路径按统一配置文件相对路径解析

prompt 目录和模板文件如果是相对路径，统一相对于 `config/config.toml` 所在目录解析，而不是相对于当前工作目录。这与现有 `resolve_path_from_config(...)` 行为一致，也能避免 smoke、测试和 IDE 启动目录不同导致路径漂移。

考虑过的替代方案：
- 相对于仓库根目录解析：本仓库可行，但会让配置语义依赖仓库布局，不如“相对于配置文件”稳定。
- 强制绝对路径：最明确，但不利于仓库内共享和提交示例配置。

### 决策: 对 prompt 模板装载与渲染失败快速失败

planner factory 在装载 prompt 模板时必须对以下问题快速失败：

- prompt 目录不存在
- system/user prompt 文件不存在或不可读
- 模板渲染后仍残留未识别占位符
- 模板声明了系统不支持的占位符名称

这样可以把错误尽早暴露为配置或模板问题，而不是把异常延迟到一次模糊的 LLM 调用失败之后。

考虑过的替代方案：
- 缺失文件时回退到代码内置 prompt：兼容性强，但会让“外置配置”失去可信真相。
- 忽略未知占位符并原样传给模型：实现简单，但问题更难排查。

## 风险 / 权衡

- [外置 prompt 后模板占位符容易写错] → 通过集中渲染函数和未解析占位符校验快速失败。
- [配置新增 prompt 路径字段后模型变复杂] → 将新增字段限定在 planner 子配置内，避免扩散到无关模块。
- [文本模板与代码字段名脱节] → 用固定占位符集合和测试样例约束模板契约。
- [未来 prompt 版本变多，单一配置难以表达切换策略] → 本次先只支持“目录 + 默认文件”模型，后续再按实际需要扩展。

## Migration Plan

1. 在统一配置模型中新增 planner prompt 目录与模板文件字段，并更新 `config/config.toml` 示例。
2. 在 `config/` 下新增默认 system/user prompt 文本模板。
3. 把 `planner.py` 中的内嵌 prompt 构建逻辑替换为“加载模板 + 渲染占位符”流程。
4. 为配置加载、路径解析、模板渲染和 planner 调用补充测试。
5. 更新 README 或相关调试文档，说明如何直接编辑 prompt 文本并通过 `config.toml` 切换目录。

## Open Questions

- prompt 配置字段是采用 `directory + system_file + user_file`，还是直接分别声明两个完整路径，更符合现有配置风格？
- `validation_feedback` 在首轮为空时，模板是渲染为空字符串，还是完全省略该段内容，更利于模型稳定性？
