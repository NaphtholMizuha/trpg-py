## 新增需求

### 需求:主 agent orchestration 实现必须以清晰模块边界组织
系统必须将主 agent 的 orchestration 实现组织为 `augury.agent` 包内的清晰核心入口，并要求其模块命名能够直接表达“编排”职责。系统禁止继续让承担主 agent 装配与委派真相的核心实现长期停留在语义过宽或与职责不符的文件命名下。

#### 场景:维护者查找主 agent 编排入口
- **当** 维护者需要定位默认的主 agent orchestration 实现
- **那么** 他必须能够通过明确表达编排职责的模块名找到该入口
- **那么** 该入口不得与 eval helper、CLI helper 或其他支持性模块混放为同类事实标准

## 修改需求

### 需求:主 agent 必须默认提供 list_skills、load_skills 与 delegate 三个工具
系统必须为主 agent 默认提供 `list_skills`、`load_skills` 和 `delegate` 三个工具，并把它们视为能力发现与委派的基础接口。系统必须让主 agent 的 orchestration 实现与子 agent、工具装配、辅助模块保持清晰分层，禁止要求维护者从散落在 `augury.agent` 包根的杂项文件中反推出真正的委派入口。

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
- **那么** 主 orchestration、`subagents/`、`tools/` 与支持性 helper 必须呈现清晰的目录或模块边界
- **那么** 支持性 helper 不得继续与主 orchestration 入口长期平铺在同一层级并共同承担包根真相

## 移除需求
