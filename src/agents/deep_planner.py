"""
DeepPlannerAgent - 深度规划Agent

支持多 skill 的灵活规划，LLM 自主决定如何组合使用 skills。
保留 ReAct 工具调用能力，输出统一的 PlannedTask。
"""
import uuid
import re
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import BaseTool

from ..types import PlannedTask, DecisionPoint, normalize_decision_timing
from ..utils.logging import get_logger
from ..skills import get_registry, Skill
from .base import BaseAgent

logger = get_logger(__name__)

# 读取 prompt 文件
_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"
TASK_TEMPLATE = (_PROMPT_DIR / "planner_task.md").read_text(encoding="utf-8")
FORCE_OUTPUT_PROMPT = (_PROMPT_DIR / "force_output" / "planner.txt").read_text(encoding="utf-8")


class DeepPlannerAgent(BaseAgent):
    """
    Deep Planner Agent - 支持多 skill 的灵活规划

    职责:
    1. 加载多个 skills，组合为系统提示词
    2. 使用 ReAct 模式，LLM 自主决定如何组合使用 skills
    3. 调用工具获取信息 (fetch_keys/read/search)
    4. 生成自然语言任务描述，放入任务队列

    与 PlannerAgent 的区别:
    - 不通过意图识别选择单个 skill
    - 同时加载所有 skills，由 LLM 自主决定使用哪些
    - 更灵活，支持复杂场景的组合 skill 使用
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
        tools: list[BaseTool] | None = None,
        skills: list[Skill] | None = None,
    ):
        super().__init__(model, api_key, base_url, tools, max_iterations=10)
        self.skills = skills or []
        self._logger = get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    def get_system_prompt(self) -> str:
        """
        组合所有 skill 内容为系统提示词
        """
        base_prompt = """你是 TRPG 规划助手，负责分析 DM 的指令并生成执行任务。

你的职责:
1. 分析 DM 的自然语言指令，理解行动类型、角色、目标
2. 使用工具查询必要的游戏状态信息（角色属性、怪物状态、规则等）
3. 根据指令类型，选择合适的处理方式:
   - 标准游戏流程（攻击、施法、检定等）→ 生成结构化任务描述
   - 世界编辑指令（set/create/delete等）→ 生成字段变更指令
4. 预判可能的连锁反应和角色反应机会

重要提示:
- 你可以自主决定使用哪些 skill 的内容来处理指令
- 对于复杂场景，可以组合使用多个 skill 的规则
- 所有数值必须标注来源（KV/RAG/确认）
- 不确定的信息标记为 [Needs Confirmation]
- 调用 search 工具时，默认优先使用中文查询；只有需要补充别名时才附带英文原名
"""

        if not self.skills:
            return base_prompt

        skills_content = "\n\n" + "=" * 50 + "\n\n".join([
            f"## Skill: {s.name}\n{s.content}"
            for s in self.skills
        ])

        return f"{base_prompt}\n\n## 可用的 Skills\n{skills_content}"

    def plan(self, user_input: str) -> list[PlannedTask]:
        """
        将用户输入转换为 PlannedTask 列表

        使用 ReAct 模式:
        1. 调用 LLM 生成 tool calls 查询信息
        2. 执行 tools 获取数据
        3. LLM 输出任务描述

        LLM 自主决定:
        - 需要查询哪些信息
        - 需要应用哪些 skill 的规则
        - 最终生成 PlannedTask 列表

        如果检测到潜在决策窗口，会将其附着在主任务上，
        由工作流在执行前统一处理。
        """
        self._logger.info("DeepPlannerAgent 分析指令", user_input=user_input)

        # 检测指令类型，选择不同的任务模板
        intent_type = self._detect_intent_type(user_input)

        if intent_type == "world_edit":
            task_prompt = f"""DM世界编辑指令: {user_input}

这是一个直接的世界状态修改指令，不需要骰子检定。
请解析为结构化的字段变更指令，输出JSON格式。

注意：
1. 跳过所有攻击检定、豁免等机械流程
2. 直接生成MOD/ADD/DEL操作
3. 标注dm_override标志

