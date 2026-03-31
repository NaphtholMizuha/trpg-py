## 新增需求

### 需求:planner node 默认 prompt 必须存放在 config prompts 目录中
系统必须将 `task_node` 与 `dsl_node` 的默认提示词存放在 `config/prompts/` 目录中的独立文件里，禁止继续把完整默认 prompt 只保留为代码内联常量。

#### 场景:默认启动 task node 与 dsl node
- **当** 调用方使用默认配置创建 `task_node` 与 `dsl_node`
- **那么** 两个节点必须能够从 `config/prompts/` 下的独立 system prompt 与 user prompt 文件读取默认提示词模板
- **那么** 两个节点不得要求调用方手工传入完整 prompt 字符串才能工作

### 需求:task node 与 dsl node 必须使用不同的 prompt 文件
系统必须为 `task_node` 与 `dsl_node` 使用不同的 prompt 文件，禁止两个节点默认共享同一个通用 prompt 文件。

#### 场景:节点初始化默认 prompt
- **当** `task_node` 与 `dsl_node` 初始化默认 prompt
- **那么** `task_node` 必须读取属于自己的 system prompt 文件与 user prompt 文件
- **那么** `dsl_node` 必须读取属于自己的 system prompt 文件与 user prompt 文件

### 需求:config.toml 必须为两个 node 单独声明 prompt 文件名
系统必须在 `config/config.toml` 中为 `task_node` 与 `dsl_node` 分别声明 prompt 文件名配置，禁止只依赖代码约定猜测文件名。

#### 场景:节点解析默认 prompt 配置
- **当** `task_node` 或 `dsl_node` 需要加载默认 prompt
- **那么** 节点必须通过 `config/config.toml` 中属于自己的 prompt 配置节解析 `system_file` 与 `user_file`
- **那么** 节点不得把文件名只写死在代码里作为唯一真相

### 需求:显式传入的 prompt 必须覆盖文件默认值
系统必须允许调用方在 node 依赖或初始化参数中显式传入 prompt 文本，并且该值必须覆盖配置文件中的默认 prompt 内容。

#### 场景:测试覆写 task node prompt
- **当** 调用方为 `task_node` 或 `dsl_node` 显式提供 prompt 字符串
- **那么** 节点必须优先使用显式提供的 prompt
- **那么** 节点不得继续读取并覆盖该显式值

## 修改需求

## 移除需求
