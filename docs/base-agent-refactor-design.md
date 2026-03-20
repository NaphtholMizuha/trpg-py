# BaseAgent 重构设计

## 目标

这份文档讨论如何重构当前的 `BaseAgent`，减少手写 agent runtime，与项目里已经引入的 `LangChain` / `LangGraph` 能力对齐。

重构目标不是立刻改写所有 agent，而是先明确一条稳定的演进方向：

- 把通用的 ReAct 工具循环尽量交给框架
- 把 `BaseAgent` 收敛成“项目级 agent 约定层”，而不是“再造一个小型 agent 框架”
- 保留项目真正需要的自定义逻辑，例如强制收口、结果兜底和日志
- 让 `Planner` / `Executor` / `Resolver` 的职责边界更清楚，后续更容易接入新的 agent

## 当前版本的状态

当前 `BaseAgent` 位于 [base.py](/home/naifen/code/trpg-py/src/agents/base.py#L77)。

它现在实际承担了几类职责：

- 创建 `ChatOpenAI` 实例
- 绑定工具
- 执行 ReAct 工具循环
- 执行结构化输出
- 在结构化输出失败时回退到手工 JSON 提取
- 执行单个工具调用并记录日志
- 在迭代上限时追加“强制输出”提示

也就是说，它虽然名义上叫 `BaseAgent`，本质上更像一个“轻量自定义 agent runtime”。

## 当前设计的问题

### 1. 重复实现了框架已有的工具循环

在 [base.py](/home/naifen/code/trpg-py/src/agents/base.py#L108) 到 [base.py](/home/naifen/code/trpg-py/src/agents/base.py#L169)，`BaseAgent` 手工实现了：

1. 调用模型
2. 读取 `tool_calls`
3. 手工执行工具
4. 拼接 `ToolMessage`
5. 再次调用模型
6. 直到没有工具调用为止

这本质上就是 ReAct agent 的主循环。

但当前项目已经依赖：

- `langchain>=1.2.10`
- `langgraph>=0.2.0`

而且这一代 `LangChain` 已经提供 `create_agent(...)` 作为主入口，负责同类循环逻辑。

因此这里最明显的问题不是“代码能不能跑”，而是：

- 维护成本重复
- 行为约定与框架逐渐分叉
- 以后如果要加 middleware、interrupt、stream、调试钩子，会变得更拧巴

### 2. `BaseAgent` 的抽象层级不纯

当前 `BaseAgent` 既像“抽象基类”，又像“运行时引擎”，还夹带了若干项目策略。

例如：

- `_react_loop` 是运行时能力
- `_invoke_structured_output` 是输出协议能力
- `_should_force_output` 是项目级收口策略

这些东西并不属于同一抽象层。

结果就是：

- 子类继承的是一个很重的父类
- 但父类又没有完整收拢“prompt 组装”和“agent 调用入口”
- `get_system_prompt()` 虽然定义成抽象方法，但在父类主流程里并没有直接消费

这会让 `BaseAgent` 看起来像统一抽象，实际上更像一个半成品工具箱。

### 3. 结构化输出同时走了框架能力和手工兜底，边界不清

在 [base.py](/home/naifen/code/trpg-py/src/agents/base.py#L171) 到 [base.py](/home/naifen/code/trpg-py/src/agents/base.py#L208)，当前实现已经正确使用了：

- `with_structured_output(..., method="json_schema")`
- `with_structured_output(..., method="function_calling")`
- `with_structured_output(...)`

这部分并不是重复造轮子。

但失败后又回退到：

- 直接 `llm.invoke(messages)`
- 手工从 markdown code fence 或文本里抽 JSON
- 再用 `Pydantic` 验证

这一层是有价值的，但它本质上是“业务可靠性补丁”，不是 agent 基类的核心职责。

如果继续把它和通用 agent loop 混在一起，后面会越来越难看出：

- 什么是框架能力
- 什么是项目策略
- 什么是兼容性补丁

### 4. 运行时状态有可变共享风险

例如 `ExecutorAgent.execute()` 会临时把 `self.llm_with_tools` 改成 `self.llm`，执行完再改回来。

这在当前串行流程下可以工作，但从设计上说：

- 父类实例带有可变运行时状态
- 子类通过覆盖实例属性改变一次调用行为

这会让“同一个 agent 实例是否线程安全、是否可复用”变得不明确。

即使短期不做并发，这也说明 `BaseAgent` 目前的职责切分还不够清楚。

### 5. 一些细节已经开始暴露“自定义 runtime”的维护成本

例如：

- `_react_loop_structured()` 中无论条件真假都会追加同样的 `force_output_prompt`
- `_extract_final_message()` 需要自己兼容 `content` 为 `str` 或 `list`
- `_execute_tool()` 需要自己处理未知工具、异常包装和日志截断

这些都不是大问题，但叠加起来说明：项目已经开始承担一套 agent 运行时的维护责任。

## 重构目标形态

推荐把未来的 `BaseAgent` 收敛成两层概念：

### 1. 框架层：交给 `LangChain` / `LangGraph`

由框架负责：

- 模型调用
- 工具循环
- `ToolMessage` 回填
- 中断点
- checkpointer 接入
- 结构化输出主路径

优先使用：

- `langchain.agents.create_agent(...)`

如果某些场景仍需保留自定义循环，也应尽量复用：

- `ToolNode`
- 统一 `messages` state
- `response_format`

### 2. 项目层：保留为你们自己的约定

由项目保留：

- agent 使用哪些工具
- prompt 模板如何组织
- 何时允许工具调用，何时禁用
- 结构化输出失败时是否允许手工 JSON 兜底
- 达到迭代上限时如何强制收口
- 对输出结果的 sanitize / fallback 策略

也就是说，重构后的核心思想应是：

> 不再让 `BaseAgent` 承担“如何当一个通用 agent”，而是只负责“本项目里的 agent 应该遵守什么约定”。

## 推荐职责拆分

### A. `BaseAgent` 只保留项目级骨架

建议未来的 `BaseAgent` 只提供这些能力：

- 创建模型或接收外部模型
- 统一日志器
- 统一 prompt 组装入口
- 统一结构化调用入口
- 统一 fallback / sanitize 钩子

它不再直接手写完整 ReAct 循环。

### B. 新增一个轻量“调用策略层”

如果项目确实需要“有时带工具，有时不带工具，有时强制结构化输出”的细粒度策略，建议显式拆出一层，而不是塞在 `BaseAgent` 里混用。

例如概念上可分成：

- `AgentCallPolicy`
- `StructuredResultPolicy`

是否真正拆成独立类，可以后面再定；关键是概念上先拆干净。

### C. 子类只关心业务

理想情况下：

- `DeepPlannerAgent` 负责“如何把 DM 输入转成 `TaskExecution`”
- `ExecutorAgent` 负责“如何把任务转成 `ExecutionResult`”
- `ResolverAgent` 负责“如何把 `ResolutionWindow` 转成 `ResolutionResult`”

子类不应该再关心：

- 如何跑工具循环
- 如何拼 `ToolMessage`
- 如何手工驱动 ReAct

## 推荐方案

本文推荐直接采用方案 B。

下面给出三个可选方向，按改动强度从低到高排列。

### 方案 A：最小侵入重构

这是最稳妥的方案，适合先把结构拉顺，不追求一步到位。

做法：

- 保留现有 `BaseAgent`
- 但把 `_react_loop` / `_execute_tool` 标记为过渡实现
- 新增统一的“agent 调用入口”，内部优先尝试 `create_agent(...)`
- 结构化输出继续保留现有 fallback
- 子类先不大改 prompt 和返回值

优点：

- 风险小
- 改造可以渐进进行
- 便于和现有 `Planner` / `Executor` / `Resolver` 对照验证

缺点：

- 会存在一段时间“双轨制”
- `BaseAgent` 仍然偏重

### 方案 B：中等力度重构

这是更推荐的主线方案。

做法：

- 用 `create_agent(...)` 接管工具循环
- `BaseAgent` 不再持有 `llm_with_tools` 这种可变运行时状态
- `BaseAgent` 去掉工具缓存职责
- 每次调用根据上下文显式构造模型
- 每次调用根据上下文显式构造工具列表
- 每次调用根据上下文显式构造 `system_prompt`
- 每次调用根据上下文显式构造 `response_format`
- 结构化输出兜底逻辑下沉为单独辅助函数或 mixin
- 如果将来仍需要缓存，应放到 tool wrapper、middleware 或更外层的数据访问层，而不是留在 `BaseAgent`

优点：

- 抽象更干净
- 更容易接 LangChain 新能力
- 更适合后续扩展 middleware、streaming、trace

缺点：

- 需要同时调整多个 agent 的调用方式
- 测试覆盖不足时风险高于方案 A

### 方案 C：彻底去掉 `BaseAgent`

这是最激进的方案。

做法：

- 每个 agent 直接持有自己的调用图
- 共通逻辑拆成若干 helper
- 不再保留继承式基类

这个方向并不是不能做，但当前项目里：

- `Planner` / `Executor` / `Resolver` 仍有明显共性
- 结构化输出、fallback、日志、工具白名单都还需要统一约定

所以现在就完全去掉 `BaseAgent`，会让公共策略重新散落回子类，短期收益不高。

当前更合适的是：

- 保留 `BaseAgent`
- 但让它变轻

## 推荐保留的自定义能力

以下能力即使迁到框架主路径，仍建议保留为项目自定义层：

### 1. 强制收口策略

`TRPG` 这类任务很容易因为工具调用反复兜圈。

因此“达到一定轮次后要求直接输出结果”是合理的项目策略。

但建议未来把它写成显式策略，而不是散在循环细节里。

### 2. 结构化输出兜底

模型供应商的结构化输出虽然越来越稳定，但在实际工程里保留一层手工 JSON 兜底仍然有意义。

建议保留，但应明确定位为：

- “可靠性补丁”
- “最后一道后备路径”

而不是主执行链路的组成部分。

### 3. 输出结果 sanitize / fallback

例如：

- `ExecutorAgent` 对 `field_changes` 的过滤和回填
- `ResolverAgent` 对非法路径的过滤
- planner 失败时的最小任务回退

这些都属于业务契约，不是框架能替代的，应继续保留在项目层。

## 推荐下沉给框架的能力

以下能力原则上不建议继续手写：

- ReAct 工具循环
- `tool_calls -> ToolMessage` 回填
- agent state 中的消息维护
- 标准化 structured response 主路径
- 中断点和 debug tracing 的运行机制
- 工具缓存与工具执行耦合的那一层

原因很简单：

- 这些是框架的核心价值区
- 自己维护收益低
- 后续接新功能的成本高

## 迁移步骤

建议分四步进行。

### 第一步：文档先行，固定目标边界

先统一团队共识：

- 什么能力保留在 `BaseAgent`
- 什么能力交给框架
- 这次重构不顺手改业务规则

这份文档就是第一步。

### 第二步：抽出与框架无关的辅助函数

优先把最容易稳定的东西从 `BaseAgent` 中拆开：

- JSON 提取辅助函数
- 结构化输出兜底函数
- 日志预览 helper

这样做的意义是：

- 先把“项目策略”从“运行时引擎”中分离
- 后面替换执行引擎时改动更小

### 第三步：让单个 agent 先切到 `create_agent(...)`

推荐先从 `ResolverAgent` 或 `DeepPlannerAgent` 试点。

原因：

- 它们更偏“读多写少”
- 工具集相对简单
- 结构化输出价值高

而 `ExecutorAgent` 因为有更多 sanitize 和特殊策略，适合在第二批迁移。

### 第四步：收敛 `BaseAgent`

当至少一个 agent 成功迁到框架主路径后，再反向收缩 `BaseAgent`：

- 移除手写 ReAct 主循环
- 移除 `_execute_tool()` 或把它降级为兼容层
- 去掉 `llm_with_tools` 这类可变共享状态
- 保留统一入口和项目策略钩子

## 风险与注意事项

### 1. 重构时不要顺手改 prompt 契约

如果在替换调用链的同时大改 prompt，很难判断问题来自：

- 框架迁移
- prompt 变化
- schema 变化

因此建议每一步尽量只改一类变量。

### 2. 结构化输出的“成功率”不等于“业务正确率”

切到框架后，即使 schema 命中率提升，也不代表：

- `field_changes` 一定合理
- `triggered_chains` 一定可用

所以业务层的 sanitize 不能删。

### 3. `ExecutorAgent` 的无工具调用分支要单独设计

当前 `ExecutorAgent` 会在某些任务下临时禁用 `evaluate`。

如果未来切到统一 agent 工厂，需要明确：

- 是传空工具列表
- 还是走不带工具的模型调用入口
- 还是做成按任务动态选择 agent 配置

这个点最好显式设计，不要继续通过修改实例属性来实现。

## 推荐的落地结论

综合当前项目状态，推荐结论是：

1. 保留 `BaseAgent`，但把它从“自定义 agent runtime”收缩成“项目级 agent 约定层”。
2. 优先把 ReAct 工具循环迁给 `langchain.agents.create_agent(...)` 或等价框架能力。
3. 采用方案 B，明确把工具缓存从 `BaseAgent` 中移除。
4. 保留强制收口、结构化输出兜底、sanitize/fallback 这些项目自定义逻辑。
5. 先挑一个风险较低的 agent 做试点，再逐步收缩旧实现。

如果用一句话总结这次重构的方向，就是：

> `BaseAgent` 不应该再负责“怎样实现一个 agent”，而应该只负责“这个项目里的 agent 需要遵守哪些共同约定”。

## 方案 B 实施细化

这一节把方案 B 进一步拆成可以直接执行的改造清单。

目标不是一次性追求“最优抽象”，而是让每一步都能：

- 变更范围清楚
- 回归风险可控
- 出问题时容易回退

### 一、目标代码形态

重构完成后，建议代码关系变成这样：

- `BaseAgent`：只保留项目级共用入口和钩子
- `DeepPlannerAgent` / `ExecutorAgent` / `ResolverAgent`：负责各自的 prompt、schema、sanitize、fallback
- 结构化输出兜底 helper：独立函数或独立模块
- agent 调用入口：统一走 `create_agent(...)` 或同等框架入口

从职责上看：

- 框架负责“怎么跑 agent”
- `BaseAgent` 负责“这个项目里的 agent 怎么接框架”
- 子类负责“这个 agent 产出什么业务结果”

### 二、建议保留在 `BaseAgent` 的接口

方案 B 下，`BaseAgent` 建议只保留这些稳定接口。

#### 1. 初始化相关

- 保存 `model`
- 保存 `api_key`
- 保存 `base_url`
- 保存 `tools`
- 保存 `max_iterations`
- 创建统一 logger

这里建议把 `self.tools` 保留为按名字索引的字典，但不再保留：

- `self.llm_with_tools`
- `self._tool_cache`
- `CACHEABLE_TOOLS`

#### 2. 模型创建接口

建议保留：

```python
def _create_llm(self, model: str, api_key: str | None, base_url: str | None) -> ChatOpenAI:
    ...
```

这个方法已经足够稳定，而且子类目前没有额外 provider 差异。

#### 3. agent 构造接口

建议新增一个统一入口，概念上类似：

```python
def _build_agent(
    self,
    *,
    tools: list[BaseTool] | None,
    response_format: type[BaseModel] | None = None,
    system_prompt: str | None = None,
):
    ...
```

这个入口内部负责：

- 创建 `llm`
- 调 `create_agent(...)`
- 传入工具列表
- 传入 `system_prompt`
- 传入 `response_format`

这样子类就不再依赖：

- 手写 `_react_loop`
- 手写 `_execute_tool`

#### 4. 统一调用入口

建议新增一个高层方法，作为所有子类的唯一执行入口。概念上类似：

```python
def _invoke_agent(
    self,
    *,
    messages: list,
    tools: list[BaseTool] | None = None,
    response_format: type[StructuredOutputT] | None = None,
    force_output_prompt: str | None = None,
):
    ...
```

这个方法负责：

- 构造 agent
- 执行 agent
- 在必要时追加强制收口提示
- 读取最终消息或结构化结果
- 失败时抛出统一异常或交给 fallback helper

#### 5. 结构化输出兜底入口

建议保留一个统一 helper，但从 `BaseAgent` 的主执行链里拆开。

例如概念上：

```python
def _invoke_structured_with_fallback(
    self,
    messages: list,
    schema: type[StructuredOutputT],
):
    ...
```

这个 helper 的职责应非常纯粹：

- 先走框架主路径
- 再走 provider fallback
- 最后才做手工 JSON 提取

不要再和工具执行循环耦合在一起。

### 三、建议移出 `BaseAgent` 的实现

以下内容建议从 `BaseAgent` 彻底移除。

#### 1. `_react_loop`

原因：

- 与 `create_agent(...)` 重复
- 手工维护成本高
- 不利于后续接 middleware / tracing

#### 2. `_react_loop_structured`

原因：

- 本质上是“工具循环 + 结构化输出”的组合器
- 更适合变成 `_invoke_agent(..., response_format=...)` 的一种模式

#### 3. `_execute_tool`

原因：

- 与框架工具节点职责重叠
- 当前还承担了异常包装和缓存逻辑，职责太杂

#### 4. `_extract_final_message`

原因：

- 如果统一走 agent graph 输出，最终消息提取应收敛在一个更薄的适配层里
- 没必要继续作为基类核心能力存在

#### 5. `_build_tool_cache_key`

原因：

- 你的决策已经很明确：缓存不再属于 `BaseAgent`

### 四、辅助函数的推荐去向

当前 [base.py](/home/naifen/code/trpg-py/src/agents/base.py#L24) 里的几个辅助函数不一定都该留在类里。

推荐拆分如下：

#### 保留为模块级 helper

- `_extract_json_payload`
- `_content_to_text`
- `_preview_text`

原因：

- 它们不依赖实例状态
- 以后可能被 `ResolverAgent`、`ExecutorAgent` 或测试代码复用

#### 如有需要可迁到新模块

建议新建类似文件：

- `src/agents/structured_output.py`
- 或 `src/agents/runtime_helpers.py`

如果后续 helper 继续增加，单独拆文件会更清晰。

### 五、每个 agent 的具体改造点

#### 1. `DeepPlannerAgent`

这是最适合先试点的 agent。

建议改造点：

- 保留 `get_system_prompt()`
- 保留 `plan()` 的 prompt 组装逻辑
- 把 `_react_loop_structured(...)` 替换成统一 `_invoke_agent(..., response_format=TaskExecution)`
- 保留 `_normalize_task()`、`_ensure_task_id()`、`_build_fallback_task()`

预期收益：

- 改动面小
- 工具集简单
- 结构化输出价值高

#### 2. `ResolverAgent`

这是第二个适合迁移的 agent。

建议改造点：

- 保留 `resolve()` 的输入组装
- 保留 `_sanitize_result()`、`_build_fallback_result()`、`_is_actionable_result()`
- 去掉对 `CACHEABLE_TOOLS` 的依赖
- 把 `_react_loop_structured(...)` 替换成统一调用入口

需要特别注意：

- resolver 的 fallback 逻辑已经是业务基线，迁移时不要改变其语义

#### 3. `ExecutorAgent`

这是最晚迁移的 agent。

建议改造点：

- 保留 `_build_key_hints()`、`_sanitize_result()`、`_backfill_missing_changes()` 等业务逻辑
- 去掉通过修改 `self.llm_with_tools` 来临时禁用工具的做法
- 改成在调用时显式选择：
  - 带 `evaluate` 工具
  - 或空工具列表

这里建议明确形成一个局部变量：

- `tools_for_call = [evaluate_tool]`
- 或 `tools_for_call = []`

而不是修改实例状态。

### 六、建议的提交顺序

为了让每个提交都相对可验证，建议按下面的顺序推进。

#### 提交 1：清理 `BaseAgent` 的文档和死概念

范围：

- 删除 `CACHEABLE_TOOLS`
- 删除 `_tool_cache`
- 删除与缓存相关的辅助逻辑
- 补充注释或 docstring，明确 `BaseAgent` 不再负责缓存

验收标准：

- 所有 agent 仍能正常初始化
- 没有残留缓存字段引用

#### 提交 2：抽 helper，不改行为

范围：

- 提取 `_extract_json_payload`
- 提取 `_content_to_text`
- 提取 `_preview_text`
- 保持行为完全一致

验收标准：

- 结构化输出相关行为不变
- 现有 fallback 不回归

#### 提交 3：为 `BaseAgent` 增加统一调用入口

范围：

- 新增 `_build_agent(...)`
- 新增 `_invoke_agent(...)`
- 暂时保留旧 `_react_loop*` 作为兼容层

验收标准：

- 新旧调用路径可并存
- 至少一个简单场景能通过新入口跑通

#### 提交 4：迁移 `DeepPlannerAgent`

范围：

- planner 改走新入口
- 删除 planner 对旧循环的直接依赖

验收标准：

- `plan()` 仍能返回有效 `TaskExecution`
- fallback 行为不变

#### 提交 5：迁移 `ResolverAgent`

范围：

- resolver 改走新入口
- 删除 resolver 对缓存概念的依赖

验收标准：

- `resolve()` 在正常路径下能得到 `ResolutionResult`
- fallback 路径语义不变

#### 提交 6：迁移 `ExecutorAgent`

范围：

- executor 改走新入口
- 显式选择本次调用是否带 `evaluate`
- 删除通过修改实例属性切换运行模式的实现

验收标准：

- 需要 `evaluate` 的任务仍能调工具
- 不需要 `evaluate` 的任务不会误进工具循环
- sanitize / backfill 行为不变

#### 提交 7：删除旧 runtime

范围：

- 删除 `_react_loop`
- 删除 `_react_loop_structured`
- 删除 `_execute_tool`
- 删除 `_extract_final_message`

验收标准：

- 所有 agent 均已不再引用旧 runtime
- `BaseAgent` 只剩项目级骨架能力

### 七、建议补充的测试

如果要让这次重构更稳，建议至少覆盖以下场景。

#### 1. `BaseAgent` 层

- 创建模型时缺少 API key 的报错行为
- 结构化输出 fallback 的解析行为
- 强制收口提示是否按 `max_iterations` 生效

#### 2. `DeepPlannerAgent`

- 正常输入能得到 `TaskExecution`
- 结构化输出失败时会回退到 `_build_fallback_task()`

#### 3. `ResolverAgent`

- 正常 window 能返回 `ResolutionResult`
- 非法 path 会被 `_sanitize_result()` 过滤
- 空结果会回退到 `_build_fallback_result()`

#### 4. `ExecutorAgent`

- 需要掷骰的任务会启用 `evaluate`
- 不需要掷骰的任务不会启用 `evaluate`
- `field_changes` 的过滤、旧值回填、HP/法术位规范化不回归

### 八、建议利用现有异常类

当前 [exceptions.py](/home/naifen/code/trpg-py/src/agents/exceptions.py#L1) 已经定义了：

- `AgentError`
- `ParseError`
- `ToolExecutionError`
- `LLMError`

重构时建议把它们真正用起来。

例如：

- provider structured output 全部失败后，可抛 `ParseError`
- agent graph 调用失败时，可包装为 `LLMError`
- 如果未来仍保留少量手工工具执行兼容层，可统一抛 `ToolExecutionError`

这样做的好处是：

- fallback 路径更清晰
- 日志更容易分类
- agent 子类不用大量直接 `except Exception`

### 九、完成态验收标准

当下面这些条件同时成立时，可以认为方案 B 基本完成：

1. `BaseAgent` 中不再包含手写 ReAct 循环。
2. `BaseAgent` 中不再包含工具缓存逻辑。
3. `ExecutorAgent` 不再通过修改实例属性来切换是否使用工具。
4. `Planner` / `Resolver` / `Executor` 都通过统一入口调用框架 agent。
5. 结构化输出兜底仍然存在，但已经从工具循环实现中解耦。
6. 业务层 sanitize / fallback 逻辑保持原有语义。

### 十、推荐的实际落地顺序

如果只从“改造收益 / 风险比”考虑，推荐实际顺序如下：

1. 先删缓存职责。
2. 再抽结构化输出 helper。
3. 然后给 `BaseAgent` 增加新调用入口。
4. 先迁 `DeepPlannerAgent`。
5. 再迁 `ResolverAgent`。
6. 最后迁 `ExecutorAgent`。
7. 最后删除旧 runtime。

这个顺序的核心思路是：

- 先减负
- 再搭桥
- 再迁业务
- 最后拆旧桥
