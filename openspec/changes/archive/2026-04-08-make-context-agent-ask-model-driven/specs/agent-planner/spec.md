## 新增需求

### 需求:Context Agent 必须通过模型推理决定是否 ask
系统必须让 Context Agent 在上下文收集过程中由模型根据证据缺口决定是否调用 `ask`。系统禁止继续在 Context Agent 宿主实现中保留 `_ask_for_actor_if_needed`、`_ask_for_target_if_needed`、`_ask_for_area_point_if_needed` 这类按缺口类别硬编码的 ask 触发控制流。

#### 场景:执行者缺失但 agent 仍可先继续取证
- **当** 当前意图尚未唯一识别执行者
- **那么** Context Agent 必须先由模型判断是否应继续检索证据、直接阻塞，或发起 ask
- **那么** 宿主代码不得仅因 `actor_missing` 为真就直接触发 ask

#### 场景:范围法术缺少爆点
- **当** 范围法术意图缺少爆点或位置描述
- **那么** Context Agent 必须由模型判断是发起 ask、依据现有目标位置继续推理，还是返回其他结构化结果
- **那么** 宿主代码不得仅因命中某个法术名或位置缺失条件就直接构造 ask

## 修改需求

### 需求: planner 必须驻留在 agent 命名空间并以结构化接口对外
系统必须在 `augury.agent` 命名空间下提供 planner 能力，并以结构化输入输出接口供调用方使用，禁止仅通过临时 prompt 或不可复用脚本触发规划流程。planner 的默认模型认证信息必须通过统一配置解析后的环境变量密钥获取，而不是要求调用方把密钥直接写入项目配置文件。对于 ask 驱动的上下文收集，planner 还必须把 ask 视为模型决策的一部分，而不是宿主代码内置的业务规则分支。

#### 场景:调用方以结构化方式发起规划
- **当** 调用方向 planner 提交 instruction、state 或其他结构化上下文
- **那么** 调用方可以通过 `augury.agent` 暴露的 planner 入口发起请求
- **那么** planner 返回结构化的 `ready`、`needs_human` 或 `blocked` 结果
- **那么** 调用方不需要依赖一次性脚本或内联 prompt 才能使用 planner

#### 场景:planner 进入 ask 路径
- **当** Context Agent 在规划过程中需要澄清信息
- **那么** ask 请求必须来自模型推理结果
- **那么** planner 宿主代码不得使用字段缺失或命中特定业务模式的分支直接决定 ask

## 移除需求
