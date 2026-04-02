## 为什么

当前 `task_node` 和 `dsl_node` 的 system prompt 仍然内联在 Python 代码里，而 user prompt 模板也散落在节点实现内部。这样修改和对比都不方便，也不利于后续做 prompt 迭代。现在需要把这两个 node 的提示词提取到 `config/prompts/` 里，并在 `config/config.toml` 中分别配置两个 node 的 prompt 文件名，让 planner 的节点提示词与配置文件体系保持一致。

## 变更内容

- 将 `src/augury/planner/nodes/task_node.py` 中的 system prompt 与 user prompt 模板从代码常量提取到 `config/prompts/` 下的独立文件。
- 将 `src/augury/planner/nodes/dsl_node.py` 中的 system prompt 与 user prompt 模板从代码常量提取到 `config/prompts/` 下的独立文件。
- 在 `config/config.toml` 中为两个 node 分别增加 prompt 文件名配置，使默认 prompt 路径通过配置解析而不是硬编码约定。
- 为两个 node 增加统一的 prompt 加载入口，使节点默认从配置文件读取提示词，而不是把完整文案写死在模块内部。
- 保留对显式传入 prompt 字符串的覆盖能力，确保测试和局部实验仍然方便。

## 功能 (Capabilities)

### 新增功能
- `planner-node-prompts`: 定义 planner node 提示词在 `config/prompts/` 中的组织方式，以及节点默认从配置文件加载 prompt 的约束。

### 修改功能

## 影响

- 受影响代码：`src/augury/planner/nodes/task_node.py`、`src/augury/planner/nodes/dsl_node.py` 以及可能新增的 prompt 加载辅助函数。
- 受影响配置：`config/config.toml` 与 `config/prompts/` 下会新增 task/dsl node 的 system/user prompt 文件配置与对应文件。
- 受影响工作流：planner node 的提示词将从“代码常量”变成“配置文件 + 可选覆写”的模式。
