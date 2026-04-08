## 新增需求

## 修改需求

### 需求:agent ask tool 必须提供可复用的结构化澄清请求
系统必须提供一个可装载到多个 agent 上的通用 `ask` tool，用于在事实或背景未明晰时向 DM 发起结构化确认请求。系统禁止把 ask 能力实现为 Context Agent 私有协议或仅存在于自由文本缺口中的临时约定。

#### 场景:其他 agent 复用 ask tool
- **当** 未来有除 Context Agent 之外的 agent 需要向 DM 发起澄清请求
- **那么** 该 agent 必须能够复用同一个 `ask` tool 契约
- **那么** 调用方不得为每个 agent 单独发明新的 ask 请求格式

### 需求:ask tool 必须保持统一契约并允许不同宿主分别实现
系统必须要求 `ask` tool 的核心数据契约与交互宿主解耦。系统可以先只实现 Python CLI 作为 ask 的实际交互方式，但禁止把 ask 请求或回答格式设计成 CLI 私有协议，导致后续 HTTP 或其他宿主必须重做 agent 侧接口。

#### 场景:当前只实现 Python CLI
- **当** 系统当前只为 ask 提供 Python CLI 交互入口
- **那么** ask 的核心请求与响应字段仍必须保持统一契约
- **那么** 后续新增 HTTP 宿主时不得要求修改 agent 生成 ask 的数据模型

### 需求:ask 工具必须作为可中断工具返回结构化回答
系统必须要求 `ask` 作为可中断工具参与运行时 interrupt/resume 语义。系统禁止长期把 `ask` 定义成只返回 `AskRequest` 而不向 agent 返回最终回答结果的请求构造工具。

#### 场景:ask 恢复后返回回答
- **当** agent 调用 `ask` 且宿主随后提供恢复输入
- **那么** `ask` 必须向 agent 返回结构化 `AskResponse`
- **那么** agent 必须可以带着该回答继续执行后续逻辑

## 移除需求
