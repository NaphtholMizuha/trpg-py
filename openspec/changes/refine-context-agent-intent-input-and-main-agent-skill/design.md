## 上下文

当前系统已经建立了主 agent -> Context Agent 的委派链路，但这条链路的输入仍然偏向旧式“直接转发原始 instruction”的形状。刚完成的 Context Agent eval change 也继承了这一点：eval runner 主要在复现当前 payload，而不是复现更清晰的“事实获取任务”。

现在我们已经收敛出一个更准确的心智模型：

- `intent`：保留用户原始意图
- `goal`：说明这次上下文收集是为了什么
- `requests`：主 agent 用自然语言明确列出希望 Context Agent 获取或确认的事实

这里最重要的变化不是字段换名，而是职责变化：主 agent 不再只是把用户原话塞给 Context Agent，而是先将其整理成一项结构化的事实获取任务；Context Agent 再通过自身的工具链去收集规则证据和状态证据。

与此同时，eval 脚本和测试也需要从“打印当前 payload”升级为“验证新的委派任务是否被正确构造和展示”。再往前一步，主 agent 本身还需要一条明确的 skill / prompt 约束，确保它稳定地产生这种输入，而不是每次在实现里临时拼装。

## 目标 / 非目标

**目标：**

- 将主 agent 到 Context Agent 的输入收紧为 `intent.goal.requests` 结构。
- 要求 `requests` 使用自然语言描述事实获取请求，而不是问句、字段名或自由散文。
- 让 Context Agent 默认通过自身工具获取状态与规则证据，而不是依赖 `state/context` 作为长期输入契约。
- 补强 Context Agent eval 脚本和测试，使其围绕新输入契约工作。
- 为主 agent 增加一条明确的 skill / prompt 约束，指导它如何把用户意图整理成 Context Agent 任务。

**非目标：**

- 本次设计不扩展成更大的 delegation schema，不新增 priority、constraints、expected_outputs 等字段。
- 本次设计不重写 Context Agent 的内部证据采集策略。
- 本次设计不要求 Resolution Agent 同步改成相同的输入模式。
- 本次设计不引入新的外部依赖或复杂的 skill 执行框架；这里只定义主 agent 使用 Context Agent 的长期规范。

## 决策

### 决策 1：输入字段收敛为 `intent.goal.requests`

主 agent 给 Context Agent 的默认输入应只包含三类任务语义：

- `intent`：用户原始意图
- `goal`：上下文采集目的
- `requests`：需要获取或确认的事实请求列表

选择理由：

- `intent` 能保留用户原话，避免主 agent 在委派前过度改写任务。
- `goal` 能告诉 Context Agent 这次采集是为了什么，而不是只看到一句原始话术。
- `requests` 能把委派从“转发原始句子”升级为“明确发布事实获取任务”。

备选方案：

- 继续使用 `instruction/state/context`。未采用，因为这更像材料转发，而不是委派任务。
- 使用字段名列表如 `caster_id`、`target_id`。未采用，因为这太接近内部 schema，不能很好表达证据类请求。
- 使用问句列表。未采用，因为问句更像对话，而不是稳定的任务请求结构。

### 决策 2：`requests` 必须是可操作的自然语言事实请求

`requests` 中的每一项都应是自然语言，但必须可操作，能够映射到“需要收集的证据或需要确认的事实”。例如：

- “识别施法者对应的角色 id”
- “识别目标对应的角色 id；若不唯一则指出歧义”
- “检索与该法术结算直接相关的规则证据”

选择理由：

- 它比字段名更有任务语义。
- 它比问句更易稳定消费。
- 它允许同一列表中既包含标量事实，也包含证据类请求。

备选方案：

- 允许宽泛 prose。未采用，因为这会让 Context Agent 失焦。
- 强制请求项只能是一对一字段槽位。未采用，因为规则证据类请求天然不是单字段返回。

### 决策 3：Context Agent 默认不再把 `state/context` 当作长期输入契约

Context Agent 的长期输入契约将不再要求 `state` 和通用 `context` 字段。状态与规则材料应由 Context Agent 通过其默认工具边界自行获取。

选择理由：

- 这让主 agent 更像在发布任务，而不是在打包材料。
- 这让 Context Agent 的工具边界更有意义。
- 它能减少输入与输出中 `context` 一词的语义冲突。

备选方案：

- 把 `state` 保留为可选输入。未采用作为长期默认，因为这会弱化工具边界。
- 只删除 `context` 但保留 `state`。未采用，因为它仍然保留了“上游塞材料”的核心模式。

### 决策 4：主 agent 使用 Context Agent 的方式必须有显式 skill / prompt 约束

主 agent 需要一条明确的长期约束，指导其在调用 Context Agent 之前：

1. 保留用户原始意图为 `intent`
2. 用一句话说明上下文采集目标为 `goal`
3. 把需要确认的事实整理为 `requests`

选择理由：

- 如果没有这条约束，主 agent 很容易在实现里回退成“直接把原话塞过去”。
- 这条约束应该可被 prompt、skill 或等价配置稳定复用，而不是藏在 helper 代码里。

备选方案：

- 只在 runtime helper 中硬编码字段转换。未采用，因为这无法表达主 agent 应有的行为心智。
- 只靠测试倒逼。未采用，因为测试能发现回归，但不能表达长期设计真相。

### 决策 5：eval 脚本与测试必须把“委派任务形状”作为一等观察对象

Context Agent eval 脚本不再只是展示 bundle，还必须展示新的 `intent.goal.requests` 输入；自动测试也必须断言：

- payload 构造正确
- `requests` 为自然语言事实请求
- 输出 bundle 与这些请求的预期关注点保持一致

选择理由：

- 这能让 eval 脚本真正服务于“观察主 agent 如何使用 Context Agent”。
- 这能防止实现把新契约写在代码里，但脚本和测试仍旧围绕旧契约工作。

## 风险 / 权衡

- `requests` 仍然可能写得过宽 → 通过主 agent skill / prompt 约束和测试样例收紧“可操作的自然语言”边界。
- 去掉 `state/context` 后，部分 helper 可能需要重组 → 通过明确迁移步骤，把 payload builder、eval helper 和脚本一起调整。
- `intent` 与 `goal` 容易被写成重复内容 → 通过规范明确：`intent` 保留用户原话，`goal` 只描述上下文采集目的。
- 旧 prompt/spec 仍然带有 `task_node` 语义包袱 → 通过这次增量先把“主 agent 如何使用 Context Agent”明确写出来，逐步替换旧命名残留。

## 迁移计划

1. 先更新委派契约与相关规范，把 `intent.goal.requests` 定成新真相。
2. 再调整 runtime helper 与 Context Agent eval helper，使其构造和展示新 payload。
3. 补强自动测试，覆盖新的 payload 形状与自然语言请求样例。
4. 最后更新主 agent 的 skill / prompt 约束，使其稳定地产生这类委派输入。

回滚策略：

- 若实现阶段发现完全移除 `state/context` 影响过大，可临时保留兼容解析，但规范上的长期真相仍然是 `intent.goal.requests`。
- 若主 agent 的 skill / prompt 约束一时难以完全接通，可先通过 helper 落地，再补 prompt/skill 的正式入口。

## 开放问题

- `intent` 是直接保留用户原话，还是允许主 agent 做最小归一化后再写入。
- `requests` 是否需要固定顺序，例如“实体事实优先，规则事实其次”。
- 主 agent 的 skill 最终承载在单独 skill 文件、prompt 模板，还是 runtime 内部的配置指引。
