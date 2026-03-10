"""
ChainAgent - 连锁Agent，检测状态变更触发的连锁反应

V3增强版: 支持Tools，增加DM审批机制
"""
import json
import uuid
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool

from ..types import StateChange, ChainTrigger, PlannedTask


class ChainAgent:
    """
    ChainAgent - 连锁Agent (V3增强版)

    职责:
    1. 检查本轮的修改记录
    2. 使用read工具获取相关状态
    3. 使用search工具查询连锁相关规则（如死亡规则、爆炸规则等）
    4. 生成自然语言的连锁触发效果
    5. **置入任务队列前需要DM审批**（关键新增）

    DM审批机制:
    - ChainAgent生成连锁任务但不直接放入队列
    - 设置pending_chain_tasks等待DM确认
    - DM确认后才真正加入task_queue
    """

    SYSTEM_PROMPT = """你是D&D 5e的ChainAgent，负责检测状态变更触发的连锁反应。

你的职责:
1. 分析本轮的状态变更记录
2. 使用fetch_keys和read工具读取当前状态
3. 使用search查询连锁相关规则
4. 输出自然语言连锁检测结果

可用工具:
- fetch_keys: 获取所有KV状态的key列表
- read: 读取当前状态验证连锁条件
- search: RAG查询连锁相关规则（如死亡、爆炸、法术效果等）

连锁检测清单:
1. HP归零 → 死亡/昏迷
2. 火药桶点燃 → 爆炸
3. 法术效果触发 → 持续伤害/状态
4. 环境互动 → 连锁反应

输出要求（自然语言格式）:
```
连锁检测结果:

触发器列表:
[如果没有触发器] 无连锁反应
[如果有触发器]
1. [优先级] [条件描述]
   效果: [连锁效果描述]
   来源: [触发的key]

2. ...

连锁任务（待DM审批）:
[如果没有] 无
[如果有]
- 任务ID: [自动生成]
  描述: [任务描述]
  行动者: [触发者]
  目标: [影响目标]
  动作: [连锁动作]
  建议操作: [具体执行建议]
```

重要:
- 使用自然语言描述，不要输出JSON
- 生成的连锁任务不会立即执行，需要DM审批
- 如果不确定是否触发连锁，标注"[需要DM确认]"
- 只能引用已存在的KV key
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

    def check_chains(self, changes: list[StateChange], state_text: str) -> tuple[list[ChainTrigger], list[PlannedTask]]:
        """
        检查连锁反应

        返回:
            (triggers, pending_tasks)
            - triggers: 连锁触发器列表
            - pending_tasks: 待审批的连锁任务
        """
        print(f"\n🔗 ChainAgent: 检测连锁反应...")

        # 构建变更描述
        changes_json = json.dumps([
            {
                "path": c.path,
                "old_value": str(c.old_value)[:100] if c.old_value else None,
                "new_value": str(c.new_value)[:100] if c.new_value else None,
                "operation": c.operation
            }
            for c in changes[-5:]  # 最近5个变更
        ], ensure_ascii=False, indent=2)

        # 构建对话历史
        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=f"""状态变更记录:
{changes_json}

当前状态:
{state_text[:1000]}

请检测连锁反应。

工作流程：
1. 使用工具查询需要的信息（read/search）
2. 分析状态变更是否触发连锁
3. 输出JSON格式的结果

