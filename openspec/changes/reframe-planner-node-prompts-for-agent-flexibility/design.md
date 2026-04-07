## 上下文

当前 planner prompt 的设计思路带有明显的“两种过拟合”：

1. `task_node` prompt 过度中心化任务原型分类、few-shot 覆盖面和固定工具顺序。这样做虽然在早期帮助模型快速收敛，但也让 prompt 开始规定模型“应该怎么想”，而不仅仅是“最终输出必须满足什么边界”。结果是模型更容易先把任务塞进最近的原型，再围绕这个原型补证据，而不是先从执行目标、关键前提和真实缺口出发组织 `TaskDraft`。
2. `dsl_node` prompt 通过 `template` 与 `lint` 获得了较强合法性护栏，但 prompt 仍主要强调“识别任务族 -> 查模板 -> 填参数 -> lint”。这会让模型把 engine primitive 视为模板槽位，而不是具有输入输出语义、适用边界和可组合性的执行原语。

项目当前的架构其实已经具备做得更好的前提：`TaskDraft` 是显式中间对象，engine primitive 边界明确，`template` 和 `lint` 都是结构化工具，执行器也能提供确定性的 ground truth。真正需要调整的，是 prompt 如何使用这些资产。

相关约束：
- 不能破坏 `TaskDraft` / `TaskDocumentSchema` / `template` / `lint` 的既有结构化协议。
- 不能把 prompt 放松到允许模型自由发明 engine 外 DSL。
- 需要同步更新 OpenSpec 规范，否则 prompt 改动会与当前 spec 冲突。

## 目标 / 非目标

**目标：**
- 让 `task_node` prompt 从“分类介绍式 prompt”转向“执行目标、关键前提、证据缺口和状态绑定驱动”的启发式 prompt。
- 保留 `task_node` 的必要护栏，例如不能编路径、范围效果先处理 coverage、证据不足进入 `missing_info`，但不再把“任务原型分类”写成主入口。
- 让 `dsl_node` prompt 明确解释 engine 中每类 primitive 的职责、典型输入输出、常见组合关系和边界条件。
- 让 `dsl_node` 在理解 primitive 语义的前提下自由合理搭配原语，而不是仅围绕少量模板做机械填空。
- 保留 `template` 与 `lint` 的 harness 作用，但将其定位为“结构边界与诊断反馈”，而不是替代 primitive 理解的唯一真相。
- 让规范、prompt、测试三者重新对齐。

**非目标：**
- 不在本次变更中新增 planner 节点、外层 orchestrator 或新的工具类型。
- 不在本次变更中修改 engine primitive 的代码语义或 DSL schema。
- 不试图彻底移除 few-shot、`template` 或 `lint`。
- 不在本次变更中引入新的长期记忆、自动评测框架或 LangGraph 持久化能力。

## 决策

### 决策 1：`task_node` prompt 从“任务原型优先”改为“执行需求与证据缺口优先”

- 选择原因：`TaskDraft` 的价值不在于把任务贴上类别标签，而在于诚实表达“要执行什么、需要哪些状态、缺什么证据、哪些写回是安全可绑定的”。如果 prompt 把“先归类”写成主入口，模型就更容易把分类当成答案而不是手段。
- 方案：在 prompt 中把任务原型降级为可选启发，不再要求固定的 upfront 分类与固定 few-shot 覆盖。主线改为：
  - 先识别执行目标与成功条件
  - 再识别关键前提、受影响对象和潜在写回
  - 再决定需要哪些工具证据
  - 最后把不能安全绑定的部分显式留在 `missing_info`
- 替代方案：保留现有分类骨架，只缩短文案。
- 未选择原因：这会保留旧的思维控制结构，只是把它写得更短。

### 决策 2：保留 `task_node` 护栏，但把“固定流程”改成“优先原则”

- 选择原因：完全放开会让模型重新漂移；但把 search/grep/few-shot/query mode 写成强流程，又会压扁泛化能力。需要的是高优先级原则，而不是逐步仪式。
- 方案：
  - 保留 judgment-first / evidence-driven 的精神，但允许模型在形成 provisional judgment 后迭代取证，而不是只能遵守单一路径。
  - 保留对 `grep` 的使用指导，但不要求每次都显式走“实体分类 -> 表达式模板”。
  - 对 `search` 模式仅保留锚点保持、避免身份漂移、没有可靠术语时再语义搜索这类原则，不再强制显式三选一流程。
- 替代方案：彻底删去工具使用指导。
- 未选择原因：工具 ACI 仍然需要被 prompt 清楚表达，否则会损失 harness 稳定性。

