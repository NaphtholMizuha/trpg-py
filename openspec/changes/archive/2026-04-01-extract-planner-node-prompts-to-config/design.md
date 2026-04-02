## 上下文

当前 planner node 的提示词仍然直接写在 `src/augury/planner/nodes/task_node.py` 和 `src/augury/planner/nodes/dsl_node.py` 里。这样虽然实现简单，但 prompt 迭代需要改 Python 代码，不利于单独审阅、版本比较和后续实验。除此之外，node 的 user message 模板现在也内嵌在代码中，使“system 指令”和“user 模板”无法独立维护。

仓库已经存在 `config/prompts/` 目录，并且旧 planner 体系已经有外置 prompt 文件，因此这次设计更像是把新的 node prompt 也拉回到统一的配置组织方式，而不是再引入一套新的 prompt 存储机制。

## 目标 / 非目标

**目标：**
- 将 `task_node` 和 `dsl_node` 的默认 system prompt 与 user prompt 模板都提取到 `config/prompts/` 下的独立文件。
- 在 `config/config.toml` 里为两个 node 分别增加 prompt 文件名配置。
- 为 planner node 提供统一的 prompt 加载逻辑，使默认路径来自配置文件而不是代码常量。
- 保留测试或实验时显式传入 prompt 字符串的能力。
- 让 prompt 文件命名清晰，能直接体现 node 归属。

**非目标：**
- 本次设计不改写 prompt 的业务语义。
- 本次设计不重构整个项目的配置模型，只在必要范围内扩展 prompt 加载方式。
- 本次设计不要求把 workflow 级或旧 planner 级 prompt 一并迁走，只聚焦两个新 node。

## 决策

### 决策 1：两个 node 的 system 与 user prompt 都放在 `config/prompts/`

新的默认 prompt 文件直接放在现有 `config/prompts/` 目录下，例如：
- `config/prompts/planner_task_node_system.txt`
- `config/prompts/planner_task_node_user.txt`
- `config/prompts/planner_dsl_node_system.txt`
- `config/prompts/planner_dsl_node_user.txt`

这样做的原因是：
- 复用仓库已存在的 prompt 目录约定
- 避免把 planner node prompt 散落到新目录
- 文件名能直观看出属于哪个 node 与 prompt 类型

替代方案：
- 放在 `src/augury/planner/prompts/`：更贴近代码，但会形成第二套 prompt 目录约定
- 合并成单个 planner prompt 文件：不利于节点独立迭代

### 决策 2：在 `config/config.toml` 中为两个 node 分别配置 prompt 文件名

`config/config.toml` 应当在现有 `[planner.prompt]` 之外，为两个 node 提供独立 prompt 配置节，例如：

```toml
[planner.task_node_prompt]
system_file = "planner_task_node_system.txt"
user_file = "planner_task_node_user.txt"

[planner.dsl_node_prompt]
system_file = "planner_dsl_node_system.txt"
user_file = "planner_dsl_node_user.txt"
```

这样做的原因是：
- 让文件名成为显式配置，而不是靠代码约定猜测
- 后续如果 prompt 文件改名，不需要同步修改节点代码
- system/user 两类 prompt 都能被对称管理

替代方案：
- 只使用约定式文件名，不写入配置：实现更快，但扩展性和可见性更差

### 决策 3：节点加载 prompt 的优先级是“显式传入 > 配置文件默认值”

`task_node` 和 `dsl_node` 都应遵循同一优先级：
1. 调用方显式传入的 prompt 文本
2. 配置文件中声明的默认 prompt 文件内容

这样做的原因是：
- 测试仍然可以局部覆写 prompt
- 默认运行路径不再依赖代码内联常量
- 节点的调用方式保持灵活

替代方案：
- 完全禁止代码侧覆写：过于僵硬，不利于测试和实验
- 始终优先代码常量：会让外置 prompt 失去意义

### 决策 4：prompt 加载逻辑应当复用现有配置解析能力

prompt 文件的定位应当优先建立在现有 `config/config.toml` 与路径解析工具之上，而不是在 node 模块里手写绝对路径。

这样做的原因是：
- 避免节点直接耦合仓库目录结构
- 让 prompt 加载和现有配置系统保持一致
- 后续如果 prompt 目录调整，只需改配置和加载辅助函数
- user prompt 模板和 system prompt 使用同一套路径解析机制

替代方案：
- 在 node 模块里写死 `Path("config/prompts/...")`：实现快，但可维护性差

## 风险 / 权衡

- [prompt 文件外置后，运行时更依赖文件系统状态] → 通过保留显式传入 prompt 的覆写能力和清晰错误信息来缓解。
- [配置项增多可能让 node 初始化更复杂] → 通过把路径解析集中到小型辅助函数中，避免在 node 内部分散处理。
- [system prompt 与 user prompt 同时外置后，模板耦合更显式] → 通过文件命名和配置分节让配对关系清晰可见。
- [两个 node prompt 分离后可能逐渐漂移] → 通过明确文件命名和用途，让 review 更容易发现不一致。

## Migration Plan

1. 在变更中定义 prompt 外置的文件组织与读取规则。
2. 在 `config/config.toml` 中新增两个 node 的 prompt 文件名配置。
3. 新增 `task_node` 和 `dsl_node` 的 system/user prompt 文件到 `config/prompts/`。
4. 重构 node 初始化逻辑，默认从配置文件解析 prompt 文件并读取内容。
5. 更新测试，覆盖“默认走文件”和“显式覆写 prompt”两种路径。

## Open Questions

- user prompt 模板应该仅作为字符串模板文件读取，还是顺手引入更正式的模板渲染抽象？
