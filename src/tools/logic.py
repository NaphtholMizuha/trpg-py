"""
LogicEngine - 极简表达式求值引擎
仅支持掷骰函数 Roll('XdY') 和简单数值运算
"""

import re
import random
import threading
from dataclasses import dataclass, field
from typing import Any
from asteval import Interpreter


@dataclass
class DiceRecord:
    """记录一次掷骰的详细物理过程"""
    formula: str    # 原始公式 如 "3d20"
    breakdown: str  # 拆解过程 如 "10 + 2 + 2"
    total: int      # 合计值


@dataclass
class EvalResult:
    """评估结果 - 兼容 LogicResult 接口"""
    result: Any
    resolved: str  # 详细的轨迹：包含数值来源和掷骰拆解
    success: bool = True  # 执行是否成功
    resolved_paths: dict = None  # 兼容性字段
    trace: list = None  # 兼容性字段

    def __post_init__(self):
        if self.resolved_paths is None:
            self.resolved_paths = {}
        if self.trace is None:
            self.trace = [self.resolved] if self.resolved else []


class LogicEngine:
    """极简逻辑表达式求值引擎 - 仅支持掷骰和数值运算"""

    # 正则表达式
    DICE_FUNC_REGEX = re.compile(r'(?i)Roll\(["\']([^"\']*)["\']\)')

    def __init__(self):
        self._lock = threading.Lock()
        self._rng = random.Random()
        self._dice_records: list[DiceRecord] = []
        # 缓存基础符号表（内置函数）
        self._base_symtable: dict[str, Any] | None = None

    def eval(self, expression: str) -> EvalResult:
        """
        核心入口：执行表达式

        Args:
            expression: 表达式字符串，如 "Roll('1d20') + 5 >= 15"

        Returns:
            EvalResult: 包含结果和解析轨迹
        """
        with self._lock:
            self._dice_records = []  # 重置记录

            # 构建 interpreter - 无上下文注入
            interpreter = self._build_interpreter()

            # 执行表达式
            result = interpreter(expression)

            # 检查错误
            if interpreter.error:
                err = interpreter.error[0]
                raise ValueError(f"执行错误: {err.get_error()}")

            # 生成包含详细解释的轨迹
            resolved = self._generate_verbose_trace(expression)

            return EvalResult(result=result, resolved=resolved)

    def _build_interpreter(self) -> Interpreter:
        """构建 asteval 解释器，仅注入 Roll 函数"""
        # 首次调用时缓存基础符号表
        if self._base_symtable is None:
            base = Interpreter()
            self._base_symtable = dict(base.symtable)

        # 从基础符号表复制，避免重复创建内置函数
        symtable = dict(self._base_symtable)

        # 注入 Roll 函数
        def roll_func(formula: str) -> int:
            record = self._physical_roll(formula)
            self._dice_records.append(record)
            return record.total

        symtable['Roll'] = roll_func

        return Interpreter(symtable=symtable)

    def _physical_roll(self, formula: str) -> DiceRecord:
        """
        物理掷骰：记录每一个骰子的结果

        Args:
            formula: 骰子公式，如 "3d20" 或 "d20"
        """
        formula = formula.lower().strip()
        match = re.match(r'^(\d+)?d(\d+)$', formula)

        if not match:
            return DiceRecord(formula=formula, breakdown="", total=0)

        count = int(match.group(1)) if match.group(1) else 1
        if count <= 0:
            count = 1
        sides = int(match.group(2))

        rolls = []
        total = 0
        for _ in range(count):
            r = self._rng.randint(1, sides)
            total += r
            rolls.append(str(r))

        return DiceRecord(
            formula=formula,
            breakdown=' + '.join(rolls),
            total=total
        )

    def _generate_verbose_trace(self, expr_str: str) -> str:
        """
        生成详细轨迹
        格式: 14 [3d20 = 10 + 2 + 2 = 14]
        """
        idx = 0
        def replace_dice(match: re.Match) -> str:
            nonlocal idx
            if idx < len(self._dice_records):
                rec = self._dice_records[idx]
                idx += 1
                return f"{rec.total} [{rec.formula} = {rec.breakdown} = {rec.total}]"
            return match.group(0)

        return self.DICE_FUNC_REGEX.sub(replace_dice, expr_str)
