"""数学计算引擎：基于 SymPy 的精确计算，通过 Function Calling 暴露给 LLM。"""

import logging
import math
from typing import Any

import sympy as sp

logger = logging.getLogger(__name__)

# 支持的变量符号
_SYMBOLS: dict[str, sp.Symbol] = {}


def _get_symbol(name: str) -> sp.Symbol:
    if name not in _SYMBOLS:
        _SYMBOLS[name] = sp.Symbol(name)
    return _SYMBOLS[name]


def evaluate_expression(expr_str: str, substitutions: dict[str, float] | None = None) -> dict[str, Any]:
    """解析并计算数学表达式，返回精确结果和数值近似。"""
    try:
        expr = sp.sympify(expr_str, evaluate=False)
        if substitutions:
            subs = {k: sp.nsimplify(v) for k, v in substitutions.items()}
            expr = expr.subs(subs)
        result = sp.simplify(expr)
        numeric = None
        if result.is_number:
            try:
                numeric = float(result.evalf())
            except (TypeError, ValueError):
                pass
        return {
            "success": True,
            "exact": str(result),
            "numeric": numeric,
            "latex": sp.latex(result),
        }
    except Exception as e:
        logger.warning("evaluate_expression failed: %s", e)
        return {"success": False, "error": str(e)}


def solve_equation(eq_str: str, symbol: str = "x") -> dict[str, Any]:
    """解方程，返回所有解。支持 Eq(a, b) 格式或表达式=0 格式。"""
    try:
        x = _get_symbol(symbol)
        # 支持 "x**2 - 4 = 0" 和 "Eq(x**2, 4)" 两种写法
        if "=" in eq_str and "Eq" not in eq_str:
            left, right = eq_str.split("=", 1)
            eq = sp.Eq(sp.sympify(left), sp.sympify(right))
        else:
            eq = sp.sympify(eq_str)
        solutions = sp.solve(eq, x)
        return {
            "success": True,
            "solutions": [str(s) for s in solutions],
            "latex": [sp.latex(s) for s in solutions],
        }
    except Exception as e:
        logger.warning("solve_equation failed: %s", e)
        return {"success": False, "error": str(e)}


def simplify_expression(expr_str: str) -> dict[str, Any]:
    """化简表达式。"""
    try:
        expr = sp.simplify(sp.sympify(expr_str))
        return {
            "success": True,
            "result": str(expr),
            "latex": sp.latex(expr),
        }
    except Exception as e:
        logger.warning("simplify_expression failed: %s", e)
        return {"success": False, "error": str(e)}


def derivative(expr_str: str, symbol: str = "x", order: int = 1) -> dict[str, Any]:
    """求导。"""
    try:
        x = _get_symbol(symbol)
        result = sp.diff(sp.sympify(expr_str), x, order)
        return {
            "success": True,
            "result": str(result),
            "latex": sp.latex(result),
        }
    except Exception as e:
        logger.warning("derivative failed: %s", e)
        return {"success": False, "error": str(e)}


def integrate_expression(expr_str: str, symbol: str = "x",
                         lower: float | None = None, upper: float | None = None) -> dict[str, Any]:
    """积分（不定积分或定积分）。"""
    try:
        x = _get_symbol(symbol)
        expr = sp.sympify(expr_str)
        if lower is not None and upper is not None:
            result = sp.integrate(expr, (x, lower, upper))
        else:
            result = sp.integrate(expr, x)
        numeric = None
        if result.is_number:
            try:
                numeric = float(result.evalf())
            except (TypeError, ValueError):
                pass
        return {
            "success": True,
            "result": str(result),
            "latex": sp.latex(result),
            "numeric": numeric,
        }
    except Exception as e:
        logger.warning("integrate_expression failed: %s", e)
        return {"success": False, "error": str(e)}


def factor_expression(expr_str: str) -> dict[str, Any]:
    """因式分解。"""
    try:
        expr = sp.factor(sp.sympify(expr_str))
        return {
            "success": True,
            "result": str(expr),
            "latex": sp.latex(expr),
        }
    except Exception as e:
        logger.warning("factor_expression failed: %s", e)
        return {"success": False, "error": str(e)}


def expand_expression(expr_str: str) -> dict[str, Any]:
    """展开表达式。"""
    try:
        expr = sp.expand(sp.sympify(expr_str))
        return {
            "success": True,
            "result": str(expr),
            "latex": sp.latex(expr),
        }
    except Exception as e:
        logger.warning("expand_expression failed: %s", e)
        return {"success": False, "error": str(e)}


def _execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """根据工具名分发执行。"""
    handlers = {
        "calculate": lambda: evaluate_expression(
            args["expression"],
            args.get("substitutions"),
        ),
        "solve": lambda: solve_equation(
            args["expression"],
            args.get("symbol", "x"),
        ),
        "simplify": lambda: simplify_expression(args["expression"]),
        "derivative": lambda: derivative(
            args["expression"],
            args.get("symbol", "x"),
            args.get("order", 1),
        ),
        "integrate": lambda: integrate_expression(
            args["expression"],
            args.get("symbol", "x"),
            args.get("lower"),
            args.get("upper"),
        ),
        "factor": lambda: factor_expression(args["expression"]),
        "expand": lambda: expand_expression(args["expression"]),
    }
    handler = handlers.get(name)
    if not handler:
        return {"success": False, "error": f"未知工具: {name}"}
    return handler()


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "计算数学表达式的精确结果。用于：表达式求值、代入计算、数值运算。输入标准数学符号。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '(3/4) * 8' 或 '2*x + 1'",
                    },
                    "substitutions": {
                        "type": "object",
                        "description": "变量替换，如 {\"x\": 2}",
                        "additionalProperties": {"type": "number"},
                    },
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "solve",
            "description": "解方程。支持 'Eq(a,b)' 或 '表达式=0' 格式。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "方程，如 'Eq(x**2, 4)' 或 'x**2 - 4 = 0'",
                    },
                    "symbol": {
                        "type": "string",
                        "description": "未知数符号，默认 'x'",
                        "default": "x",
                    },
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "simplify",
            "description": "化简数学表达式。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "要化简的表达式",
                    },
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "derivative",
            "description": "对表达式求导。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "表达式，如 'x**3 + 2*x'",
                    },
                    "symbol": {
                        "type": "string",
                        "description": "求导变量，默认 'x'",
                        "default": "x",
                    },
                    "order": {
                        "type": "integer",
                        "description": "求导阶数，默认 1",
                        "default": 1,
                    },
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "integrate",
            "description": "积分。不指定上下限为不定积分，指定则为定积分。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "表达式，如 '2*x'",
                    },
                    "symbol": {
                        "type": "string",
                        "description": "积分变量，默认 'x'",
                        "default": "x",
                    },
                    "lower": {
                        "type": "number",
                        "description": "积分下限（不定积分时不填）",
                    },
                    "upper": {
                        "type": "number",
                        "description": "积分上限（不定积分时不填）",
                    },
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "factor",
            "description": "对多项式进行因式分解。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "多项式，如 'x**2 - 4'",
                    },
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "expand",
            "description": "展开数学表达式。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "表达式，如 '(x+1)*(x-1)'",
                    },
                },
                "required": ["expression"],
            },
        },
    },
]
