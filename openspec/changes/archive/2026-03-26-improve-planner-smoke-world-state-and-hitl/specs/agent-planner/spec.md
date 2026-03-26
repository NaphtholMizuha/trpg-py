## 新增需求

## 修改需求

### 需求:planner 集成脚本必须帮助开发者观察代表性规划结果
系统必须让 planner 集成脚本支持至少一个可复现示例场景，并能够向开发者清晰展示 `task_document`、澄清问题或阻塞原因等核心结果。该结果必须来源于真实调用，而不是脚本预制的假响应。默认示例场景必须使用一份足够丰富的 world state 文件，而不是继续使用只含少量字段的内联最小 state。

#### 场景:脚本展示 planner 结果摘要
- **当** planner 集成脚本完成一次规划请求
- **那么** 调用方可以从输出中看出 planner 返回的真实状态类型
- **那么** 调用方可以查看对应的真实 `task_document`、`questions` 或 `error` 摘要

#### 场景:脚本使用更真实的默认世界状态
- **当** 开发者直接运行 `smoke/test_planner.py`
- **那么** 脚本必须从配置指定的默认 world state 文件加载示例状态
- **那么** 该状态必须覆盖比当前极简内联 state 更完整的角色、战斗或环境信息
- **那么** 脚本不得继续把内联最小字典作为默认真相

### 需求:planner smoke 脚本必须默认验证真实配置链路
系统必须让 `smoke/test_planner.py` 默认读取项目统一配置并构造真实 planner，禁止以内置 fake agent、fake LLM、fake tool 或脚本预制结果作为默认 smoke 路径。默认 smoke 状态也必须通过配置指定的 world state 文件提供，并在加载后转换为真实 planner 使用的 state 结构。

#### 场景:开发者直接运行 planner smoke 脚本
- **当** 开发者执行 `python smoke/test_planner.py`
- **那么** 脚本必须读取 `config/config.toml` 或显式传入的配置路径
- **那么** 脚本必须通过 `trpg_py.agent.create_planner(...)` 构造真实 planner
- **那么** 规划过程中必须使用真实 `search` 与真实 `fetch_keys` 工具链路
- **那么** 默认 state 必须来自配置指定的 world state 文件而不是内联常量
- **那么** 脚本不得默认返回脚本内部伪造的规划结果

### 需求:planner smoke 脚本必须展示真实规划结果
系统必须让 `smoke/test_planner.py` 的输出直接来源于真实 planner 调用结果，禁止把预制 `ready`、`needs_human` 或 `blocked` 响应当作 smoke 输出真相。命中 HITL 中断时，脚本在人类可读模式下不得直接结束进程，而必须等待用户输入并继续同一规划线程，直到用户主动退出或规划返回最终结果。

#### 场景:脚本输出真实 planner 结果
- **当** planner smoke 脚本完成一次规划调用
- **那么** 人类可读摘要或 JSON 输出必须展示真实返回的 `status`
- **那么** 若返回 `ready`，输出中必须可见真实 `task_document` 摘要或正文
- **那么** 若返回 `needs_human` 或 `blocked`，输出中必须可见真实问题列表或错误信息

#### 场景:HITL 中断后脚本继续等待人工输入
- **当** planner smoke 脚本在非 JSON 模式下收到带 `resume.thread_id` 的 HITL 中断结果
- **那么** 脚本不得直接结束程序
- **那么** 脚本必须等待用户输入审批或补充决策
- **那么** 脚本必须使用同一个 `thread_id` 继续调用 planner 直到得到下一次真实结果

## 移除需求
