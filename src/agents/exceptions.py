"""
Agent 自定义异常类
"""


class AgentError(Exception):
    """Agent 基础异常"""
    pass


class ParseError(AgentError):
    """解析失败"""
    def __init__(self, content: str, reason: str):
        self.content = content
        self.reason = reason
        super().__init__(f"解析失败: {reason}")


class ToolExecutionError(AgentError):
    """工具执行失败"""
    pass


class LLMError(AgentError):
    """LLM 调用失败"""
    pass