重要：
- 完成工具查询后，必须直接输出JSON，不要输出思考过程或解释
- 如果没有连锁反应，输出: {{"triggers": [], "chain_tasks": []}}
""")
        ]

        # ReAct循环
        max_iterations = 5
        for i in range(max_iterations):
            response = self.llm_with_tools.invoke(messages)
            messages.append(response)

            if not response.tool_calls:
                break

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

                messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))

        # 如果达到最大迭代次数但仍没有最终结果，强制要求输出
        if i >= max_iterations - 1 and response.tool_calls:
            messages.append(HumanMessage(content='请直接输出JSON格式的连锁检测结果，格式为 {"triggers": [], "chain_tasks": []}，不要继续调用工具。'))
            response = self.llm_with_tools.invoke(messages)
            messages.append(response)

        # 解析结果
        # 找到最后一个 AIMessage（不是 ToolMessage）
        final_message = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content and msg.content.strip():
                final_message = msg
                break

        if final_message:
            print(f"   📩 LLM输出: {final_message.content[:200]}...")
            return self._parse_chain_result(final_message.content, changes)
        else:
            raise RuntimeError("ChainAgent failed to generate a valid result - no AI message found")

    def _parse_chain_result(self, content: str, changes: list[StateChange]) -> tuple[list[ChainTrigger], list[PlannedTask]]:
        """解析自然语言输出"""
        try:
            print(f"   🔍 解析自然语言连锁结果...")

            # 清理markdown代码块
            cleaned = content.strip()
            if cleaned.startswith("```"):
                end_idx = cleaned.find("```", 3)
                if end_idx > 0:
                    cleaned = cleaned[3:end_idx].strip()

            triggers = []
            tasks = []

            # 检查是否有"无连锁反应"或空触发器
            if "无连锁" in cleaned or "无" in cleaned[:50]:
                return triggers, tasks

            # 解析触发器（简单启发式）
            lines = cleaned.split('\n')
            current_trigger = None
            in_task_section = False

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # 检测触发器列表开始
                if "触发器列表:" in line or "检测到的连锁:" in line:
                    continue

                # 检测任务部分
                if "连锁任务" in line or "待DM审批" in line:
                    in_task_section = True
                    continue

                # 解析触发器 (格式: "1. [优先级] 条件")
                if line[0].isdigit() and "." in line[:3] and not in_task_section:
                    # 提取优先级和条件
                    parts = line.split(".", 1)[1].strip().split("]", 1)
                    if len(parts) >= 2:
                        priority_str = parts[0].replace("[", "").strip()
                        try:
                            priority = int(priority_str) if priority_str.isdigit() else 1
                        except:
                            priority = 1
                        condition = parts[1].strip()
                    else:
                        priority = 1
                        condition = line.split(".", 1)[1].strip()

                    current_trigger = {
                        "priority": priority,
                        "condition": condition,
                        "effect": "",
                        "source_path": changes[-1].path if changes else ""
                    }

                # 解析效果行
                elif line.startswith("效果:") and current_trigger:
                    current_trigger["effect"] = line.split(":", 1)[1].strip()

                # 解析来源行
                elif line.startswith("来源:") and current_trigger:
                    current_trigger["source_path"] = line.split(":", 1)[1].strip()

                # 完成一个触发器
                elif current_trigger and not line.startswith("-") and not line.startswith("效果") and not line.startswith("来源"):
                    if current_trigger["condition"]:
                        triggers.append(ChainTrigger(**current_trigger))
                    current_trigger = None

                # 解析任务 (格式: "- 任务ID: xxx")
                elif in_task_section and line.startswith("-") and "任务ID:" in line:
                    # 简单提取任务信息
                    task_desc = line.replace("-", "").strip()
                    tasks.append(PlannedTask(
                        task_id=f"chain_{uuid.uuid4().hex[:8]}",
                        description=task_desc,
                        actor="系统",
                        action="连锁反应"
                    ))

            # 处理最后一个触发器
            if current_trigger and current_trigger["condition"]:
                triggers.append(ChainTrigger(**current_trigger))

            if triggers:
                print(f"   ⚠️ 发现 {len(triggers)} 个连锁触发:")
                for t in triggers:
                    print(f"      [{t.priority}] {t.condition}")
                    print(f"      → {t.effect}")

            return triggers, tasks

        except Exception as e:
            print(f"   ⚠️ 解析连锁结果时出错: {e}，返回空结果")
            return [], []
