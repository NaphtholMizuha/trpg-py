"""
结构化日志配置

使用 loguru 替代 structlog，支持结构化输出和层级日志
"""
import sys
from loguru import logger


def configure_logging(debug: bool = False):
    """配置 loguru 日志

    Args:
        debug: 是否启用 DEBUG 级别（显示工具调用输入输出）
    """
    # 移除默认处理器
    logger.remove()

    level = "DEBUG" if debug else "INFO"

    # 添加控制台处理器
    logger.add(
        sys.stdout,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{extra[name]}</cyan> - "
               "<level>{message}</level>",
        colorize=True,
    )


def get_logger(name: str):
    """获取日志记录器

    Args:
        name: logger 名称，通常使用 __name__

    Returns:
        配置了 name 的 logger 实例
    """
    return logger.bind(name=name)
