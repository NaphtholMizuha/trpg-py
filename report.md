# TRPG Agent 项目面试介绍提纲（扩展版）

## 1. 项目场景（这个项目解决什么问题）

这个项目是一个 **TRPG（桌面角色扮演）战斗结算 Agent 系统**，核心目标是把 DM 的自然语言指令，转成可执行、可审计、可回写的状态变更。

典型场景：
- DM 输入：`马利克对艾尔德拉施放魔法飞弹`
- 系统自动完成：任务规划 -> 执行掷骰/规则判断 -> 反应窗口处理（如护盾术、法术反制）-> 冲突裁决 -> world-state 回写

项目定位不是“纯聊天”，而是 **带状态机的规则执行系统**，重点是“结果落地正确”而不是“回答好看”。

进一步说，我在项目里解决的是三个工程化痛点：
- 规则复杂且可中断：同一动作可能被反应动作（Shield/Counterspell）打断，不能线性处理
- LLM 输出不稳定：需要强结构约束和兜底，不能让自由文本直接改状态
- 结果要可审计：每次状态变化都需要能回溯“为什么这样改”

---

## 2. 模块设计（系统怎么拆）

主流程基于 LangGraph：

`planner -> task_approval -> executor -> window_review -> resolver -> commiter -> planner`

如果用“职责分离”解释这条链路：
- planner 负责“定义这一步要做什么”
- executor 负责“把这一步算出来”
- resolver 负责“多步骤冲突时谁生效”
- commiter 负责“把最终结果安全写回”

### A. Planner（`src/agents/deep_planner.py`）
- 输入 DM 指令，输出结构化 `TaskExecution`
- 结合 skill（`combat` / `world_edit`）做意图路由
- 负责生成可执行的一步任务，而不是多轮剧本
- 会做 actor/target 归一化（例如中文名映射到 `Malik`/`Aldera`）
- 会补强 `write_targets`（例如施法动作自动补 `spell_slots` 写路径）

### B. Executor（`src/agents/executor.py`）
- 执行单步任务，输出 `ExecutionResult`
- 只允许 `evaluate` 工具做随机与表达式计算
- 输出按三类拆分：`resource_costs` / `primary_effects` / `contingent_effects`
- 做严格清洗：只允许修改上下文里出现的 key，非法 path 直接过滤
- 对 HP 等字段做值规范化，降低“文本格式漂移”导致的脏数据

### C. Resolution Window + Resolver（`src/workflow/nodes.py`, `src/agents/resolver.py`）
- 把同一结算窗口的多个 run（主动作 + 反应动作）合并
- 按 `priority + order` 处理事件先后
- 产出 `ResolutionResult`（最终生效与丢弃变更）
- 保留 discarded 轨迹，说明哪些变更被后续动作覆盖或取消
- 保守策略：不确定时给 `dm_suggestions`，不硬编规则结论

### D. Commiter（`src/workflow/nodes.py`）
- 统一把字段级变更写回 KV world-state
- 防止非法路径写入（必须是 `Key.Field`）
- 只在最终节点落地，避免执行阶段直接污染状态
- 兼容两种提交模式：直接执行结果提交 / resolver 窗口裁决后提交
- 提交前检查 key 是否存在，避免对不存在实体做 MOD/DEL

### E. Toolkit（`src/tools/toolkit.py`）
- 核心工具：`fetch_keys/read/search/evaluate/write_fields`
- `search` 用 RAG 查 D&D 5e SRD
- `evaluate` 执行骰子与数值逻辑
- 工具层统一日志，便于定位“是模型问题还是工具问题”

### F. 状态存储（`src/tools/kv_state.py`）
- 扁平 KV 存储（支持 txt/toml）
- 支持字段级 patch 与自动 summary 刷新（如 combat、spell_slots）
- 支持文件锁写入，保证持久化场景下的基本一致性

### G. 评测体系（`src/evals/*` + `evals/*`）
- 分 planner/executor/resolver/workflow 多层评测
- case + scorer + report 的可回归结构
- 支持 fake workflow 与真实 workflow，适配单测与集成评测

---

## 2.1 一次完整请求的落地路径（可面试口述）

以“马利克施放魔法飞弹，艾尔德拉可能用护盾术”为例：

