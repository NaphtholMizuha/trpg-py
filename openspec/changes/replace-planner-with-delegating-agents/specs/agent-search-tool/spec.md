## 新增需求

### 需求:search 返回结果必须可直接作为 Context Agent 的规则证据输入
系统必须保证 `search` 的返回结构足够稳定，使 Context Agent 可以直接将命中结果整理为规则证据，而不是先把返回值降格为自由文本再二次解析。

#### 场景:Context Agent 消费 search 结果
- **当** Context Agent 调用 `search` 获取规则原文
- **那么** 返回结果必须保留原始命中文本和必要元数据
- **那么** Context Agent 可以直接基于这些字段构造高信息密度规则证据

## 修改需求

### 需求: search 返回语义必须可直接驱动 planner 分支决策
系统必须保证 `search` 的 `ok`、`no_match` 和 `error` 三类返回语义稳定可区分，供 Context Agent 与主 agent 直接判定“规则证据充分”“规则证据不足”或“检索故障”。系统禁止将不同结果折叠为同一空结果。

#### 场景:Context Agent 根据 no_match 识别规则证据不足
- **当** Context Agent 提交合法 query 且 `search` 返回 `status=no_match`
- **那么** Context Agent 可以将该结果解释为规则证据不足
- **那么** 主 agent 可以据此决定继续补充上下文或返回 `needs_human`

#### 场景:Context Agent 根据 error 识别检索故障
- **当** `search` 返回 `status=error`
- **那么** Context Agent 可以将该结果解释为检索链路故障
- **那么** 主 agent 可以进入 `blocked` 或恢复流程

## 移除需求

### 需求: search 工具必须提供可手动运行的集成测试脚本
**Reason**: `search` 的长期验证真相不再通过 smoke 脚本表达。
**Migration**: 将 `search` 的真实链路验证迁移到自动测试与固定评测，而不是保留 `smoke/test_search.py`。
