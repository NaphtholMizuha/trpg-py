"""
PlannerAgent - 规划Agent

合并意图识别 + RAG检索 + 任务生成
使用ReAct模式，通过tools决定如何执行
"""
import uuid
import json
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool

from ..types import PlannedTask


class PlannerAgent:
    """
    PlannerAgent - 规划Agent

    职责:
    1. 分析玩家输入的自然语言指令
    2. 使用fetch_keys查看所有可用的KV记忆key
    3. 使用read工具查询感兴趣的key的value
    4. 使用search工具(RAG)查询D&D规则(英文)
    5. 生成自然语言任务描述，放入任务队列

    优先级策略: KV记忆 > RAG获取的内容 > 模型自身知识
    """

    SYSTEM_PROMPT = """你是D&D 5e的PlannerAgent，负责将DM的自然语言指令转换为结构化的任务计划。

你的职责:
1. 分析玩家/DM的自然语言指令
2. 使用工具查询需要的信息（状态、规则）
3. 生成自然语言任务描述，供Executor执行

可用工具:
- fetch_keys: 获取所有KV状态的key列表
- read: 读取指定key(s)的值
- search: RAG检索D&D 5e规则文档

优先级策略(严格遵守):
1. KV记忆 > RAG获取的内容 > 模型自身知识
2. 不确定数值时，优先使用read工具查询状态
3. 不确定规则时，使用search工具查询
4. 如果仍然无法确定，在任务描述中标注"[需要确认]"

工作流程:
1. 先用fetch_keys查看所有可用的key
2. 用read读取相关角色/对象的状态
3. 用search查询相关D&D规则(英文)
4. 用自然语言生成任务描述，包含所有执行需要的信息

输出要求（自然语言格式）:
```
任务ID: task_xxx（或让系统自动生成）
任务描述: [简洁描述，如"艾尔德拉使用+1长剑攻击地精"]
行动者: [角色名]
目标: [目标名，可选]
动作: [攻击/施法/移动等]

执行所需信息:
- 行动者状态: [KV key，如 Aldera.combat]
- 目标状态: [KV key，如 Goblin.combat]
- 相关数值: [攻击加值、AC、伤害骰等，从状态中读取到的]
- 规则参考: [查询到的D&D规则要点]

执行说明: [具体的执行要求，如"进行攻击检定，命中后造成1d8+4挥砍伤害"]
```

重要:
- 使用自然语言描述，不要输出JSON
- 提供足够的上下文让Executor理解如何执行
- 明确指出需要读取哪些KV key
- 如果信息不完整，在描述中标注"[需要确认]"
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

    def plan(self, user_input: str) -> PlannedTask:
        """
        将用户输入转换为PlannedTask（自然语言版本）

        使用ReAct模式:
        1. 调用LLM生成tool calls
        2. 执行tools获取信息
        3. LLM输出自然语言任务描述
        """
        print(f"\n🧠 PlannerAgent: 分析指令 - {user_input}")

        # 构建对话历史
        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=f"""DM指令: {user_input}

请分析并生成自然语言任务描述。

工作流程：
1. 使用工具查询需要的信息（fetch_keys/read/search）
2. 整合信息后，输出自然语言格式的任务描述

请开始分析。""")
        ]

        # ReAct循环
        max_iterations = 10
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
                if len(str(result)) > 2000:
                    result = str(result)[:2000] + "\n... [截断]"

                messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))

        # 如果达到最大迭代次数但仍没有最终结果，强制要求输出
        if i >= max_iterations - 1:
            messages.append(HumanMessage(content="请直接输出自然语言任务描述，不要继续调用工具。"))
            response = self.llm_with_tools.invoke(messages)
            messages.append(response)

        # 解析最终输出
        final_message = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content and msg.content.strip():
                final_message = msg
                break

        if final_message:
            print(f"   📩 LLM输出:\n{final_message.content[:500]}...")
            return self._parse_planned_task_natural(final_message.content, user_input)
        else:
            raise RuntimeError("PlannerAgent failed to generate a valid task - no AI message found")

    def _parse_planned_task_natural(self, content: str, original_input: str) -> PlannedTask:
        """解析自然语言输出为PlannedTask"""
        try:
            print(f"   🔍 解析自然语言任务...")

            # 清理markdown代码块
            cleaned = content.strip()
            if cleaned.startswith("```"):
                # 找到代码块结束位置
                end_idx = cleaned.find("```", 3)
                if end_idx > 0:
                    cleaned = cleaned[3:end_idx].strip()

            # 提取关键信息
            lines = cleaned.split('\n')
            task_id = f"task_{uuid.uuid4().hex[:8]}"
            description = original_input
            actor = "未知"
            target = None
            action = ""
            context = {"raw_description": cleaned}

            for line in lines:
                line = line.strip()
                if line.startswith("任务ID:") or line.startswith("任务编号:"):
                    task_id = line.split(":", 1)[1].strip()
                elif line.startswith("任务描述:") or line.startswith("描述:"):
                    description = line.split(":", 1)[1].strip()
                elif line.startswith("行动者:") or line.startswith("执行者:"):
                    actor = line.split(":", 1)[1].strip()
                elif line.startswith("目标:"):
                    target = line.split(":", 1)[1].strip()
                elif line.startswith("动作:"):
                    action = line.split(":", 1)[1].strip()
                elif line.startswith("- 行动者状态:") or line.startswith("- 目标状态:"):
                    key = line.split(":", 1)[1].strip().split()[0]
                    if "actor_key" not in context:
                        context["actor_key"] = key
                    else:
                        context["target_key"] = key

            # 如果没有提取到描述，使用原始输入的前缀
            if description == original_input and len(lines) > 0:
                # 取第一行非空且不是字段定义的行作为描述
                for line in lines:
                    line_stripped = line.strip()
                    if line_stripped and not line_stripped.startswith(("任务", "行动者", "目标", "动作", "执行", "- ", "* ")):
                        description = line_stripped
                        break

            task = PlannedTask(
                task_id=task_id,
                natural_description=description,
                actor=actor,
                target=target,
                action=action,
                context=context,
                source="dm"
            )

            print(f"   ✅ 生成任务: {task.natural_description}")
            print(f"      行动者: {task.actor}, 目标: {task.target}, 动作: {task.action}")

            return task

        except Exception as e:
            print(f"   ❌ 解析失败: {e}")
            print(f"   ❌ 原始内容: {content[:500]}")
            # 失败时使用原始输入创建基本任务
            return PlannedTask(
                task_id=f"task_{uuid.uuid4().hex[:8]}",
                natural_description=original_input,
                actor="未知",
                context={"raw_description": content},
                source="dm"
            )