1. Planner 产出单步任务，明确 actor/target、上下文、可写字段  
2. Task Approval 节点支持人工中断确认（也支持 auto confirm）  
3. Executor 计算伤害与资源消耗，返回结构化变更  
4. Window Review 决定是否追加同窗口反应动作（如 Shield、Counterspell）  
5. Resolver 按优先级合并 run，产出 final/discarded 变更  
6. Commiter 统一写回 world-state  
7. 进入下一轮 planner，继续处理新输入或链式任务

---

## 3. 细节设计（你可以重点讲“做难做对”的地方）

### 3.1 严格结构化输出 + 多层 fallback
- 所有 agent 输出都走 Pydantic schema（`src/types.py`）
- 若结构化输出失败，`BaseAgent` 会降级到多种 structured-output 模式，再尝试 JSON 抽取兜底
- 目的：降低 LLM 输出漂移对系统稳定性的影响
- 这点是生产可用的关键：模型可以波动，但系统契约不能波动

### 3.2 任务与写回的“字段级约束”
- Planner 会把写目标规范到字段级路径（如 `Aldera.combat.HP`）
- Executor 二次清洗，禁止写未知 root key，禁止整 key 覆盖
- Commiter 再做最后一次合法性检查后才写入
- 这形成了“三道闸门”，把 hallucination 风险拦在提交前

### 3.3 反应链的窗口化裁决
- 不是一条任务立即写回，而是先进入 `ResolutionWindow`
- 支持追加同窗口动作（interrupt）
- Resolver 对同路径冲突给出 final/discarded 结果，解决“先后动作互相覆盖”的问题
- 这是项目里最有区分度的设计，解决了 TRPG 的非线性结算问题

### 3.4 随机性控制策略
- 仅在需要随机判定时调用 `evaluate`
- 明确“同一随机量只掷一次，结果复用”
- 保证战斗可解释性，避免多次掷骰导致的不一致
- `LogicEngine` 会记录掷骰拆解轨迹，方便日志审计与复盘

### 3.5 可观察性与测试
- workflow 节点有清晰日志输出（planner/executor/resolver/commit）
- 单测覆盖：类型归一、路径清洗、窗口优先级、fallback 等
- eval runner 可按 provider/model 批量回归并产出报告
- 文档里还定义了阶段性优化策略（比如 planner 写目标稳定性、resolver discard 一致性）

---

## 3.6 关键数据结构（面试官追问“你怎么建模”时可用）

### TaskExecution（planner 输出）
- 描述本轮唯一可执行任务
- 核心字段：`description/context/execution_steps/write_targets/actor/target/task_category`

### ExecutionResult（executor 输出）
- 不是一团 field_changes，而是三段语义桶：
- `resource_costs`：法术位/反应等成本
- `primary_effects`：动作直接效果
- `contingent_effects`：条件成立才生效的效果

### ResolutionWindow / ResolutionResult（resolver 输入输出）
- Window 聚合同一结算窗口 run
- Resolution 输出 final + discarded，保留冲突裁决轨迹

这个建模好处是：
- 上下游职责清晰
- 评测可精确到桶级别
- 后续扩展“回放/撤销/日志审计”更自然

---

## 3.7 Prompt 分层策略（不是一个超级提示词）

项目把 prompt 拆成 planner/executor/resolver 三套，分别强调：
- planner：产出一步任务与上下文完整性
- executor：只做可落地执行，严格约束 path 和工具使用
- resolver：只处理窗口裁决，不做随机、不直接写状态

这能降低单一提示词“职责互相污染”的问题。

---

## 3.8 Skill 机制（领域约束注入）

通过 skill registry 动态加载 `combat` / `world_edit` 规则片段：
- `combat` 强调规则检索、反应链、不确定项确认
- `world_edit` 强调 DM 直改状态（绕过掷骰）

优点：
- 把“领域差异”从核心代码里抽离
- 降低主流程复杂度
- 后续可增新 skill 而不重写 planner 主体

---

## 4. 技术点（面试时可直接抛关键词）

- **LangGraph 状态机编排**：多节点可中断流程、窗口化结算
- **LangChain Agent + ToolStrategy**：结构化输出驱动，不做自由文本串联
- **Pydantic 契约治理**：TaskExecution / ExecutionResult / ResolutionResult 全链路 schema 化
- **RAG 混合检索**：Qdrant Dense + BM25 + Rerank（SRD 规则检索）
- **规则执行引擎**：`asteval` + 自定义 `Roll('XdY')` 掷骰轨迹
- **KV 状态系统**：字段级 patch + 派生 summary 自动刷新
- **评测工程化**：组件评测 + 端到端 workflow 评测 + 报告输出
- **Prompt 工程**：planner/executor/resolver 分治，硬约束路径与职责边界

