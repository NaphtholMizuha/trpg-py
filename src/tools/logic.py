"""
LogicEngine - 表达式求值引擎
支持掷骰函数和状态引用
"""

import re
import random
import threading
from dataclasses import dataclass
from types import SimpleNamespace
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
    """评估结果"""
    result: Any
    resolved: str  # 详细的轨迹：包含数值来源和掷骰拆解


class LogicEngine:
    """逻辑表达式求值引擎"""

    # 正则表达式
    DICE_FUNC_REGEX = re.compile(r'(?i)Roll\(["\']([^"\']*)["\']\)')
    IDENT_REGEX = re.compile(r'[a-zA-Z_][a-zA-Z0-9._]*')

    def __init__(self):
        self._lock = threading.Lock()
        self._rng = random.Random()
        self._dice_records: list[DiceRecord] = []
        # 缓存基础符号表（内置函数）
        self._base_symtable: dict[str, Any] | None = None

    def eval(self, expression: str, state: dict[str, Any]) -> EvalResult:
        """
        核心入口：执行表达式

        Args:
            expression: 表达式字符串
            state: 状态字典

        Returns:
            EvalResult: 包含结果和解析轨迹
        """
        with self._lock:
            self._dice_records = []  # 重置记录

            # 构建 interpreter
            interpreter = self._build_interpreter(state)

            # 执行表达式
            result = interpreter(expression)

            # 检查错误
            if interpreter.error:
                err = interpreter.error[0]
                raise ValueError(f"执行错误: {err.get_error()}")

            # 生成包含详细解释的轨迹
            resolved = self._generate_verbose_trace(expression, state)

            return EvalResult(result=result, resolved=resolved)

    def _build_interpreter(self, state: dict[str, Any]) -> Interpreter:
        """构建 asteval 解释器，注入状态和自定义函数"""
        # 首次调用时缓存基础符号表
        if self._base_symtable is None:
            base = Interpreter()
            self._base_symtable = dict(base.symtable)

        # 从基础符号表复制，避免重复创建内置函数
        symtable = dict(self._base_symtable)

        # 转换嵌套字典为 SimpleNamespace，支持 player.ac 语法
        converted = self._convert_to_namespace(state)
        symtable.update(converted)

        # 注入 Roll 函数
        def roll_func(formula: str) -> int:
            record = self._physical_roll(formula)
            self._dice_records.append(record)
            return record.total

        symtable['Roll'] = roll_func
        
        # 注：asteval 原生支持 Python 条件表达式: x if cond else y
        # 示例: Roll('2d6') if Roll('1d20') >= 15 else 0
        
        return Interpreter(symtable=symtable)

    @staticmethod
    def _convert_to_namespace(d: dict[str, Any]) -> dict[str, Any]:
        """
        递归转换嵌套字典为 SimpleNamespace
        支持属性访问语法: player.ac
        支持数组索引: weapon.0 访问 weapons[0]
        """
        result = {}
        for k, v in d.items():
            if isinstance(v, dict):
                result[k] = LogicEngine._convert_to_namespace(v)
                # 如果结果只有字典，包装为 SimpleNamespace
                if isinstance(result[k], dict):
                    result[k] = SimpleNamespace(**result[k])
            elif isinstance(v, list):
                # 将列表转换为字典，索引作为key，支持 .0 .1 访问
                list_dict = {}
                for i, item in enumerate(v):
                    if isinstance(item, dict):
                        list_dict[str(i)] = LogicEngine._convert_to_namespace(item)
                        if isinstance(list_dict[str(i)], dict):
                            list_dict[str(i)] = SimpleNamespace(**list_dict[str(i)])
                    else:
                        list_dict[str(i)] = item
                result[k] = SimpleNamespace(**list_dict)
            else:
                result[k] = v
        return result

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

    def _generate_verbose_trace(self, expr_str: str, state: dict[str, Any]) -> str:
        """
        生成详细轨迹
        格式: 14 [3d20 = 10 + 2 + 2 = 14]
        """
        # 1. 先替换掷骰函数
        idx = 0
        def replace_dice(match: re.Match) -> str:
            nonlocal idx
            if idx < len(self._dice_records):
                rec = self._dice_records[idx]
                idx += 1
                return f"{rec.total} [{rec.formula} = {rec.breakdown} = {rec.total}]"
            return match.group(0)

        res_str = self.DICE_FUNC_REGEX.sub(replace_dice, expr_str)

        # 2. 再替换路径标识符
        def replace_ident(match: re.Match) -> str:
            m = match.group(0)
            if m == 'Roll' or self._is_numeric(m):
                return m

            val = self._get_deep(state, m)
            if val is not None and self._is_simple_value(val):
                return f"{val} [{m}]"
            return m

        res_str = self.IDENT_REGEX.sub(replace_ident, res_str)
        return res_str

    @staticmethod
    def _is_numeric(s: str) -> bool:
        """检查字符串是否为数字"""
        try:
            float(s)
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_simple_value(v: Any) -> bool:
        """检查值是否为简单类型（可用于显示）"""
        return isinstance(v, (int, float, bool))

    @staticmethod
    def _get_deep(data: dict[str, Any], path: str) -> Any:
        """
        深度获取嵌套字典中的值

        Args:
            data: 数据字典
            path: 点分隔的路径，如 "entities.player.ac"
        """
        keys = path.split('.')
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current