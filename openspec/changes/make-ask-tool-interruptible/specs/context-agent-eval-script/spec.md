## 新增需求

### 需求:Context Agent eval 脚本必须支持 ask interrupt 的恢复执行
系统必须让 Context Agent eval 脚本不仅能观察 ask interrupt，还能在支持的宿主中驱动恢复执行。系统禁止将 eval 脚本长期限定为“只展示 ask 或只采集回答，但不展示恢复后的最终结果”。

#### 场景:CLI eval 在 ask 后恢复执行
- **当** 开发者在 Python CLI 中运行 Context Agent eval 脚本且 Context Agent 触发 ask interrupt
- **那么** 脚本必须收集 DM 回答并驱动 runtime 恢复
- **那么** 脚本必须展示恢复后的最终 `ContextBundle`

## 修改需求

### 需求:Context Agent eval 脚本必须支持完整 bundle 输出
系统必须让 Context Agent eval 脚本支持输出完整 bundle 和中断恢复过程中的关键结果，以便开发者复制、比对或留档。系统禁止把结构化 bundle、interrupt 状态或恢复后的结果永久压缩成不可还原的人类摘要文本。

#### 场景:开发者请求完整输出
- **当** 开发者以完整输出模式运行 Context Agent eval 脚本
- **那么** 脚本必须输出完整的结构化 bundle
- **那么** 若本次运行经历了 ask interrupt 和恢复，脚本还必须输出可观察的 interrupt / resume 结果
- **那么** 输出内容必须能够覆盖默认摘要视图中未展示的字段细节

## 移除需求
