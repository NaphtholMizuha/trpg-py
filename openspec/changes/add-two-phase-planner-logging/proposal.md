## 为什么

当前 planner 的工具层已经有 `loguru` 摘要日志，但当规划在结构化输出阶段或 deep agent 调用边界发生 `blocked` 时，调用方仍然只能看到被压缩后的异常字符串，无法稳定复盘导致失败的原始上下文。现在需要把 planner 运行期诊断提升为一项正式能力，通过自动落盘的详细日志文件，让开发者能在不改代码和不依赖偶发复现的前提下定位 blocked 根因。

## 变更内容

- 为 planner 增加按次运行自动生成的详细日志文件，统一写入项目内 `logs/` 目录下的 planner 日志路径。
- 按两阶段推进 planner 日志改造：
  - 第一阶段聚焦 planner 核心调用边界，记录 run 元数据、轮次信息、工具调用摘要以及 `blocked` 场景下的结构化输出异常细节。
  - 第二阶段补充更细的调试快照，包括每轮 prompt/response 摘要、修复反馈、结构化响应快照，以及 smoke 入口对文件 sink 的自动配置与展示提示。
- 让 planner 与相关 smoke 入口在保持现有人类可读摘要的同时，提供可复盘的文件日志诊断链路，而不是只依赖终端瞬时输出。

## 功能 (Capabilities)

### 新增功能
- `planner-run-logging`: 定义 planner 运行期详细日志文件的自动生成、阶段化日志范围和 blocked 场景下的诊断信息要求。

### 修改功能
- `agent-planner`: planner 的调试与失败解释能力需要扩展到文件日志诊断层，补充对结构化输出失败和轮次级运行信息的可观测性要求。
- `planner-execution-smoke`: planner 相关 smoke 入口需要补充对 planner 文件日志的自动接线或展示约定，确保开发者能找到本次运行对应的日志文件。

## 影响

- `trpg_py/agent/planner.py` 及 planner factory 的运行期日志行为。
- `smoke/test_planner.py` 与 `smoke/test_planner_engine.py` 的调试入口、默认展示和日志接线方式。
- 新增或更新 `logs/` 目录下的 planner 日志文件布局约定。
- 与 `loguru` sink 配置、测试断言和 README 调试说明相关的实现与文档。
