# lint-diagnostic-templates 规范

## 目的
定义受支持 DSL primitive 的统一模板化诊断目录，让 `lint`、`dsl_node` prompt 与测试共享同一份“合法形状”真相。

## 需求
### 需求:lint 必须为受支持 primitive 提供模板化诊断目录
系统必须为受支持的 DSL primitive 提供统一的模板化诊断目录，禁止继续只在零散 prompt 文本或单条 lint 错误消息里隐含“正确模板”知识。

#### 场景:定义高频 primitive 的 canonical 模板
- **当** 系统为 `dsl_node` 和 `lint` 准备 DSL 诊断契约
- **那么** 必须至少为 `select.area`、`check.save`、`check.attack`、`damage.apply`、`resource.consume`、`state.set` 和 `state.adjust` 提供 canonical 模板
- **那么** 每个模板必须说明必填字段和至少一个 canonical example

#### 场景:模板目录说明禁止形状
- **当** 某个 primitive 存在高频错误形状或错误字段名
- **那么** 模板目录必须能够表达常见禁止形状、错误字段名或不支持的嵌套形式
- **那么** lint 和 prompt 必须能够消费这些信息
