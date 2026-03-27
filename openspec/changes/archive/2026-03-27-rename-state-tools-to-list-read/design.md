## 上下文

当前 planner 的状态取证工具分为 `fetch_keys` 与 `reads` 两类：前者枚举路径，后者读取值。底层职责本身清晰，但对 LLM、prompt、日志和 smoke 输出来说，这两个名字偏实现导向，不如 `list` / `read` 直接。当前 `no_match` 也只返回空结果，不带任何相近路径提示；一旦 planner 拼错前缀、层级或字段名，就容易围绕同一片错误路径空间反复试探。

这次变更会同时触及 `trpg_py.agent.tools`、planner 默认工具集、prompt 文案、日志断言、smoke 入口与测试，因此属于跨模块行为变更。另一个约束是：现有 engine 与 state-store 已经稳定依赖点路径语义，变更不能引入第二套 state 访问实现，也不能把建议路径逻辑做成与 DnD 规则强耦合的硬编码表。

## 目标 / 非目标

**目标：**
- 统一 planner 面向状态的工具心智模型为 `list` / `read`。
- 保持底层仍复用 `store.keys` 与 `store.reads`，不改变 canonical state 契约。
- 在 `no_match` 时给出足够有帮助的建议路径，帮助 planner 和开发者更快修正错误路径。
- 让 planner prompt、日志、smoke 与测试围绕新工具名与新 no-match 语义保持一致。

**非目标：**
- 不重做 state-store 包的公开接口；`trpg_py.store.keys/read/reads` 等底层 API 不在本次更名范围内。
- 不引入新的 projection 层、规则推理层或 DnD 特定路径映射表。
- 不在本次设计中解决 planner 打转的全部问题；本次只收敛工具命名与 no-match 导航能力。

## 决策

### 决策 1：将 agent.tools 的公开工具名改为 `list` / `read`
- 选择：planner 默认工具集中的路径枚举工具统一名为 `list`，值读取工具统一名为 `read`。
- 理由：这两个名字更贴近 LLM 的通用读 state 心智模型，也更容易在 prompt 中形成“先 list，再 read”的稳定策略。
- 替代方案：
  - 保持 `fetch_keys` / `reads` 不变，只在 prompt 里解释它们等价于 list/read。缺点是模型与人类都仍需持续做术语翻译。
  - 同时暴露两套同权重名称。缺点是 planner prompt 和日志会出现双重语义，增加工具选择歧义。

### 决策 2：底层实现继续复用现有 store 能力，不创建第二套读路径实现
- 选择：`list` 继续包装 `store.keys`，`read` 继续包装 `store.reads` / `store.read`。
- 理由：这样可以把行为变化收敛在 agent.tools 这一层，不改 engine 和 state-store 的既有契约。
- 替代方案：
  - 为 planner 单独实现 projection 或缓存索引层。缺点是本次范围明显扩大，且会引入新的同步和测试面。
  - 在 no-match 时查询外部规则或世界知识。缺点是建议路径本质是 state 导航问题，不应依赖规则系统。

### 决策 3：`no_match` 建议路径基于当前 state 的可枚举点路径集合做相似度推荐
- 选择：当 `list(prefix=...)` 或 `read(paths=...)` 返回 `status=no_match` 时，工具额外返回少量建议路径；建议来源于当前 state 的点路径全集或相关子集，经前缀邻近、token 重叠和字符串相似度排序。
- 理由：建议路径应该只依赖当前 state 结构，而不是依赖 DnD 规则知识或人工维护的字段别名字典。这样无论世界状态如何扩展，建议逻辑都能稳定工作。
- 替代方案：
  - 纯编辑距离。缺点是对层级错误、前缀偏移、复数/下划线差异不够鲁棒。
  - 维护“法术位/HP/位置”等语义映射表。缺点是容易演化为不断膨胀的硬编码词典。
  - 不返回建议，只维持空结果。缺点是 planner 和开发者都缺少收敛线索。

### 决策 4：建议路径返回格式保持结构化且有限
- 选择：`no_match` 返回体新增建议字段，数量保持小而稳定，例如最多 3-5 条，且每条建议都使用 canonical 点路径字符串。
- 理由：建议的目标是帮助收敛，不是替代完整枚举；太多建议会让 planner 和人类都更难选。
- 替代方案：
  - 返回全部相近路径。缺点是噪声太大，且输出成本高。
  - 返回自然语言解释而不返回路径。缺点是 planner 仍然无法直接把建议转回可读写路径。

### 决策 5：planner 默认 prompt、日志和 smoke 输出统一采用新工具语义
- 选择：planner prompt、smoke 文案、日志摘要、测试断言统一改为 `list` / `read`，并明确告诉 planner 可在 `no_match` 结果中利用建议路径继续收敛。
- 理由：如果只改工具实现而不改 prompt/日志，LLM 和开发者仍会被旧术语牵引，效果会打折。
- 替代方案：
  - 只在工具对象层改名，不动 prompt。缺点是模型仍会生成旧工具调用意图，收益有限。

## 风险 / 权衡

- [破坏性更名会影响既有测试和调用点] → 在实现中评估是否保留轻量 deprecated alias，并在迁移说明里明确默认工具名已改为 `list` / `read`。
- [建议路径排序不稳定会让 planner 更困惑] → 采用固定的排序策略和上限，并为典型 no-match 输入补充测试。
- [全量枚举相似度计算可能增加成本] → 优先利用 prefix 缩小候选集；仅在无前缀或候选为空时退回全量路径。
- [建议路径看似“智能”，实际却掩盖真实无数据] → 保持 `status=no_match` 为主语义，建议只作为附加线索，不能伪装成命中。

## Migration Plan

1. 在 agent.tools 层引入 `list` / `read` 命名与 no-match 建议字段。
2. 同步更新 planner 默认工具集、prompt、日志输出与 smoke 脚本文案。
3. 更新对应单元测试、日志断言与 smoke 测试。
4. 若保留旧 helper 或导出别名，明确标记其兼容性质；若不保留，则在变更说明中明确迁移方式。
5. 若实现后发现建议排序噪声过大，可回滚到“保留新名称但禁用建议字段”的较小变更。

## Open Questions

- 是否需要在 Python 导出层短期保留 `create_fetch_keys_tool` / `create_reads_tool` 这类兼容 helper，还是直接只保留新入口？
- `read` 的建议路径是否应该按“每个请求 path 单独给建议”返回，还是在顶层统一汇总建议列表？
- `list` 的建议路径是否需要显式区分“相近前缀建议”和“完整点路径建议”，还是统一用路径列表即可？
