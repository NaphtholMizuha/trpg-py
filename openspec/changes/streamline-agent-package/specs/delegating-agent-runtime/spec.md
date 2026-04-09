## 新增需求

### 需求:delegating runtime 的根级兼容 shim 必须及时清理
系统必须把 `augury.agent` 包内的根级兼容 shim 视为临时迁移手段，而不是长期架构组成。对已经迁移到 `orchestrate.py`、`utils.*`、`subagents/` 或 `tools/` 的实现，系统禁止继续长期保留仅做简单转发的根级 shim 文件。

#### 场景:维护者完成一次 agent 包迁移
- **当** 某个 helper 或 orchestration 实现已经在新目录中稳定落位
- **那么** 对应的根级兼容 shim 必须在后续收口阶段被删除
- **那么** 维护者不得把“临时兼容”继续当作长期模块边界

## 修改需求

### 需求:主 agent 必须默认提供 list_skills、load_skills 与 delegate 三个工具
系统必须为主 agent 默认提供 `list_skills`、`load_skills` 和 `delegate` 三个工具，并把它们视为能力发现与委派的基础接口。系统必须让主 agent 的 orchestration 实现、子 agent、工具装配和辅助模块保持清晰分层；当某个根级模块仅剩简单转发职责时，系统必须优先删除该 shim，而不是继续让其与长期实现共同承担目录真相。

#### 场景:主 agent 查询可用能力
- **当** 主 agent 需要判断当前可调用哪些子能力
- **那么** 它必须能够调用 `list_skills`
- **那么** 返回结果必须可区分可直接加载的能力项

#### 场景:主 agent 装配某项能力
- **当** 主 agent 确定需要某项能力或子 agent profile
- **那么** 它必须能够调用 `load_skills`
- **那么** 装配结果必须可被后续 `delegate` 调用消费

#### 场景:主 agent 委派子任务
- **当** 主 agent 决定把子任务交给某个已装配的子 agent
- **那么** 它必须能够调用 `delegate`
- **那么** `delegate` 必须接受目标子 agent 标识与结构化输入
- **那么** `delegate` 不得退化为简单字符串拼接或隐藏的内部函数调用

#### 场景:维护者查看 delegating runtime 包布局
- **当** 维护者查看 `augury.agent` 的 delegating runtime 实现
- **那么** 主 orchestration、`subagents/`、`tools/` 与 `utils/` 必须呈现清晰的长期模块边界
- **那么** 已经失去独立实现价值的根级兼容 shim 不得继续保留在包根

## 移除需求
