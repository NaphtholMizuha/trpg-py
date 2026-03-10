"""
ExecutorAgent - 执行Agent

合并逻辑计算 + 状态写入
使用ReAct模式，通过tools执行计算和写入
"""
import uuid
import json
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool

from ..types import PlannedTask, ExecutionResult, StateChange


class ExecutorAgent:
    """
    ExecutorAgent - 执行Agent

    职责:
    1. 分析PlannerAgent生成的自然语言任务描述
    2. 使用evaluate工具执行表达式计算（含Roll）
    3. 使用write工具修改KV记忆
    4. 返回执行结果

    如果不能确定计算逻辑，回滚到DM确认
    """

    SYSTEM_PROMPT = """你是D&D 5e的ExecutorAgent，负责执行任务并生成状态变更指令。

你的职责:
1. 解析Planner生成的自然语言任务描述
2. 使用fetch_keys和read工具读取当前状态
3. 使用evaluate工具执行掷骰和计算
4. 根据结果生成结构化的状态变更指令（ADD/MOD/DEL）
5. 使用write工具执行状态变更
6. 输出结构化的执行结果

可用工具:
- fetch_keys: 获取所有KV状态的key列表
- read: 读取指定key(s)的值
- evaluate: 执行Roll()表达式，如 "Roll('1d20') + 7 >= 15"
- write: 修改KV状态（支持ADD/MOD/DEL）

执行流程:
1. 先用fetch_keys查看所有可用的key
2. 根据任务描述读取相关角色的状态（read工具）
3. 从状态中解析出数值（AC、HP、攻击加值等）
4. 使用evaluate执行掷骰和检定
5. 根据结果判断是否有状态变更：
   - 攻击命中且有伤害 → 计算新HP，生成 MOD 指令
   - 攻击未命中 → 不生成变更指令
   - 施法成功 → 根据效果生成相应指令
6. 使用write工具执行变更
7. 输出JSON格式的执行结果

重要:
- 所有数值计算必须通过evaluate工具
- **关键**: 如果没有状态变更（如攻击未命中），changes数组为空，不要调用write
- **关键**: 只能修改已存在的key（MOD操作），不要创建新的key
- new_value必须是完整的自然语言段落（参考原状态格式）

输出要求（JSON格式）:
```json
{
    "success": true/false,
    "narration": "执行过程的自然语言描述，包括掷骰结果、命中/未命中、伤害等",
    "changes": [
        {
            "operation": "MOD",
            "path": "Goblin.combat",
            "old_value": "HP: 10/10 | AC: 15...",
            "new_value": "HP: 5/10 | AC: 15..."
        }
    ]
}
```

注意:
- 如果没有状态变更，changes为空数组: []
- old_value和new_value必须是完整的自然语言段落
- operation只能是: MOD(修改已存在key), ADD(添加新key), DEL(删除key)
"""

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None, base_url: str | None = None, tools: list[BaseTool] | None = None):
        self.tools = {t.name: t for t in (tools or [])}

        kwargs = {"model": model, "temperature": 0, "api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.llm = ChatOpenAI(**kwargs)
        if tools:
            self.llm_with_tools = self.llm.bind_tools(tools)
        else:
            self.llm_with_tools = self.llm

    def execute(self, task: PlannedTask) -> ExecutionResult:
        """
        执行PlannedTask

        使用ReAct模式:
        1. 调用LLM生成tool calls
        2. 执行tools计算和写入
        3. 返回执行结果
        """
        print(f"\n⚡ ExecutorAgent: 执行任务 - {task.description}")

        # 构建对话历史
        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=f"""请执行以下任务:

任务ID: {task.task_id}
任务描述: {task.description}
行动者: {task.actor}
目标: {task.target}
动作: {task.action}

任务详情:
{task.context.get('raw_description', '无详细描述')}

工作流程：
1. 使用fetch_keys查看可用key，使用read读取相关状态
2. 使用evaluate执行掷骰和计算
3. 根据结果生成JSON格式的变更指令
4. 使用write工具执行状态变更
5. 输出JSON格式的执行结果

重要：
- 攻击未命中时changes设为空数组，不调用write
- 只能修改已存在的key
- new_value必须是完整的自然语言段落
- 输出必须是JSON格式，包含success, narration, changes字段
""")
        ]

        # ReAct循环
        max_iterations = 10
        tool_results = []

        for i in range(max_iterations):
            # 调用LLM
            response = self.llm_with_tools.invoke(messages)
            messages.append(response)

            # 检查是否有工具调用
            if not response.tool_calls:
                # LLM已输出最终结果
                break

            # 执行工具调用
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call["id"]

                print(f"   🔧 调用工具: {tool_name}({tool_args})")

                if tool_name in self.tools:
                    try:
                        result = self.tools[tool_name].invoke(tool_args)
                    except Exception as e:
                        result = f"错误: {e}"
                else:
                    result = f"错误: 未知工具 {tool_name}"

                # 截断结果避免过长
                if len(str(result)) > 1000:
                    result = str(result)[:1000] + "\n... [截断]"

                tool_results.append((tool_name, result))
                messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))

        # 如果达到最大迭代次数但仍没有最终结果，强制要求输出
        if i >= max_iterations - 1 and response.tool_calls:
            messages.append(HumanMessage(content='请直接输出JSON格式的执行结果，格式为 {"success": true/false, "narration": "...", "changes": [...]}，不要继续调用工具。'))
            response = self.llm_with_tools.invoke(messages)
            messages.append(response)

        # 解析最终输出
        # 找到最后一个 AIMessage（不是 ToolMessage）
        final_message = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content and msg.content.strip():
                final_message = msg
                break

        if final_message:
            print(f"   📩 LLM输出: {final_message.content[:200]}...")
            return self._parse_execution_result(final_message.content, task, tool_results)
        else:
            raise RuntimeError("ExecutorAgent failed to generate a valid result - no AI message found")

    def _parse_execution_result(self, content: str, task: PlannedTask, tool_results: list) -> ExecutionResult:
        """解析JSON输出为ExecutionResult"""
        try:
            print(f"   🔍 解析执行结果...")

            # 清理markdown代码块
            cleaned = content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            # 找到JSON部分
            json_start = cleaned.find("{")
            json_end = cleaned.rfind("}")
            if json_start >= 0 and json_end > json_start:
                cleaned = cleaned[json_start:json_end+1]
            else:
                raise ValueError(f"No JSON object found in content: {cleaned[:200]}")

            data = json.loads(cleaned)

            # 解析changes
            changes = []
            for c in data.get("changes", []):
                changes.append(StateChange(
                    path=c.get("path", c.get("key", "")),
                    old_value=c.get("old_value"),
                    new_value=c.get("new_value"),
                    operation=c.get("operation", "MOD")
                ))

            result = ExecutionResult(
                task_id=task.task_id,
                success=data.get("success", True),
                changes=changes,
                narration=data.get("narration", "执行完成")
            )

            print(f"   ✅ 执行结果: {result.narration[:100]}...")
            print(f"      变更: {len(result.changes)} 项")

            return result

        except Exception as e:
            print(f"   ⚠️ 解析执行结果时出错: {e}")
            print(f"   ⚠️ 原始内容: {content[:500]}")
            # 返回基本结果
            return ExecutionResult(
                task_id=task.task_id,
                success=True,
                changes=[],
                narration=content[:500] if content else "执行完成"
            )
