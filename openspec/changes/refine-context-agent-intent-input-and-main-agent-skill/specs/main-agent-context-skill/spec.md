## 新增需求

### 需求:主 agent 必须先把用户意图整理为 Context Agent 事实获取任务
系统必须要求主 agent 在委派 Context Agent 之前，先把用户原始意图整理为包含 `intent`、`goal`、`requests` 的事实获取任务。系统禁止主 agent 继续把原始用户句子直接当作唯一子任务输入下发给 Context Agent。

#### 场景:主 agent 准备委派 Context Agent
- **当** 主 agent 判定需要调用 Context Agent 收集上下文
- **那么** 主 agent 必须保留用户原始意图为 `intent`
- **那么** 主 agent 必须生成一句描述上下文采集目的的 `goal`
- **那么** 主 agent 必须生成一个 `requests` 列表来描述要获取的事实

### 需求:主 agent 生成的 requests 必须是自然语言事实获取请求
系统必须要求主 agent 生成的 `requests` 使用自然语言描述要获取或确认的事实。系统禁止把 `requests` 退化为问句列表、字段名列表或宽泛散文。

#### 场景:主 agent 为范围法术任务生成 requests
- **当** 主 agent 需要为类似“火球术攻击 goblin”之类的输入构造 Context Agent 任务
- **那么** `requests` 中的每一项都必须是可操作的自然语言事实请求
- **那么** `requests` 不得只写成 `caster_id`、`target_id` 这类字段名
- **那么** `requests` 也不得只写成“施法者是谁？”这类纯问句

## 修改需求

## 移除需求
