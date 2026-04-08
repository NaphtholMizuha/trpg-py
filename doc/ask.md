# Ask 工具

## 概述

Ask 工具是一个通用的、与传输层无关的机制，用于 Agent 向人类（DM）请求结构化输入。它在 Planner 工作流的 **Context Agent** 阶段使用，用于在执行任务文档之前消除意图中的歧义。

## 核心文件

| 文件 | 说明 |
|---|---|
| `src/augury/agent/tools/ask.py` | 工具核心实现 |
| `src/augury/agent/models.py` | 数据模型（AskRequest, AskResponse 等） |
| `src/augury/agent/cli_ask.py` | CLI 交互式适配器 |
| `src/augury/agent/context_eval.py` | 评估与渲染集成 |

## 数据模型

### AskRequest

```python
class AskRequest(BaseModel):
    question_id: str                        # 问题唯一标识
    prompt: str                             # 展示给用户的问题文本
    options: list[AskOption] = []           # 预定义选项
    default_option_id: str | None = None    # 默认选项（Enter 键选中）
    allow_custom_input: bool = False        # 是否允许自由文本输入
    custom_input_label: str | None = None   # 自定义输入的提示标签
    custom_input_placeholder: str | None = None  # 自定义输入的占位符
    reason: str | None = None               # 提问原因说明
```

### AskResponse

```python
class AskResponse(BaseModel):
    question_id: str
    selected_option_id: str | None = None   # 选中的选项 ID
    custom_input: str | None = None         # 自定义输入文本
```

### AskOption

```python
class AskOption(BaseModel):
    id: str
    label: str
    description: str | None = None
```

## 工具行为

`AskTool` 继承自 `langchain_core.tools.BaseTool`，名为 `"ask"`。

### 三种执行路径

1. **Resume 路径**：如果输入中包含 `resume_response`，直接返回该响应，不触发中断。
2. **Responder 路径**：如果构造时注入了 `responder` 回调，调用它并返回结果。
3. **Interrupt 路径（默认）**：抛出 `AskInterrupt` 异常，由 `ContextAgent` 捕获并向上传递，最终返回 `status="needs_human"` 的结果。

### 输入参数

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `question_id` | str | 必填 | 问题唯一标识 |
| `prompt` | str | 必填 | 展示的问题文本 |
| `options` | list | `[]` | 预定义选项 |
| `default_option_id` | str | `None` | 默认选项 ID |
| `allow_custom_input` | bool | `False` | 允许自由文本输入 |
| `custom_input_label` | str | `None` | 自定义输入标签 |
| `custom_input_placeholder` | str | `None` | 自定义输入占位符 |
| `reason` | str | `None` | 提问原因 |
| `resume_response` | dict | `None` | 用于恢复的先前响应 |

## 使用场景

Context Agent 在以下三种情况下会调用 ask 工具：

| question_id | 场景 | 输入模式 |
|---|---|---|
| `actor_identification` | 无法从意图中确定执行者 | 仅自定义输入 |
| `target_disambiguation` / `target_identification` | 目标匹配多个实体或无法解析 | 选项 + 自定义输入 |
| `area_point` | 区域法术缺少爆发点 | 选项（默认"使用目标位置"）+ 自定义输入 |

## 交互流程

```
ContextAgent.run()
  └─ _resolve_analysis_with_ask()
       while True:
         1. 分析意图 → action, entities, gaps
         2. 如果 actor 缺失 → 调用 ask_tool(actor_identification)
         3. 如果 target 歧义 → 调用 ask_tool(target_disambiguation)
         4. 如果区域法术缺少点位 → 调用 ask_tool(area_point)
         5. 全部解析完成 → 返回分析结果
```

当 `AskInterrupt` 被抛出时：
- `ContextAgent` 返回 `status="needs_human"` 的 `ContextBundle`
- `pending_interrupt` 字段包含 `PendingInterrupt` 对象
- 最终 `PlannerAgent.invoke()` 返回 `PlannerResult` with `status="needs_human"`

## CLI 适配器

`prompt_for_ask_requests()` 函数提供命令行交互界面：
- 显示格式：`"DM Ask: {prompt}"`
- 支持选项 ID 输入、Enter 键选择默认、`custom:` 前缀自定义输入
- 输入验证与错误提示

## 注册与依赖注入

在 `PlannerAgent.__init__()` 中：

```python
self.ask_tool = self.dependencies.ask_tool or create_ask_tool()
```

可通过 `PlannerDependencies.ask_tool` 注入自定义实现（如带 responder 的版本）。
