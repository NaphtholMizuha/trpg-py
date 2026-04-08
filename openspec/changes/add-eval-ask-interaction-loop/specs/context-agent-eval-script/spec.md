## 新增需求

### 需求:Context Agent eval 脚本必须在交互式 CLI 中执行 ask 交互
系统必须让 Context Agent eval 脚本在交互式 Python CLI 场景下对 `ask_requests` 执行真实交互，而不只是打印请求内容。系统禁止在检测到可交互终端后仍把 ask 停留在只读展示状态。

#### 场景:脚本在交互终端里采集 ask 回答
- **当** 开发者在交互式终端中运行 Context Agent eval 脚本且 bundle 返回 `ask_requests`
- **那么** 脚本必须逐条展示问题、候选选项、默认值和自定义输入入口
- **那么** 脚本必须采集 DM 的回答并生成结构化 `AskResponse` 列表

### 需求:Context Agent eval 输出必须同时展示 ask 请求与 ask 回答
系统必须让 Context Agent eval 脚本在完成 ask 交互后同时展示原始 ask 请求和结构化 ask 回答。系统禁止只展示请求而隐藏回答，或只展示回答而丢失问题上下文。

#### 场景:脚本回显 ask 结果
- **当** Context Agent eval 脚本在一次运行中采集到 ask 回答
- **那么** 调用方必须能直接看见 ask 请求中的问题文本、选项和默认值
- **那么** 调用方必须能直接看见最终选择或自定义输入结果

## 修改需求

### 需求:Context Agent eval 脚本必须支持完整 bundle 输出
系统必须让 Context Agent eval 脚本支持输出完整 bundle 和已采集的 ask 回答，以便开发者复制、比对或留档。系统禁止把结构化 bundle 或 ask 响应永久压缩成不可还原的人类摘要文本。

#### 场景:开发者请求完整输出
- **当** 开发者以完整输出模式运行 Context Agent eval 脚本
- **那么** 脚本必须输出完整的结构化 bundle
- **那么** 若本次运行已采集 ask 回答，脚本还必须输出完整的结构化 `AskResponse` 列表
- **那么** 输出内容必须能够覆盖默认摘要视图中未展示的字段细节

## 移除需求