### 决策 3：`dsl_node` prompt 改成“primitive 语义说明书 + lowering 原则 + 受约束自由组合”

- 选择原因：对于 `dsl_node`，真正限制模型的不是 creativity，而是它是否理解 engine primitive 在运行时各自承担什么职责、产出什么结果、何时应该组合。若 prompt 只强调模板查询和 lint，自由组合能力就会被压成模板填空。
- 方案：
  - 在 prompt 中为每类 primitive 给出职责说明、关键输入、典型输出和与其他 primitive 的连接关系。
  - 明确“select 负责确定对象集合，check 负责产生判定结果，damage/heal/resource/effect/state 负责写回变化”这类运行语义。
  - 强调可以在合法边界内自由组合这些 primitive，只要组合符合 `TaskDraft` 的 judgments 与 engine 语义。
  - 保留 `template` 作为骨架提示与 shape 参考，但 prompt 必须明确它不是唯一组合来源。
- 替代方案：继续扩写 template few-shot，覆盖更多任务族。
- 未选择原因：这会让 prompt 再次退化为更大的模板手册，而不是提升原语理解。

### 决策 4：`template` 与 `lint` 继续充当 harness，而不是充当认知替代物

- 选择原因：这两个工具是稳定性的关键，不能弱化；但如果 prompt 把它们写成“不会用就不会生成 DSL”，模型仍会回到机械填空。
- 方案：
  - `template` 用于确认合法 shape、默认 step order、常见错误。
  - `lint` 用于提交前校验与结构化诊断。
  - prompt 明确要求模型先理解 `TaskDraft` 和 primitive 语义，再利用 `template`/`lint` 收敛，而不是把工具结果当作全部 reasoning。
- 替代方案：把 `template` 再次升级为更细的任务族枚举，缩小自由度。
- 未选择原因：会继续把 prompt 和模型都锁进分类系统。

### 决策 5：通过规范修改明确撤销旧的“分类介绍式”硬约束

- 选择原因：当前 `planner-langgraph-workflow` 规范已经把 few-shot 原型覆盖、固定 search mode 选择等写成了硬要求。如果只改 prompt 而不改 spec，后续测试和实现会长期打架。
- 方案：
  - 修改 `planner-langgraph-workflow` 中与 task 原型覆盖、固定 search mode、强流程化 prompt 相关的需求。
  - 修改 `planner-node-prompts` 中与 `dsl_node` translation rules 相关的需求，补上“primitive 语义建模与自由组合”。
- 替代方案：新增一组补充需求，不触碰旧需求。
- 未选择原因：旧需求会继续成为冲突真相。

## 风险 / 权衡

- [风险] `task_node` prompt 放松后，短期内可能出现更自由但更发散的 `TaskDraft`
  - 缓解措施：保留不能编路径、范围效果必须处理 coverage、缺证据必须进入 `missing_info` 等硬护栏，并同步更新测试断言这些边界。

- [风险] `dsl_node` prompt 强调 primitive 语义后，模型可能更愿意 freehand，而减少 `template` 使用
  - 缓解措施：保留“先 template 后 lint”的默认收敛路径，但把它表述为 guardrail 而不是认知替代。

- [风险] 规范修改范围较大，容易与现有测试文案强绑定
  - 缓解措施：把测试从“断言具体分类口号”改为“断言真正重要的边界与语义”，例如 task prompt 是否要求暴露缺口、dsl prompt 是否解释 primitive 职责。

- [风险] prompt 更启发式后，不同模型提供商之间行为差异可能放大
  - 缓解措施：在 smoke 和回归测试中保留代表性任务，优先验证结构边界、lint 通过率和范围法术等高风险案例。

## 迁移计划

1. 先更新 OpenSpec 规范，明确新的 prompt 契约。
2. 再重写 `task_node` 与 `dsl_node` 的 system/user prompt。
3. 调整测试，去掉对“分类介绍式措辞”的强绑定，改为校验新 prompt 的边界与目标。
4. 运行现有 planner workflow / smoke / dsl smoke 测试，观察是否出现明显退化。
5. 如出现退化，优先通过补充原语语义说明或护栏，而不是回滚到旧的长篇分类 prompt。

## 开放问题

- `task_node` 是否仍需要保留少量 few-shot，还是进一步压缩到几乎纯原则式 prompt？
- `dsl_node` 是否需要把每个 primitive 的“常见误用”单独列成一个紧凑表，而不是散落在 prose 中？
- 后续是否要补一个小型 eval harness，专门比较“旧 prompt vs 新 prompt”在 Fireball、混合任务和状态查询上的行为差异？
