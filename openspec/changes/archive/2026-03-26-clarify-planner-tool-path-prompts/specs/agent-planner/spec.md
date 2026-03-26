## 新增需求

### 需求:planner prompt 必须显式区分工具路径与 TaskDocument 引用路径
系统必须让 planner 默认 prompt 明确区分两套路径语义：`fetch_keys` 与 `reads` 消费的是当前 store 的裸点路径（如 `actors.aldera.ac`），而最终 `TaskDocument` 中的 `$ref` 使用 `state.*`、`context.*`、`result.*` 命名空间。系统禁止继续让 prompt 把这两类路径语法混为一谈，导致模型把 `state.` 前缀误用于工具参数。

#### 场景:planner 使用 fetch_keys 和 reads 时采用裸 store 路径
- **当** planner 需要发现 actor、AC、HP、攻击加值或其他 state 路径
- **那么** prompt 必须告诉模型向 `fetch_keys` 与 `reads` 传入裸 store 路径
- **那么** 路径示例必须使用 `actors.goblin_1.ac`、`actors.aldera.hp` 等形式
- **那么** prompt 不得把 `state.actors...` 当作工具参数示例

#### 场景:planner 在 TaskDocument 中继续使用命名空间引用
- **当** planner 已经通过工具确认了真实 store 路径并准备输出 `TaskDocument`
- **那么** prompt 必须告诉模型在 `$ref` 中使用 `state.<store-path>` 形式引用 state
- **那么** prompt 必须保留 `context.*`、`state.*`、`result.*` 等命名空间引用约定
- **那么** 模型可以区分“工具输入路径”和“最终文档引用路径”不是同一种字符串

#### 场景:prompt 示例展示从工具路径到最终引用的映射关系
- **当** prompt 提供 canonical example、工具说明或路径示例
- **那么** 相邻内容中必须可见从 `actors...` 裸路径到 `state.actors...` 引用路径的对应关系
- **那么** 开发者和模型都可以看出 planner 应先用工具确认真实路径，再把该路径写入最终 `$ref`

## 修改需求

## 移除需求
