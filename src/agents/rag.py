"""
RagAgent - 规则检索Agent，负责理解任务并检索D&D 5e规则
"""
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from ..types import TaskIntent


class RagAgent:
    """
    RagAgent - 规则检索Agent
    
    职责：
    1. 理解任务意图
    2. 将中文任务翻译成最佳英文查询
    3. 检索D&D 5e SRD规则
    4. 返回规则文本供TaskAgent使用
    """
    
    def __init__(self, model: str = "gpt-4o", api_key: str | None = None, base_url: str | None = None, retriever=None):
        self.use_llm = api_key is not None
        self.retriever = retriever
        
        if self.use_llm:
            kwargs = {"model": model, "temperature": 0, "api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.llm = ChatOpenAI(**kwargs)
        else:
            self.llm = None
    
    def retrieve(self, task: TaskIntent) -> str:
        """
        根据任务检索相关规则
        
        Args:
            task: 任务意图
            
        Returns:
            检索到的规则文本（已格式化）
        """
        if not self.use_llm or not self.retriever:
            return "[RAG未配置，使用默认规则]"
        
        # 使用LLM将任务翻译成最佳英文查询
        english_query = self._translate_query(task)
        print(f"   🔍 RagAgent: 查询 '{english_query}'")
        
        # 执行检索
        results = self.retriever.search(english_query, limit=3)
        
        if not results:
            return "未找到相关规则"
        
        # 格式化结果
        formatted = self._format_results(results, english_query)
        print(f"   📚 RagAgent: 获取 {len(results)} 条规则")
        
        return formatted
    
    def _translate_query(self, task: TaskIntent) -> str:
        """
        使用LLM将任务翻译成英文自然语言描述
        
        用自然语言而非关键词进行检索，语义效果更好：
        - "艾尔德拉用长剑攻击地精" → "Eldara attacks the goblin with a longsword"
        - "地精试图逃跑" → "The goblin tries to disengage and move away"
        """
        system_prompt = """你是一个D&D 5e规则查询助手。

将用户的任务描述翻译成简洁的英文自然语言描述，用于语义检索D&D 5e规则。

翻译原则：
1. 保留核心动作和机制（attack, spell, saving throw等）
2. 保留角色和对象信息（谁对谁做什么）
3. 用简洁的自然语言，不要关键词堆砌
4. 输出应该是一个完整的短句或短语

示例：
- "艾尔德拉用长剑攻击地精" → "Player attacks goblin with longsword melee weapon"
- "施放火球术" → "Casting fireball spell area damage"
- "尝试擒抱敌人" → "Attempting to grapple an enemy"
- "地精进行敏捷豁免" → "Goblin makes dexterity saving throw"
- "点燃火药桶" → "Igniting explosive barrel with fire damage"

只输出英文描述，不要解释。"""

        prompt = f"""任务描述：{task.description}
任务类型：{task.task_type.value}
行动者：{task.actor}
目标：{task.target}
动作：{task.action}

翻译成英文描述："""

        try:
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ])
            
            query = response.content.strip()
            # 移除可能的引号
            query = query.strip('"\'')
            return query
            
        except Exception as e:
            # 回退：使用简单的代码映射
            print(f"   ⚠️ LLM翻译失败: {e}，使用简单映射")
            return self._fallback_translate(task)
    
    def _fallback_translate(self, task: TaskIntent) -> str:
        """简单的回退翻译（自然语言）"""
        parts = []
        
        # 行动者
        if task.actor:
            parts.append(task.actor)
        
        # 动作
        if task.task_type.value == "attack":
            parts.append("attacks")
        elif task.task_type.value == "spell":
            parts.append("casts spell")
        elif task.task_type.value == "saving_throw":
            parts.append("makes saving throw")
        else:
            parts.append("performs action")
        
        # 目标
        if task.target:
            parts.append(f"on {task.target}")
        
        # 动作详情
        if task.action:
            parts.append(f"using {task.action}")
        
        return " ".join(parts)
    
    def _format_results(self, results: list[dict], query: str) -> str:
        """格式化检索结果为文本"""
        output_lines = [f"=== D&D 5e 规则查询: '{query}' ==="]
        
        for i, result in enumerate(results, 1):
            score = result.get("score", 0)
            content = result.get("content", "")
            metadata = result.get("metadata", {})
            title = metadata.get("title", "无标题")
            
            output_lines.append(f"\n[{i}] {title} (相关性: {score:.2f})")
            output_lines.append(content[:800])  # 限制长度
        
        return "\n".join(output_lines)
