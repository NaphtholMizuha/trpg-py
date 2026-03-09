"""
NarratorAgent - 解说Agent，将执行结果转换为自然语言描述
"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from ..core.execution import ExecutionStep
from ..core.logic_result import LogicResult


class NarratorAgent:
    """
    NarratorAgent - 战斗解说员
    
    将机械的执行轨迹转换为生动的自然语言描述
    """
    
    def __init__(self, model: str = "gpt-4o", api_key: str | None = None, base_url: str | None = None):
        self.use_llm = api_key is not None
        if self.use_llm:
            kwargs = {"model": model, "temperature": 0.7, "api_key": api_key}  # 温度稍高，更有文采
            if base_url:
                kwargs["base_url"] = base_url
            self.llm = ChatOpenAI(**kwargs)
        else:
            self.llm = None
    
    def narrate(self, step: ExecutionStep, result: LogicResult, context: dict) -> str:
        """
        生成步骤执行的自然语言描述
        
        Args:
            step: 执行的步骤
            result: 执行结果
            context: 上下文信息（行动者、目标等）
            
        Returns:
            自然语言描述
        """
        if not self.use_llm:
            return self._fallback_narrate(step, result)
        
        system_prompt = """你是一个D&D 5e战斗解说员，负责将掷骰和计算过程翻译成生动的自然语言。

规则：
1. 描述掷骰结果和计算过程
2. 说明最终结果（命中/未命中、伤害数值等）
3. 保持简洁，1-2句话
4. 用中文回复

示例：
输入：
- 行动：攻击检定
- 轨迹：18 [1d20] + 3 [力量] + 3 [熟练] >= 15 [AC]

输出：
艾尔德拉掷出1d20=18，加上力量调整值+3和熟练加值+3，总计24命中地精（AC 15）！"""

        prompt = f"""步骤：{step.description}
表达式：{step.expression or '无'}
计算轨迹：{result.trace}
结果：{result.result}

请用一句话解说这个战斗过程："""

        try:
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ])
            return response.content.strip()
        except Exception as e:
            return self._fallback_narrate(step, result)
    
    def _fallback_narrate(self, step: ExecutionStep, result: LogicResult) -> str:
        """简单的回退解说"""
        if result.result is True:
            return f"✅ {step.description} 成功"
        elif result.result is False:
            return f"❌ {step.description} 失败"
        elif isinstance(result.result, (int, float)):
            return f"🎲 {step.description} = {result.result}"
        else:
            return f"📋 {step.description} 完成"
