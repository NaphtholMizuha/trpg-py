## 新增需求

### 需求:search 返回语义必须可直接驱动 planner 分支决策
系统必须保证 `search` 的 `ok/no_match/error` 三类返回语义稳定可区分，供 planner 直接判定“规则证据充分”“规则证据不足”或“检索故障”，禁止将不同结果折叠为同一空结果。

#### 场景:planner 根据 no_match 识别规则证据不足
- **当** planner 提交合法 query 且 `search` 返回 `status=no_match`
- **那么** planner 可以将该结果解释为规则证据不足
- **那么** planner 可以转入 `needs_human` 或回退策略

#### 场景:planner 根据 error 识别检索故障
- **当** `search` 返回 `status=error`
- **那么** planner 可以将该结果解释为检索链路故障
- **那么** planner 可以进入 `blocked` 或恢复流程

## 修改需求

## 移除需求
