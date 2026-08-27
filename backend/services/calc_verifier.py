"""计算结果验证器：LLM回复中的数学等式用SymPy重新验证，不一致则自动替换。

这是 Function Calling 的兜底机制（V-P0-2 + 架构优化 A3）：
- 纯算术等式验证（如 2+3=5）
- 方程求解验证（如 3x+7=22，检验 x=5 是否满足方程）
- 多步计算链一致性验证（如 2+3=5=5×4=20 的中间步骤一致性）
即使 LLM 没有调用计算工具，后端也会验证所有数学结果，保证教给学生的计算正确。
"""

import re
import logging

import sympy as sp

logger = logging.getLogger(__name__)

# 纯算术表达式 = 数值（如 2+3 = 5, (3+4)*2 = 14）
# 要求：表达式只含数字和运算符（不含字母/未知数），且必须含至少一个二元运算符号，
#       且两侧有边界（避免截断 3x+7=22 这类含未知数的方程）
EXPR_EQ = re.compile(
    r'(?<![A-Za-z0-9_])'          # 表达式前不能是变量字符
    r'((?:\d+(?:\.\d+)?[\+\-\*\/])+\s*\d+(?:\.\d+)?)'  # 含运算的算术式
    r'\s*=\s*(-?\d+\.?\d*)'
    r'(?!\d)'
)

# 线性方程求解验证：形如 "3x+7=22, x=5" 或 "方程 3x+7=22 解得 x=5"
# 验证未知数表达式求解结果是否与声明的一致
TERM = r'(?:\d+(?:\.\d+)?\s*[xX]\s*|[xX]\s*|\d+(?:\.\d+)?\s*)'
EQ_SOLVE = re.compile(
    r'(?<![A-Za-z0-9_])'
    r'((?:' + TERM + r')(?:[\+\-\*\/]\s*' + TERM + r')*)'   # 未知数表达式，如 3x+7
    r'\s*=\s*(-?\d+\.?\d*)'
    r'(?!\d)'
    r'(?:[\s,，;；→、]+|[\s,，;；→、]*(?:的?解|解得|则|所以|可得|得到)\s*[是为]?)'
    r'\s*[xX]\s*=\s*(-?\d+\.?\d*)'
    r'(?!\d)'
)

# 多步计算链一致性：A=B=C=D（纯算术，等式串联）
# 支持 × ÷ 中文乘法除号
_CHAIN_SEG = r'(?:\d+(?:\.\d+)?(?:\s*[\+\-\*\/×÷]\s*\d+(?:\.\d+)?)*)'
CHAIN_EQ = re.compile(
    r'(?<![A-Za-z0-9_])'
    + _CHAIN_SEG                          # 第一段：算术式
    + r'(?:\s*=\s*' + _CHAIN_SEG + r'){2,}'  # 后续至少 2 段
    + r'(?!\d)'
)


def _eval_expr(expr_str: str) -> float | None:
    """安全求值纯算术表达式，失败返回 None。"""
    try:
        normalized = expr_str.replace("×", "*").replace("÷", "/").replace("X", "x")
        expr = sp.sympify(normalized)
        if expr.is_number:
            return float(expr.evalf())
        return None
    except Exception:  # noqa: BLE001
        return None


def _solve_equation(lhs: str, rhs: str) -> float | None:
    """求解含未知数 x 的线性方程 lhs=rhs，返回 x 的值或 None。"""
    try:
        x = sp.Symbol("x")
        # 统一 x/X 为符号 x，并把隐式乘法 "3x" 规范为 "3*x"
        expr_str = lhs.replace("X", "x")
        expr_str = re.sub(r"(\d)\s*([x])", r"\1*\2", expr_str)
        expr_str = re.sub(r"([x])\s*(\d)", r"\1*\2", expr_str)
        lhs_sym = sp.sympify(expr_str)
        rhs_val = sp.sympify(rhs)
        sol = sp.solve(sp.Eq(lhs_sym, rhs_val), x)
        if len(sol) == 1:
            return float(sol[0].evalf())
        return None
    except Exception:  # noqa: BLE001
        return None


def verify_and_fix(text: str) -> tuple[str, list[dict]]:
    """验证文本中的数学等式，返回(修正后文本, 修正记录列表)。"""
    fixes = []

    def _try_fix(expr_str: str, claimed: str, full_match: str) -> str:
        """尝试验证一个纯算术等式，返回修正后的完整匹配或原匹配。"""
        actual = _eval_expr(expr_str)
        if actual is not None:
            claimed_val = float(claimed)
            if abs(actual - claimed_val) > 0.001:
                fixes.append({
                    "original": full_match,
                    "expr": expr_str.strip(),
                    "claimed": claimed,
                    "actual": actual,
                })
                return f"{expr_str.strip()} = {actual:g}"
        return full_match

    # 1. 纯算术等式验证
    text = EXPR_EQ.sub(
        lambda m: _try_fix(m.group(1), m.group(2), m.group(0)),
        text,
    )

    # 2. 方程求解验证（先做，避免被纯算术正则误伤）
    def _try_solve(match: re.Match) -> str:
        lhs = match.group(1).strip()
        rhs = match.group(2)
        claimed_x = match.group(3)
        solved = _solve_equation(lhs, rhs)
        if solved is not None:
            claimed = float(claimed_x)
            if abs(solved - claimed) > 0.001:
                fixes.append({
                    "original": match.group(0),
                    "expr": lhs,
                    "claimed": f"x={claimed_x}",
                    "actual": f"x={solved:g}",
                })
                return f"{lhs} = {rhs}，x = {solved:g}"
        return match.group(0)

    text = EQ_SOLVE.sub(_try_solve, text)

    # 3. 多步计算链一致性验证
    def _try_chain(match: re.Match) -> str:
        chain_str = match.group(0)
        parts = [p.strip() for p in re.split(r'\s*=\s*', chain_str) if p.strip()]
        values: list[float | None] = []
        for p in parts:
            v = _eval_expr(p)
            if v is None:
                return match.group(0)  # 含无法求值的部分，跳过
            values.append(v)
        # 链上所有值应一致（允许极小的浮点误差）
        if len(values) >= 2 and values[0] is not None:
            ref = values[0]
            broken = []
            for i, v in enumerate(values):
                if abs(v - ref) > 0.001:
                    broken.append(i)
            if broken:
                fixes.append({
                    "original": match.group(0),
                    "chain": parts,
                    "values": [f"{v:g}" for v in values],
                    "broken_at": broken,
                })
                # 不确定分段语义时，截断到第一步正确等式，保证不教错
                return f"{parts[0]} = {ref:g}"
        return match.group(0)

    text = CHAIN_EQ.sub(_try_chain, text)

    if fixes:
        logger.warning("计算验证修正了%d处: %s", len(fixes), fixes)

    return text, fixes
