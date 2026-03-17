DM指令: {user_input}

请分析并生成 Markdown 执行稿。

工作流程：
1. 使用工具查询需要的信息（fetch_keys/read/search）
2. 生成一份可执行的主线步骤稿
3. 预埋可能的反应/连锁线索，但不要提前裁定结果

## 输出结构

必须严格输出以下 Markdown 结构：

```markdown
## Task Summary
- Task ID: task_xxx
- Description: <一句话任务描述>
- Actor: <行动者>
- Target: <目标，无则写“无”>

## Context
- <关键状态或规则，每条尽量标明来源>

## Execution Steps
- [step_id: step_1] [status: pending] [phase: declare] [depends_on: none] [source: planner] <步骤标题> :: <执行说明>
- [step_id: step_2] [status: pending] [phase: consequence] [depends_on: step_1] [source: planner] <步骤标题> :: <执行说明>

## Planner Hints
- [hint_id: hint_1] [anchor: step_2] [when: before_step] [type: reaction] <可能插入的反应/连锁线索描述>
- [hint_id: hint_none] [anchor: step_2] [when: none] [type: none] 无

## Query Appendix
<KV 查询结果和 RAG 检索原文>
```

约束：
- 不要输出 JSON
- 不要生成 decision point、resolution effect 等结构化窗口
- `Execution Steps` 至少要有一个步骤
- 初始 `Execution Steps` 只写主线已承诺执行的步骤
- 护盾术、法术反制、借机攻击、连锁触发等“可插入片段”默认只能写进 `Planner Hints`
- 不要把“检查是否触发某反应/某窗口”直接写成初始步骤
- `Planner Hints` 只描述潜在线索，不描述最终结果
- 第一个字符必须是 `#`

示例（重要，输出风格尽量贴近这个例子）：

```markdown
## Task Summary
- Task ID: task_magic_missile
- Description: 马利克对艾尔德拉施放魔法飞弹
- Actor: 马利克(Malik)
- Target: 艾尔德拉(Aldera)

## Context
- 马利克拥有魔法飞弹 [Source: KV Malik.spells]
- 艾尔德拉拥有护盾术 [Source: KV Aldera.spells]
- 马利克拥有法术反制 [Source: KV Malik.spells]
- 护盾术可在被作为魔法飞弹目标时以反应施放 [Source: RAG]
- 法术反制可在看见60尺内生物施法时以反应施放 [Source: RAG]

## Execution Steps
- [step_id: step_1] [status: pending] [phase: declare] [depends_on: none] [source: planner] 宣告施法 :: 马利克对艾尔德拉施放魔法飞弹，并指定艾尔德拉为目标。
- [step_id: step_2] [status: pending] [phase: consequence] [depends_on: step_1] [source: planner] 结算魔法飞弹结果 :: 按魔法飞弹规则结算其伤害与后续状态变化；若执行稿后续发生更新，则按最新执行稿推进。

## Planner Hints
- [hint_id: hint_1] [anchor: step_2] [when: before_step] [type: reaction] 艾尔德拉可能在魔法飞弹结果结算前插入护盾术相关片段。
- [hint_id: hint_2] [anchor: step_2] [when: before_step] [type: reaction] 若护盾术开始施放，马利克可能进一步插入法术反制相关片段。

## Query Appendix
[KV] ...
[RAG] ...
```

请开始分析。
