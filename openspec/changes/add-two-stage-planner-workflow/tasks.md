## 1. workflow 骨架

- [x] 1.1 在 `src/augury/planner/` 根目录下新增新的 workflow 入口模块，定义两阶段 planner 的主流程。
- [x] 1.2 为新的 workflow 定义最小状态对象和输出边界，使其能稳定串联两个阶段节点。

## 2. 节点拆分

- [x] 2.1 在 `src/augury/planner/nodes/` 下新增第一阶段节点文件，实现 DM 指令到半结构化任务概述的最小闭环。
- [x] 2.2 在 `src/augury/planner/nodes/` 下新增第二阶段节点文件，实现任务概述到 TaskDocument DSL 的最小闭环。
- [x] 2.3 抽取两阶段共享的中间对象或共享类型，避免 workflow 与节点之间通过自由文本耦合。

## 3. 串接与验证

- [x] 3.1 将 workflow、nodes、runtime guard、task document 与现有 `planner/tools/` 串接起来，形成可运行的新 planner 主链路。
- [x] 3.2 新增或更新最小测试/ smoke，验证 workflow 能按顺序调用两个阶段节点并产出预期结构。
