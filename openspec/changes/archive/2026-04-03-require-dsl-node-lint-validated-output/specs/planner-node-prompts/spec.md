## 新增需求

## 修改需求

### 需求:planner node 默认 prompt 必须存放在 config prompts 目录中
系统必须将 `task_node` 与 `dsl_node` 的默认提示词存放在 `config/prompts/` 目录中的独立文件里，禁止继续把完整默认 prompt 只保留为代码内联常量。

#### 场景:默认启动 task node 与 dsl node
- **当** 调用方使用默认配置创建 `task_node` 与 `dsl_node`
- **那么** 两个节点必须能够从 `config/prompts/` 下的独立 system prompt 与 user prompt 文件读取默认提示词模板
- **那么** 两个节点不得要求调用方手工传入完整 prompt 字符串才能工作
- **那么** `dsl_node` 默认 prompt 必须明确要求在最终输出前使用 `lint` 检查 candidate
- **那么** `dsl_node` 默认 prompt 必须把输出当前 `lint` 视角下的 `valid` TaskDocument 作为默认目标
- **那么** `dsl_node` 默认 prompt 必须明确要求 `lint` 返回 `invalid` 时继续依据问题诊断修正 candidate

### 需求:task node 与 dsl node 必须使用不同的 prompt 文件
系统必须为 `task_node` 与 `dsl_node` 使用不同的 prompt 文件，禁止两个节点默认共享同一个通用 prompt 文件。

#### 场景:dsl_node prompt 处理 lint invalid 结果
- **当** `dsl_node` prompt 描述如何消费 `lint` 结果
- **那么** prompt 必须明确指出 `lint` 返回 `invalid` 时，该 candidate 不是理想最终答案
- **那么** prompt 必须指导模型优先依据 `lint` 返回的错误与模板化诊断调整 candidate
- **那么** prompt 必须指导模型继续调用 `lint` 检查修正后的 candidate，直到结果为 `valid` 或工具预算耗尽
- **那么** prompt 不得把 `lint` 仅描述成可有可无的普通参考工具

## 移除需求