如果要再“工程化”一点可以补这句：
- **Workflow 可中断交互**：基于 LangGraph interrupt 支持审批、窗口追加动作与人工裁定

---

## 4.1 设计取舍（面试官常问“为什么这样做”）

### 取舍 1：为什么不用单 Agent 端到端直接写状态？
- 单 Agent 简单，但不可控
- 当前方案通过 planner/executor/resolver/commiter 分层，把风险拆开并可定位

### 取舍 2：为什么要字段级 path，不直接整段文本覆盖？
- 整段覆盖容易误伤无关字段
- 字段级 patch 更安全，且评测可以精确到路径

### 取舍 3：为什么要 window + resolver？
- TRPG 有 reaction/interrupt，动作不是严格线性
- window 模型更贴合规则时序，能处理“同路径多次改写”

### 取舍 4：为什么要保留 discarded changes？
- 只看最终值会丢掉裁决信息
- discarded 让“为什么没生效”可解释

---

## 4.2 当前挑战与下一步优化（可体现你的思考深度）

从文档与评测结果看，当前主要挑战：
- planner 在资源字段写回目标上仍可能不稳定（如 spell_slots 漏规划）
- resolver 在“动作取消时资源成本是否丢弃”语义上存在波动
- executor 虽然整体稳定，但偶发 narration 与结构化结果不同步

下一步我会做：
- 把资源字段补强逻辑进一步规则化，并加 case 覆盖
- 在 resolver 明确 run 级裁决准则，再映射到字段桶
- 增加一致性后处理，确保 narration 与结构化字段不矛盾

---

## 5. 面试可用的 60 秒版本

我做的是一个面向 TRPG 的多 Agent 结算引擎。它把 DM 的自然语言指令，通过 LangGraph 编排成 planner、executor、resolver、commiter 的状态机流程。核心难点是反应链和冲突裁决，所以我引入了 ResolutionWindow，把同一结算窗口内的动作按优先级合并，再统一写回 world-state。  
在工程上我重点做了三件事：第一是全链路结构化输出和 fallback，降低 LLM 漂移；第二是字段级写回约束，避免脏状态；第三是评测体系，把 planner/executor/resolver/workflow 分层回归。最终系统不只是“会说规则”，而是能稳定落地并可审计。

---

## 5.1 面试可用的 3 分钟版本

这个项目本质是把 TRPG 结算问题工程化。输入是 DM 自然语言，输出不是聊天文本，而是可提交的状态变更。  
我把系统拆成四层：planner 只负责产出一步任务，executor 只负责执行并给结构化结果，resolver 只负责同窗口冲突裁决，commiter 只负责安全写回。  
其中最关键的设计是 ResolutionWindow，因为 TRPG 的动作会被反应动作中断，不能线性处理。我们把同一窗口里的 run 按 priority/order 合并，最后输出 final/discarded 变更，这样“谁生效、谁被覆盖”是可解释的。  
为了稳定性，我做了三道保护：第一道是 Pydantic schema 约束；第二道是 executor 的路径清洗；第三道是 commiter 的写回校验。即便模型输出有波动，也不会直接污染 world-state。  
最后我补了评测框架，把 planner/executor/resolver/workflow 分层回归，可以客观比较不同模型、提示词和版本，支持持续迭代。

---

## 5.2 常见追问回答（你可以直接背）

### Q1：你做这个项目最难的点是什么？
- 最难的是反应链和冲突裁决，不是普通问答
- 解决方案是窗口化建模 + resolver 时序合并 + discarded 轨迹保留

### Q2：怎么保证 LLM 不乱改状态？
- 结构化 schema + 字段级路径约束 + 最终提交校验三层防线
- 非法路径、未知 key、整 key 覆盖都会被拦截

### Q3：为什么要自己做评测，不靠人工看日志？
- 人工看一次可以，迭代几十次不行
- 评测把“感觉正确”变成可回归指标，能发现退化

### Q4：这个架构的可扩展性在哪？
- skill 可插拔，便于新增领域规则
- data model 稳定，便于接 settlement log / 回放 / 撤销
- workflow 节点清晰，便于替换单节点策略