请使用 world_edit skill 的规则来处理此指令。"""
        else:
            # 标准游戏流程
            task_prompt = TASK_TEMPLATE.format(user_input=user_input)

        # 构建对话历史
        messages = [
            SystemMessage(content=self.get_system_prompt()),
            HumanMessage(content=task_prompt)
        ]

        # 使用基类的 ReAct 循环
        final_message = self._react_loop(
            messages,
            force_output_prompt=FORCE_OUTPUT_PROMPT
        )

        content_str = ""
        if isinstance(final_message.content, str):
            content_str = final_message.content
        elif isinstance(final_message.content, list):
            content_str = "\n".join(str(item) for item in final_message.content)

        self._logger.info("LLM 输出", content=content_str[:200] if content_str else "None")

        return self._parse_planned_task(content_str, user_input)

    def _detect_intent_type(self, user_input: str) -> str:
        """
        简单意图检测，用于选择任务模板

        Returns:
            "standard" | "world_edit"
        """
        user_lower = user_input.lower()

        # world_edit 关键词
        world_edit_keywords = [
            "set", "create", "delete", "modify", "update", "add", "remove",
            "spawn", "kill", "heal to", "set hp", "to full", "to max", "max hp",
            "设置", "创建", "删除", "修改", "更新", "添加", "移除", "生成",
            "杀死", "治疗到", "回满", "满血", "满状态", "设置生命", "直接", "立即",
            "world edit", "dm override"
        ]

        for keyword in world_edit_keywords:
            if keyword.lower() in user_lower:
                return "world_edit"

        # 连锁任务标记
        if user_input.startswith("【连锁:"):
            # 根据连锁类型判断
            if "death" in user_lower:
                return "standard"  # 死亡连锁使用标准流程
            return "standard"

        return "standard"

    def _parse_planned_task(self, content: str, original_input: str) -> list[PlannedTask]:
        """
        解析 LLM 输出为 PlannedTask 列表

        支持两种格式:
        1. 标准任务格式 (=== Task Metadata ===)
        2. JSON 格式 (世界编辑指令)

        如果检测到潜在决策窗口，会将其附着在主任务上。
        """
        content_stripped = content.strip() if content else ""

        # 移除 <think> 标签及其内容（某些模型的 CoT 输出）
        if "<think>" in content_stripped:
            content_stripped = re.sub(r'<think>.*?</think>', '', content_stripped, flags=re.DOTALL).strip()

        # 检测是否为 JSON 格式（世界编辑）
        # 直接 JSON 或以 ```json 开头的代码块
        if content_stripped.startswith("{") or content_stripped.startswith("```"):
            return self._parse_world_edit_task(content_stripped, original_input)

        # 标准格式解析
        return self._parse_standard_task(content_stripped, original_input)

    def _parse_world_edit_task(self, content: str, original_input: str) -> list[PlannedTask]:
        """解析世界编辑 JSON 格式为 PlannedTask 列表"""
        import json

        try:
            # 清理 markdown 代码块
            cleaned = content
            if cleaned.startswith("```"):
                end_idx = cleaned.find("```", 3)
                if end_idx > 0:
                    cleaned = cleaned[3:end_idx].strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()

            data = json.loads(cleaned)

            operation_type = data.get("operation_type", "UNKNOWN")
            description = data.get("description", original_input)
            target_entity = data.get("target_entity", {})

            # 构建任务描述
            task_id = f"task_{uuid.uuid4().hex[:8]}"

            # 构建上下文（包含完整 JSON 供 Executor 解析）
            context = f"""世界编辑指令
操作类型: {operation_type}
目标实体: {target_entity.get('name', 'Unknown')}
类型: {target_entity.get('type', 'Unknown')}

