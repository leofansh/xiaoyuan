"""知识图谱（沪教版·五四制）单元测试。

用标准库 unittest，无需 pytest / FastAPI / 网络。
覆盖图谱完整性校验、前置依赖链遍历、最小不会单元定位、认知门槛判断、
掌握度判定标准 / 典型错误模式生成、台阶式诊断步骤。
"""

import unittest

from backend.knowledge import syllabus
from backend.knowledge.syllabus import KnowledgeNode


class SyllabusGraphTest(unittest.TestCase):
    def test_graph_has_78_unique_nodes(self):
        self.assertEqual(len(syllabus.NODES), 78)
        ids = [n.id for n in syllabus.NODES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_get_node_known_and_unknown(self):
        node = syllabus.get_node("6a_fangcheng_jie")
        self.assertIsNotNone(node)
        self.assertEqual(node.name, "一元一次方程及其解法")
        self.assertIsNone(syllabus.get_node("does_not_exist"))

    def test_validate_no_errors(self):
        self.assertEqual(syllabus.validate(), [])

    def test_prerequisite_chain_simple_and_leaf(self):
        self.assertEqual(
            syllabus.prerequisite_chain("6a_shuzhou"),
            ["6a_yinru", "6a_shuzhou"],
        )
        chain = syllabus.prerequisite_chain("6a_jianfa")
        self.assertEqual(chain[-1], "6a_jianfa")
        self.assertEqual(len(chain), len(set(chain)))
        self.assertEqual(syllabus.get_node(chain[0]).prerequisites, [])

    def test_prerequisite_chain_unknown_returns_empty(self):
        self.assertEqual(syllabus.prerequisite_chain("nope"), [])

    def test_find_minimum_gap_node(self):
        mastery = {"6a_yinru": 0.9, "6a_shuzhou": 0.4}
        self.assertEqual(
            syllabus.find_minimum_gap_node("6a_shuzhou", mastery), "6a_shuzhou"
        )
        mastery2 = {"6a_yinru": 0.1, "6a_shuzhou": 0.8}
        self.assertEqual(
            syllabus.find_minimum_gap_node("6a_shuzhou", mastery2), "6a_yinru"
        )
        rec_mastery = {"6a_yinru": {"score": 0.9}, "6a_shuzhou": {"score": 0.4}}
        self.assertEqual(
            syllabus.find_minimum_gap_node("6a_shuzhou", rec_mastery), "6a_shuzhou"
        )
        self.assertEqual(syllabus.find_minimum_gap_node("nope", {}), "nope")

    def test_can_learn_topic_stage_gating(self):
        transitional = syllabus.get_node("6a_fangcheng_jie")
        self.assertFalse(syllabus.can_learn_topic("concrete", transitional))
        self.assertTrue(syllabus.can_learn_topic("transitional", transitional))
        self.assertTrue(syllabus.can_learn_topic("formal", transitional))

        concrete = syllabus.get_node("6a_shuzhou")
        self.assertTrue(syllabus.can_learn_topic("concrete", concrete))
        self.assertTrue(syllabus.can_learn_topic("formal", concrete))

    def test_mastery_criteria_explicit_and_generated(self):
        explicit = syllabus.get_node("6a_fangcheng_jie")
        criteria = syllabus.mastery_criteria_for(explicit)
        self.assertEqual(len(criteria), 5)
        self.assertIn("一元一次方程", criteria[0])

        generated = syllabus.get_node("elem_sifasuan")
        criteria = syllabus.mastery_criteria_for(generated)
        self.assertEqual(len(criteria), 5)
        self.assertTrue(any("四则运算" in c for c in criteria))
        self.assertEqual(criteria[-1], "能独立完成拓展题并验证答案合理性")

    def test_typical_errors_explicit_and_generated(self):
        explicit = syllabus.get_node("6a_fangcheng_jie")
        self.assertEqual(
            syllabus.typical_errors_for(explicit),
            ["calc_sign_error", "concept_condition_unclear", "read_miss_condition"],
        )
        generated = syllabus.get_node("elem_sifasuan")
        self.assertEqual(
            syllabus.typical_errors_for(generated),
            ["calc_multiplication_table", "calc_copy_error", "concept_formula_misremember"],
        )

    def test_diagnostic_steps_explicit(self):
        node = syllabus.get_node("6a_fangcheng_jie")
        steps = syllabus.get_diagnostic_steps(node)
        self.assertEqual(len(steps), 5)
        self.assertEqual(steps[0]["name"], "去分母")
        self.assertEqual(steps[-1]["name"], "系数化 1")

    def test_diagnostic_steps_fallback_and_default(self):
        fallback = syllabus.get_node("elem_sifasuan")
        steps = syllabus.get_diagnostic_steps(fallback)
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]["name"], "运算顺序搞混")
        self.assertIn("运算顺序搞混", steps[0]["check_question"])

        empty = KnowledgeNode(id="x", name="测试知识点", chapter="ch")
        steps = syllabus.get_diagnostic_steps(empty)
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["step"], 1)
        self.assertEqual(steps[0]["name"], "概念理解")
        self.assertIn("测试知识点", steps[0]["check_question"])


if __name__ == "__main__":
    unittest.main()
