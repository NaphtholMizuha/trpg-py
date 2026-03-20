"""
结构化日志配置

使用 loguru 替代 structlog，支持结构化输出和层级日志
"""
import sys
from loguru import logger


def _escape_loguru_braces(text: str) -> str:
    """转义 loguru format string 中的花括号，避免额外字段被误当成占位符。"""
    return text.replace("{", "{{").replace("}", "}}")


def configure_logging(debug: bool = False):
    """配置 loguru 日志

    Args:
        debug: 是否启用 DEBUG 级别（显示工具调用输入输出）
    """
    # 移除默认处理器
    logger.remove()

    level = "DEBUG" if debug else "INFO"

    def formatter(record):
        logger_name = record["extra"].get("name") or record["name"]
        extra_fields = {
            key: value
            for key, value in record["extra"].items()
            if key != "name"
        }
        if extra_fields:
            rendered_extra = " ".join(
                f"{key}={value!r}"
                for key, value in extra_fields.items()
            )
            extra_suffix = f" | {_escape_loguru_braces(rendered_extra)}"
        else:
            extra_suffix = ""
        exception_suffix = "\n{exception}" if record["exception"] else ""
        return (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            f"<cyan>{logger_name}</cyan> - "
            f"<level>{{message}}</level>{extra_suffix}{exception_suffix}\n"
        )

    # 添加控制台处理器
    logger.add(
        sys.stdout,
        level=level,
        format=formatter,
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
