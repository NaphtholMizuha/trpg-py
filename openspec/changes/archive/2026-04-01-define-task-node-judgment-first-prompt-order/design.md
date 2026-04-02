## 上下文

当前 `task_node` 即使已经被要求在规则驱动任务里先 `search` 再 `grep`，仍然经常出现：

- `judgments` 已经知道要做什么
- 但 `reads` 少了执行这些 judgments 所需的 state path
- `writes` 也可能没有与 judgments 和证据路径对齐

这说明现在的问题不只是工具顺序，而是提示词没有把 `TaskDraft` 的内部生成顺序固定下来。`judgments`、`reads`、`writes` 仍然像平行产物，而不是一条有依赖关系的生成链。

## 目标 / 非目标

**目标：**
- 明确 `task_node` 提示词中的内部顺序。
- 要求 `task_node` 先可选 `search`，再先形成 `judgments`，再用 `grep` 绑定 `reads`、`writes`、`missing_info` 和 `assumptions`。
- 让 `reads/writes` 成为 judgments 的派生产物，而不是独立自由生成。

**非目标：**
- 本次设计不引入新的 node 或 validator。
- 本次设计不修改 `TaskDraft` schema。
- 本次设计不改变 `dsl_node` 的职责。

## 决策

### 决策 1：task_node 的提示词必须固定为 judgment-first 顺序

`task_node` 的内部提示顺序应明确为：

```text
1. 判断是否需要 search
2. 如果需要，先 search 获取规则约束
3. 先形成 judgments
4. 再用 grep 为 judgments 绑定 reads / writes
5. 对无法绑定的部分写入 missing_info / assumptions
```

这样做的原因是：
- judgments 才是真正定义任务执行形状的核心
- 只有先知道“要做什么判定”，才能知道“要读哪些值、写哪些值”

替代方案：
- 继续让 judgments 与 reads/writes 平行生成：实现简单，但更容易失配

### 决策 2：missing_info 和 assumptions 也必须从 judgments 派生

当某个 judgment 需要的 read 或 write 不能被 grep 绑定到 exact path 时，prompt 必须要求把这个缺口写入 `missing_info`，必要时再写入 `assumptions`。

这样做的原因是：
- 防止 judgments 很完整，但 paths 靠猜
- 让缺口表达更有语义来源

替代方案：
- 允许 agent 直接脑补 path：会继续放大 judgments/path 漂移

### 决策 3：few-shot 必须体现 judgment-first 过程

few-shot 不应只展示“工具怎么用”，而应展示：

- 规则或状态先被理解成什么 judgments
- 然后这些 judgments 需要哪些 reads / writes
- 最后哪些 gaps 进入 missing_info / assumptions

这样做的原因是：
- 这能直接教会模型“先定判定，再找路径”
- 比抽象文字更容易稳定

## 风险 / 权衡

- [prompt 变长] → 通过少量高质量 few-shot 控制长度。
- [模型可能仍然跳过顺序] → 用更硬的措辞强调 reads/writes 必须由 judgments 推导。
- [没有 validator 兜底] → 先验证 prompt-only 是否已经显著改善一致性。

## Migration Plan

1. 更新 `task_node` system prompt，明确 judgment-first 顺序。
2. 更新 `task_node` user prompt，把 judgments 作为 reads/writes 的上游约束。
3. 调整 few-shot，展示 judgments -> reads/writes/missing_info 的派生关系。
4. 更新 smoke 或相关测试，观察 judgments/reads/writes 对齐情况。

## Open Questions

- 是否后续仍需要一个轻量语义校验层，专门检查 judgments 是否被 reads/writes 覆盖？
