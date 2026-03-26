## 上下文

当前 planner smoke 脚本在两个地方与“真实演练”目标不匹配：

- 默认 state 是脚本内联的小字典，只覆盖 `goblin_1` / `hero_1` 的少量字段，信息密度远低于旧分支里的人类可读 world state 卡片。
- 虽然底层 planner 已支持 `thread_id + resume`，脚本自身却没有形成连续的交互回路；一旦进入 HITL，只能打印问题和 `resume.thread_id` 后退出。

你提到的其他分支 `world_state.txt` 提供了一个有价值的参照：它不是简单的测试字典，而是一份可长期维护、信息密度较高的角色/环境状态卡。当前分支不需要复刻旧实现的数据存储方式，但需要吸收这种“默认状态应足够真实”的思路，并把它落到本分支已经统一的 TOML 配置治理下。

## 目标 / 非目标

**目标：**
- 为 planner smoke 提供一份位于 `config/` 下、由 `config.toml` 指向的默认 world state 文件。
- 把旧分支中信息更丰富的 world state 内容转译成本分支可用的 TOML 表达，并采用点分路径平铺 key 以贴近 store/path 语义。
- 让 `smoke/test_planner.py` 从文件加载 world state，而不是继续在代码中硬编码极简 state。
- 让 HITL 在人类可读 smoke 模式下形成同进程交互闭环，用户可以直接输入决策继续执行。

**非目标：**
- 不在本次设计中重建旧分支的 KV 文本存储系统或兼容其全部解析逻辑。
- 不在本次设计中把任意 world state 文本自动转换为 TOML；本次只提供一份受控的默认配置样例与加载约定。
- 不在本次设计中修改 planner 核心三态协议或 Deep Agents 主流程。
- 不在本次设计中实现复杂的多轮命令编辑器；交互式 HITL 以最小可用输入流程为主。

## 决策

### 决策: 使用 `config/world_state.toml` 作为默认 smoke state 文件，并在 TOML 中采用点分路径平铺 key

旧分支的 `world_state.txt` 更接近“状态卡”而不是结构化嵌套对象。迁移到本分支时，我们不会直接把它转成深层 TOML 表结构，而是使用点分路径平铺 key，例如：

- `actors.goblin_1.ac = 13`
- `actors.goblin_1.attacks.scimitar.to_hit = 4`
- `environment.scene = "地下遗迹休整间隙"`

这样有几个好处：

- 贴近现有 store / fetch_keys 的点分路径心智模型
- 文件层面易读、易 diff，也便于后续手动补充字段
- 加载时可以稳定还原为当前 `create_planner(state=...)` 所需的嵌套 dict

考虑过的替代方案：
- 继续在脚本里写 Python dict：实现最简单，但和统一配置方向相悖。
- 直接用深层 TOML table：结构化更强，但从旧分支文本卡片迁移时不如点分 key 直观，也不利于路径级思考。
- 继续保留 `.txt`：更贴近旧分支，但与本分支现有 TOML 配置体系割裂。

### 决策: 由 `config/config.toml` 显式声明 smoke world state 路径

尽管 `smoke/test_planner.py` 是仓库脚本，不属于包内运行配置的强制边界，但当前项目已经允许“脚本主动复用统一配置”。因此本次会在统一配置中加入 planner smoke 默认 world state 路径，让这份默认状态来源可被查看和覆写，而不是埋在脚本常量中。

考虑过的替代方案：
- 只约定固定文件名 `config/world_state.toml`：实现快，但仍然把文件位置变成隐式约定。
- 给 smoke 单独再开一份配置文件：会削弱单一配置入口。

### 决策: 仅在 smoke 层做“平铺 TOML -> 嵌套 dict”转换

planner 与 fetch_keys 目前消费的仍是嵌套 Python state，对它们来说不需要知道文件是平铺 TOML 还是其他格式。因此转换逻辑应尽量留在 smoke / config 边界：

- 读取 `world_state.toml`
- 展开点分路径为嵌套 dict
- 交给 `create_planner(state=...)`

这样能把变更影响限制在 smoke 默认 state 输入层，不扩散到 planner 主体或 store 核心。

考虑过的替代方案：
- 让 `create_planner` 直接接受 world state 文件路径：会把脚本输入格式知识带进包 API。
- 在 `trpg_py.store` 内引入通用平铺 TOML 解析器：长期可能有价值，但本次范围过大。

### 决策: HITL 交互仅在人类可读 smoke 模式下进入阻塞等待

当 planner 返回 `resume.thread_id` 时，`smoke/test_planner.py` 在普通人类可读模式下不应直接退出，而应：

1. 展示问题与可选决策
2. 从 stdin 读取用户输入
3. 组装 `resume` 载荷
4. 用同一个 `thread_id` 继续调用 planner
5. 循环直到返回非 HITL 中断结果或用户主动退出

而 `--json` 模式仍保持单次调用语义，直接输出结构化结果和 resume token，方便自动化与脚本集成。

考虑过的替代方案：
- 所有模式都强制交互：会破坏 `--json` 与自动化使用。
- 仍然要求二次启动脚本：实现最省，但交互体验差。

## 风险 / 权衡

- [点分路径平铺 key 与 TOML section 语义混用容易混淆] → 约定 world state 文件只承载路径到标量/数组/对象值的映射，并在文档中给出示例。
- [旧 world_state.txt 有人类可读语义，迁移时会损失部分自然语言描述] → 保留高价值环境/状态文本为字符串字段，而不是强行拆成过细结构。
- [交互式 HITL 需要设计输入格式] → 优先支持最小决策集，例如 approve/reject/edit 对应的 JSON 映射，再逐步扩展。
- [脚本阻塞等待输入可能影响现有自动化] → 将阻塞行为限定在非 `--json` 且命中 resume token 的场景。

## Migration Plan

1. 选取旧分支 world state 卡片中的代表性内容，整理为 `config/world_state.toml`。
2. 扩展统一配置模型与 `config/config.toml`，声明默认 world state 文件路径。
3. 让 `smoke/test_planner.py` 加载并展开平铺 world state，替换当前内联 demo state。
4. 在 smoke 脚本中加入 HITL 交互循环，保留 `--json` 的单次调用模式。
5. 补充配置测试、smoke 脚本测试和使用说明。

## Open Questions

- 交互式 HITL 首版是否只支持 `approve/reject`，还是一开始就要支持 `edit` 并接受完整 JSON？
- `config/world_state.toml` 中是否需要保留一部分纯描述性字段，帮助 prompt 理解角色背景和环境，而不是只保留可执行数值？