完整指令:
{cleaned}
"""

            task = PlannedTask(
                task_id=task_id,
                description=description,
                context=context,
                actor="DM",
                target=target_entity.get("name"),
                source="dm",
                decision_points=[],
                task_category="world_edit"
            )

            self._logger.info(
                "生成世界编辑任务",
                task_id=task.task_id,
                operation=operation_type,
                description=task.description
            )

            return [task]

        except Exception as e:
            self._logger.error("解析世界编辑任务失败", error=str(e), content=content[:500])
            # 回退到标准格式
            return self._parse_standard_task(content, original_input)

    def _parse_standard_task(self, content: str, original_input: str) -> list[PlannedTask]:
        """解析标准任务格式为 PlannedTask 列表

        如果检测到潜在决策窗口，会将其附着在主任务上。
        """
        try:
            logger.info("解析标准任务")

            # 清理 markdown 代码块
            cleaned = content.strip() if content else ""
            if cleaned.startswith("```"):
                end_idx = cleaned.find("```", 3)
                if end_idx > 0:
                    cleaned = cleaned[3:end_idx].strip()

            # 找到 === Task Metadata === 部分开始的位置
            # 忽略之前的 CoT 内容
            metadata_start = cleaned.find("=== Task Metadata ===")
            if metadata_start >= 0:
                parse_content = cleaned[metadata_start:]
            else:
                parse_content = cleaned

            # 提取关键信息
            lines = parse_content.split('\n')
            task_id = f"task_{uuid.uuid4().hex[:8]}"
            description = original_input  # 默认使用原始输入
            actor = "未知"
            target = None
            decision_points: list[DecisionPoint] = []

            in_decision_section = False
            for line in lines:
                line = line.strip()

                if "可能出现的决策点" in line and "===" in line:
                    in_decision_section = True
                    continue
                if in_decision_section and line.startswith("==="):
                    in_decision_section = False
                    continue

                # 解析决策点条目
                if in_decision_section and line.startswith("- [条件:"):
                    point = self._parse_decision_point_line(line)
                    if point:
                        decision_points.append(point)

                # 提取基本信息（只在 Task Metadata 部分中查找）
                if line.startswith("任务ID:") or line.startswith("Task ID:") or line.startswith("任务编号:"):
                    task_id = line.split(":", 1)[1].strip()
                elif line.startswith("任务描述:") or line.startswith("Task Description:") or line.startswith("描述:"):
                    desc_value = line.split(":", 1)[1].strip()
                    if desc_value and desc_value != original_input:
                        description = desc_value
                elif line.startswith("行动者:") or line.startswith("Actor:") or line.startswith("执行者:"):
                    actor = line.split(":", 1)[1].strip()
                elif line.startswith("目标:") or line.startswith("Target:"):
                    target = line.split(":", 1)[1].strip()

            # 安全检查：如果描述为空或包含 <think>，使用原始输入
            if not description or "<think>" in description or "现在我已经收集" in description:
                description = original_input

            decision_points = self._normalize_decision_points(decision_points, actor)

            # 创建主任务
            main_task = PlannedTask(
                task_id=task_id,
                description=description,
                context=cleaned,
                actor=actor,
                target=target,
                source="dm",
                decision_points=decision_points,
                task_category="normal",
                task_status="pending"
            )

            if decision_points:
                logger.info(
                    "生成任务（含决策点）",
                    task_id=main_task.task_id,
                    description=main_task.description,
                    actor=main_task.actor,
                    target=main_task.target,
                    decision_point_count=len(decision_points)
                )
            else:
                logger.info(
                    "生成任务",
                    task_id=main_task.task_id,
                    description=main_task.description,
                    actor=main_task.actor,
                    target=main_task.target
                )

            return [main_task]

            logger.info(
                "生成任务",
                task_id=main_task.task_id,
                description=main_task.description,
                actor=main_task.actor,
                target=main_task.target,
                reaction_count=0
            )

            return [main_task]

        except Exception as e:
            logger.error("解析失败", error=str(e), content=content[:500] if content else "None")
            # 失败时使用原始输入创建基本任务
            fallback_task = PlannedTask(
                task_id=f"task_{uuid.uuid4().hex[:8]}",
                description=original_input,
                context=content if content else "",
                actor="未知",
                source="dm",
                task_category="normal",
                task_status="pending",
                decision_points=[]
            )
            return [fallback_task]

    def _normalize_decision_points(
        self,
        decision_points: list[DecisionPoint],
        main_actor: str,
    ) -> list[DecisionPoint]:
        """规范化决策点，避免把嵌套响应的结果提前写死在主任务里。"""
        normalized: list[DecisionPoint] = []
        nested_points: list[DecisionPoint] = []

        for point in decision_points:
            cleaned_description = self._strip_pre_resolved_nested_outcome(point.description)
            cleaned_condition = self._strip_pre_resolved_nested_outcome(point.condition)

            normalized.append(
                DecisionPoint(
                    condition=cleaned_condition,
                    decider=point.decider,
                    description=cleaned_description,
                    timing=point.timing,
                    option_name=point.option_name,
                    metadata=dict(point.metadata),
                )
            )

            nested = self._maybe_create_nested_counterspell_point(point, main_actor)
            if nested is not None:
                nested_points.append(nested)

        return normalized + nested_points

    def _strip_pre_resolved_nested_outcome(self, text: str) -> str:
        """移除“会被法术反制打断”这类提前写死的嵌套结果。"""
        if not text:
            return text

        cleaned = text
        patterns = [
            r"[，,；;]?但会被[^。；;，,]*法术反制[^。；;，,]*",
            r"[，,；;]?并会被[^。；;，,]*法术反制[^。；;，,]*",
            r"[，,；;]?可被[^。；;，,]*法术反制[^。；;，,]*",
        ]
        for pattern in patterns:
            cleaned = re.sub(pattern, "", cleaned)
        return cleaned.strip("，,；;。 ")

    def _maybe_create_nested_counterspell_point(
        self,
        point: DecisionPoint,
        main_actor: str,
    ) -> DecisionPoint | None:
        """若主决策点里提前出现“法术反制会打断”的叙述，则转成真正的嵌套决策点。"""
        haystack = f"{point.condition} {point.description}"
        if "法术反制" not in haystack:
            return None
        if point.option_name != "护盾术":
            return None

        return DecisionPoint(
            condition=f"{point.decider}选择施放护盾术",
            decider=main_actor,
            description=f"可在{point.decider}开始施放护盾术时，以法术反制尝试打断该响应动作",
            timing=normalize_decision_timing("before_action"),
            option_name="法术反制",
            metadata={"interrupts_option": "护盾术"},
        )

    def _parse_decision_point_line(self, line: str) -> DecisionPoint | None:
        """解析决策点条目行

        格式:
        - [条件: ...] [角色: ...] [时机: ...] [选项: ...] 描述
        """
        try:
            # 移除开头的 "- "
            line = line[2:].strip() if line.startswith("- ") else line.strip()

            # 解析各部分
            condition = ""
            decider = ""
            option_name = None
            description = ""
            timing = "before_resolution"

            # 提取各部分
            condition_match = re.search(r'\[条件:\s*([^\]]+)\]', line)
            actor_match = re.search(r'\[(?:角色|决策者):\s*([^\]]+)\]', line)
            timing_match = re.search(r'\[(?:时机|timing):\s*([^\]]+)\]', line, flags=re.IGNORECASE)
            option_match = re.search(r'\[(?:选项|动作|能力):\s*([^\]]+)\]', line)

            if condition_match:
                condition = condition_match.group(1).strip()
            if actor_match:
                decider = actor_match.group(1).strip()
            if timing_match:
                timing = normalize_decision_timing(timing_match.group(1).strip())
            if option_match:
                option_name = option_match.group(1).strip()

            # 描述是最后一个 ] 之后的内容
            last_bracket = line.rfind(']')
            if last_bracket > 0:
                description = line[last_bracket + 1:].strip()

            # 如果条件是无，则返回 None
            if condition == "无":
                return None

            return DecisionPoint(
                condition=condition,
                decider=decider,
                description=description,
                timing=normalize_decision_timing(timing),
                option_name=option_name
            )

        except Exception as e:
            logger.warning("解析决策点条目失败", line=line[:100], error=str(e))
            return None


# 工厂函数，用于从配置创建 DeepPlannerAgent
def create_deep_planner_agent(
    model: str,
    api_key: str | None,
    base_url: str | None,
    tools: list[BaseTool],
    skill_names: list[str] | None = None
) -> DeepPlannerAgent:
    """
    创建 DeepPlannerAgent 的工厂函数

    Args:
        model: LLM 模型名称
        api_key: API 密钥
        base_url: API 基础 URL
        tools: 可用工具列表
        skill_names: 要加载的 skill 名称列表，None 表示加载所有

    Returns:
        DeepPlannerAgent 实例
    """
    registry = get_registry()

    if skill_names is None:
        # 加载所有 skills
        all_skills = registry.get_all_skills()
        skills = list(all_skills.values())
    else:
        # 加载指定的 skills
        skills = []
        for name in skill_names:
            skill = registry.get_skill(name)
            if skill:
                skills.append(skill)

    return DeepPlannerAgent(
        model=model,
        api_key=api_key,
        base_url=base_url,
        tools=tools,
        skills=skills
    )
