"""计算复核层（calc_verifier）单元测试。

覆盖规格 V-P0-2 + 架构优化 A3：纯算术等式验证、方程求解验证、
多步计算链一致性验证、VIS 可视化块保护（L.8）、自由文本表达式提取。
只测确定性 SymPy 分支，无 LLM / 网络调用。
"""

import unittest

from backend.services.calc_verifier import (
    _eval_expr,
    _solve_equation,
    extract_math_expressions,
    verify_and_fix,
)


class CalcVerifierArithmeticTest(unittest.TestCase):
    def test_correct_arithmetic_unchanged(self):
        text, fixes = verify_and_fix("2+3=5")
        self.assertEqual(text, "2+3=5")
        self.assertEqual(fixes, [])

    def test_wrong_arithmetic_fixed(self):
        text, fixes = verify_and_fix("2+3=6")
        self.assertIn("2+3 = 5", text)
        self.assertEqual(len(fixes), 1)
        self.assertEqual(fixes[0]["claimed"], "6")
        self.assertEqual(fixes[0]["actual"], 5.0)

    def test_multiplication_correct_unchanged(self):
        text, fixes = verify_and_fix("(3+4)*2 = 14")
        self.assertEqual(text, "(3+4)*2 = 14")
        self.assertEqual(fixes, [])


class CalcVerifierEquationTest(unittest.TestCase):
    def test_correct_solve_unchanged(self):
        text, fixes = verify_and_fix("3x+7=22, x=5")
        self.assertEqual(text, "3x+7=22, x=5")
        self.assertEqual(fixes, [])

    def test_wrong_solve_fixed(self):
        text, fixes = verify_and_fix("3x+7=22, x=6")
        self.assertIn("x = 5", text)
        self.assertEqual(len(fixes), 1)
        self.assertEqual(fixes[0]["actual"], "x=5")

    def test_solve_equation_returns_root(self):
        self.assertAlmostEqual(_solve_equation("3x+7", "22"), 5.0)


class CalcVerifierChainTest(unittest.TestCase):
    def test_consistent_chain_unchanged(self):
        text, fixes = verify_and_fix("2+3=5=5×1")
        self.assertEqual(text, "2+3=5=5×1")
        self.assertEqual(fixes, [])

    def test_broken_chain_truncated(self):
        text, fixes = verify_and_fix("2+3=5=7")
        self.assertEqual(text, "2+3 = 5")
        self.assertEqual(len(fixes), 1)
        self.assertIn("broken_at", fixes[0])


class CalcVerifierVisBlockTest(unittest.TestCase):
    def test_vis_block_protected_from_fix(self):
        text, fixes = verify_and_fix(
            '<<<XIAOYUAN_VIS>>>{"a": "3+4=9"}<<<END_VIS>>> 2+3=6'
        )
        self.assertIn("3+4=9", text)
        self.assertIn("2+3 = 5", text)
        self.assertEqual(len(fixes), 1)


class CalcVerifierEvalTest(unittest.TestCase):
    def test_eval_expr_arithmetic(self):
        self.assertAlmostEqual(_eval_expr("2+3*4"), 14.0)
        self.assertAlmostEqual(_eval_expr("2×3"), 6.0)
        self.assertAlmostEqual(_eval_expr("10÷4"), 2.5)

    def test_eval_expr_non_numeric_returns_none(self):
        self.assertIsNone(_eval_expr("abc"))
        self.assertIsNone(_eval_expr("3x+1"))

    def test_solve_equation_no_solution_returns_none(self):
        # 含两个未知数或无法确定唯一解时返回 None
        self.assertIsNone(_solve_equation("x+y", "10"))


class CalcVerifierExtractTest(unittest.TestCase):
    def test_extract_free_text_expression(self):
        results = extract_math_expressions("计算 2+3*4 的结果")
        self.assertEqual(results, [{"expression": "2+3*4", "context": ""}])

    def test_extract_answer_expression(self):
        results = extract_math_expressions("答案=42")
        self.assertIn({"expression": "42", "context": "answer"}, results)

    def test_extract_empty(self):
        self.assertEqual(extract_math_expressions("这是一句没有数学的话"), [])


if __name__ == "__main__":
    unittest.main()
