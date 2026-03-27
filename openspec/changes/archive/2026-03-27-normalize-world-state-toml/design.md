## 上下文

当前默认 world state 文件采用一种“扁平点路径键 + TOML 值”的过渡式表示：

```toml
"actors.goblin_1.ac" = 13
"actors.goblin_1.hp" = { current = 7, max = 7 }
```

读取方再通过 `set_path(...)` 把这些点路径键展开回嵌套字典。这种格式对程序迁移阶段很实用，但已经带来几个问题：

- 人工维护 world state 时需要在脑中反向还原层级结构。
- 角色、法术、能力等相关字段在文件里缺少天然分组，审阅成本高。
- smoke/test_planner.py 与 smoke/test_reads.py 之类入口被迫绑定到“顶层键就是点路径”这一特殊表示，而不是真正的 TOML 层级语义。
- 后续如果要给 planner 增加更友好的 world state 视图，也需要先有一份结构清晰的 canonical fixture。

从运行时角度看，现有系统真正依赖的是“嵌套 state + 点路径访问语义”，而不是“配置文件必须写成扁平点路径键”。因此更合理的迁移方向是：改变文件表示与加载逻辑，但保持运行时 state 结构和点路径契约不变。

## 目标 / 非目标

**目标：**
- 让默认 `world_state.toml` 成为正常、可维护的嵌套 TOML 文件。
- 保持 world state 载入后的运行时结构与现有 `store`/`fetch_keys`/`reads`/planner/engine 兼容。
- 消除 smoke 入口对“顶层键就是点路径”的硬依赖。
- 统一测试夹具与默认示例，避免仓库中同时维护两套默认 fixture 表示。

**非目标：**
- 不在本次变更中重写 `store` 的点路径语义。
- 不在本次变更中引入额外的 planner 语义摘要视图或 LLM 专用 world summary。
- 不要求兼容“旧扁平格式”和“新嵌套格式”长期并存；本次迁移后仓库默认 fixture 以新格式为唯一真相。

## 决策

### 决策: canonical world state fixture 改为嵌套 TOML，运行时 state 仍保持嵌套 dict/list

`config/world_state.toml` 将改写为正常的层级 TOML，例如：

```toml
[actors.goblin_1]
id = "goblin_1"
ac = 13

[actors.goblin_1.hp]
current = 7
max = 7
```

这意味着 `tomllib.loads(...)` 返回的对象本身就已经接近运行时需要的嵌套结构，读取方可以直接把该 payload 当作 state 根对象使用，或者做极少量规范化，而不必再遍历顶层键并调用 `set_path(...)` 重建树。

保留运行时嵌套结构的原因是：现有 `store.compat`、`fetch_keys`、`reads` 与 engine 的点路径解析都建立在嵌套字典/列表上；文件表示变更不需要扩散成执行层语义变更。

考虑过的替代方案：
- 保持旧扁平格式不变：实现成本最低，但默认 fixture 的可维护性持续变差。
- 直接把 world state 改成半结构化文本：对 LLM 友好，但会破坏点路径读写与精确测试语义。

### 决策: smoke 入口直接消费嵌套 TOML，不再把顶层键当点路径展开

`smoke/test_planner.py` 与 `smoke/test_reads.py` 目前都把 `tomllib` 解析结果当成 `{path -> value}` 映射，并逐条 `set_path(...)`。迁移后，这些入口应直接接受嵌套 payload 作为默认 state。

这样做可以让 smoke 入口的世界状态载入逻辑更接近真实数据结构，并消除“只有默认 fixture 特殊，运行时 state 才是正常嵌套 dict”的额外心智负担。

考虑过的替代方案：
- 同时兼容扁平与嵌套两种默认格式：短期更稳，但会让加载逻辑和测试断言长期承担双格式复杂度。
- 只改 `config/world_state.toml`，不改 smoke loader：会直接导致 planner smoke 和 reads smoke 解析错误。

### 决策: 点路径语义与工具契约保持不变

虽然 world state 文件将改为正常嵌套 TOML，但对上层工具与执行器而言，以下约定保持不变：

- `fetch_keys` 仍返回点路径字符串
- `reads` 仍以点路径字符串作为输入
- TaskDocument 内 `state.*` `$ref` 约定不变
- engine 引用解析、变更提交与路径遍历语义不变

也就是说，本次迁移只改变“静态 fixture 如何书写与加载”，而不改变“运行时如何按点路径访问 state”。

### 决策: 测试夹具与默认示例一起迁移，避免仓库内部双标

默认 `config/world_state.toml` 迁移后，测试辅助（如 `tests/config_helpers.py` 中内嵌的默认 world state 模板）也必须一起改成嵌套 TOML。否则真实默认 fixture 与测试 fixture 将继续使用两种表示，造成后续维护混乱。

## 风险 / 权衡

- [一次性放弃旧扁平格式会影响现有依赖脚本] → 通过盘点仓库内所有 world state 读取入口并同步更新来控制风险。
- [嵌套 TOML 的写法更长] → 可读性和层级一致性显著提升，长期维护成本更低。
- [若某些测试隐式依赖 `set_path` 展开逻辑，迁移后会失败] → 需要明确覆盖 smoke loader、fixture helper 和相关单测。
- [角色 ID 含点号或特殊字符时嵌套 TOML 书写可能更复杂] → 当前 fixture 中 actor id 为 `goblin_1`、`aldera`，与 dotted tables 相容；未来若引入特殊键，仍可通过带引号 table key 解决。

## Migration Plan

1. 将 `config/world_state.toml` 重写为正常嵌套 TOML。
2. 更新 smoke/planner/reads 的默认 world state 加载逻辑，直接消费嵌套 TOML 结果。
3. 更新测试夹具模板，确保仓库内默认 world state 示例统一为嵌套 TOML。
4. 补充或调整测试，覆盖新格式下的默认加载与点路径工具行为。
5. 更新 README 或相关说明，明确默认 world state 现采用正常嵌套 TOML。

## Open Questions

- 是否需要在迁移初期保留一个仅供内部使用的兼容加载函数，用来自动识别旧扁平格式并报出迁移提示？
- 是否要顺手把默认 world state 中某些字段进一步规范化，例如为 spellcasting 增加更结构化的派生字段？本次倾向于不做，避免把格式迁移与领域 schema 扩展耦合在一起。
