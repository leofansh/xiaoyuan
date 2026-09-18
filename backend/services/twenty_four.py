"""24 点热身小游戏：牌面生成 + 全解求解器 + 表达式安全校验。

游戏规则：随机 4 张牌（点数 1~13），孩子用 + - * / 和括号把 4 个数各用一次
算成 24。所有数值运算均使用 fractions.Fraction 精确计算，杜绝浮点误差。

仅依赖标准库（itertools / fractions / ast / random）。
"""

from __future__ import annotations

import ast
import itertools
import random
from collections import Counter
from fractions import Fraction

OPERATORS = "+-*/"

# 5 种括号结构（4 个数 a,b,c,d 与 3 个运算符 o1,o2,o3）：
#   1. ((a o1 b) o2 c) o3 d
#   2. (a o1 (b o2 c)) o3 d
#   3. a o1 ((b o2 c) o3 d)
#   4. a o1 (b o2 (c o3 d))
#   5. (a o1 b) o3 (c o2 d)


def _combine(x, y, op):
    """把两个子表达式用运算符 op 组合，返回 (Fraction, 字符串, 优先级) 或 None。

    优先级：0 = 原子（数字），1 = 加减，2 = 乘除。除数为 0 时返回 None。
    """
    if x is None or y is None:
        return None
    xv, xs, xp = x
    yv, ys, yp = y
    if op == "+":
        return xv + yv, f"{xs}+{ys}", 1
    if op == "-":
        rs = f"({ys})" if yp == 1 else ys
        return xv - yv, f"{xs}-{rs}", 1
    if op == "*":
        ls = f"({xs})" if xp == 1 else xs
        rs = f"({ys})" if yp == 1 else ys
        return xv * yv, f"{ls}*{rs}", 2
    if op == "/":
        if yv == 0:
            return None
        ls = f"({xs})" if xp == 1 else xs
        rs = f"({ys})" if yp in (1, 2) else ys
        return xv / yv, f"{ls}/{rs}", 2
    return None


def _build_structures(nodes, o1, o2, o3):
    """按 5 种括号结构组合 4 个原子与 3 个运算符，返回非 None 的结果列表。"""
    a, b, c, d = nodes
    results = []

    # 1. ((a o1 b) o2 c) o3 d
    r = _combine(a, b, o1)
    r = _combine(r, c, o2) if r else None
    r = _combine(r, d, o3) if r else None
    results.append(r)

    # 2. (a o1 (b o2 c)) o3 d
    bc = _combine(b, c, o2)
    r = _combine(a, bc, o1) if bc else None
    r = _combine(r, d, o3) if r else None
    results.append(r)

    # 3. a o1 ((b o2 c) o3 d)
    bc = _combine(b, c, o2)
    bcd = _combine(bc, d, o3) if bc else None
    r = _combine(a, bcd, o1) if bcd else None
    results.append(r)

    # 4. a o1 (b o2 (c o3 d))
    cd = _combine(c, d, o3)
    bcd = _combine(b, cd, o2) if cd else None
    r = _combine(a, bcd, o1) if bcd else None
    results.append(r)

    # 5. (a o1 b) o3 (c o2 d)
    ab = _combine(a, b, o1)
    cd = _combine(c, d, o2)
    r = _combine(ab, cd, o3) if (ab and cd) else None
    results.append(r)

    return [x for x in results if x is not None]


def solve(cards) -> list[str]:
    """穷举全部解，返回去重后的表达式字符串列表。

    对 4 张牌的排列、4 种运算符的组合、5 种括号结构全枚举；
    用 Fraction 精确运算，结果恰为 24 即为解。
    """
    if len(cards) != 4:
        return []

    solutions = set()
    for perm in itertools.permutations(cards):
        nodes = [(Fraction(x), str(x), 0) for x in perm]
        for o1, o2, o3 in itertools.product(OPERATORS, repeat=3):
            for result in _build_structures(nodes, o1, o2, o3):
                if result[0] == 24:
                    solutions.add(result[1])
    return sorted(solutions)


def generate_round() -> dict:
    """随机生成一局有解的 24 点题目，返回 {cards, solution}。

    先穷举试出有解才返回；无解则重新生成，最多重试 50 次。
    """
    for _ in range(50):
        cards = [random.randint(1, 13) for _ in range(4)]
        solutions = solve(cards)
        if solutions:
            return {"cards": cards, "solution": solutions[0]}

    # 理论上几乎不可能走到这里（50 次随机大概率有解），兜底返回一个已知有解组合。
    cards = [4, 4, 4, 4]
    solutions = solve(cards)
    return {"cards": cards, "solution": solutions[0] if solutions else "4*4+4+4"}


def _constant_int(node):
    """返回 ast 节点中的整数字面量值；非整数常量返回 None。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Num) and isinstance(node.n, int) and not isinstance(node.n, bool):
        return node.n
    return None


def _eval_node(node, numbers):
    """用 Fraction 精确求值 ast 树，同时收集出现过的整数字面量。

    仅白名单放行：整数常量、加减乘除二元运算。其余节点抛 ValueError。
    """
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, numbers)

    v = _constant_int(node)
    if v is not None:
        numbers.append(v)
        return Fraction(v)

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, numbers)
        right = _eval_node(node.right, numbers)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise ZeroDivisionError
            return left / right

    raise ValueError("unsupported expression node")


def check_expression(cards, expr) -> dict:
    """校验孩子提交的表达式，返回 {valid, correct, reason}。

    规则：① 语法合法（只允许数字、+ - * /、括号、空格）；
         ② 出现的数字与给定 cards 一一对应（每张牌恰好用一次，支持两位数）；
         ③ 用 Fraction 精确求值，结果 == 24 则 correct。
    """
    if not isinstance(expr, str) or not expr.strip():
        return {"valid": False, "correct": False, "reason": "先写一个算式吧"}

    s = expr.strip()
    allowed = set("0123456789+-*/() ")
    for ch in s:
        if ch not in allowed:
            return {"valid": False, "correct": False, "reason": "运算符号只能用 + - * /"}

    try:
        tree = ast.parse(s, mode="eval")
    except SyntaxError:
        return {"valid": False, "correct": False, "reason": "表达式好像没写完整，检查一下括号和运算？"}

    numbers: list[int] = []
    try:
        value = _eval_node(tree, numbers)
    except ZeroDivisionError:
        return {"valid": True, "correct": False, "reason": "分母不能是 0，再想想？"}
    except ValueError:
        return {"valid": False, "correct": False, "reason": "运算符号只能用 + - * /"}

    if len(numbers) != 4:
        return {"valid": False, "correct": False, "reason": "要把 4 张牌都用上哦"}
    if Counter(numbers) != Counter(cards):
        return {"valid": False, "correct": False, "reason": "要用给出的 4 张牌，每张恰好用一次哦"}

    if value == 24:
        return {"valid": True, "correct": True, "reason": "太棒了！"}
    return {"valid": True, "correct": False, "reason": "结果还不是 24，再想想？"}
