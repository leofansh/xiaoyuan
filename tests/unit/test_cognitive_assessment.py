"""认知发展评估单元测试（认知诊断评分 + 五维画像计算 + 贝叶斯持续更新）。

用标准库 unittest，无需 pytest / FastAPI / 网络。
只测确定性计算分支：score_answer 规则评分、compute_final_result 五维画像、
get_next_question / get_assessment_summary、_weighted_update 贝叶斯更新、
update_cognitive_from_interaction 隐式更新、apply_cognitive_decay 30 天衰减、
should_reassess 重评判断。不触碰任何 LLM 调用路径。
"""

import unittest
from datetime import datetime, timedelta

from backend.agent.cognitive_assessment import (
    DIAGNOSTIC_QUESTIONS,
    AssessmentResult,
    _weighted_update,
    apply_cognitive_decay,
    compute_final_result,
    get_assessment_summary,
    get_next_question,
    score_answer,
    should_reassess,
    update_cognitive_from_interaction,
)
from backend.models.student import Student


def _question(qid: str):
    for q in DIAGNOSTIC_QUESTIONS:
        if q.id == qid:
            return q
    raise KeyError(qid)


def _make_student() -> Student:
    return Student(id="test", name="小明")


class ScoreAnswerTest(unittest.TestCase):
    def test_conservation_reasoning(self):
        scores = score_answer(_question("conservation"), "不会变，因为面积公式")
        self.assertAlmostEqual(scores["abstract_thinking"], 0.15)

    def test_conservation_guess_and_wrong(self):
        self.assertAlmostEqual(
            score_answer(_question("conservation"), "不变")["abstract_thinking"], 0.05
        )
        self.assertAlmostEqual(
            score_answer(_question("conservation"), "会变")["abstract_thinking"], -0.05
        )

    def test_hypothetical_branches(self):
        self.assertAlmostEqual(
            score_answer(_question("hypothetical"), "不可能，任何数平方都是正的")["abstract_thinking"], 0.0
        )
        self.assertAlmostEqual(
            score_answer(_question("hypothetical"), "可能存在一种新的数")["abstract_thinking"], 0.2
        )
        self.assertAlmostEqual(
            score_answer(_question("hypothetical"), "不知道")["abstract_thinking"], -0.02
        )

    def test_working_memory_branches(self):
        self.assertAlmostEqual(
            score_answer(_question("working_memory"), "先算25×4，然后乘4，接着得到400")["working_memory"],
            0.2,
        )
        self.assertAlmostEqual(
            score_answer(_question("working_memory"), "先乘起来")["working_memory"], 0.05
        )
        self.assertAlmostEqual(
            score_answer(_question("working_memory"), "直接算25乘16")["working_memory"], -0.03
        )

    def test_metacognition_branches(self):
        self.assertAlmostEqual(
            score_answer(_question("metacognition"), "换一道类似的题我还能做")["metacognition"], 0.2
        )
        self.assertAlmostEqual(
            score_answer(_question("metacognition"), "做对了就是懂了")["metacognition"], 0.0
        )
        self.assertAlmostEqual(
            score_answer(_question("metacognition"), "不知道")["metacognition"], -0.02
        )

    def test_flexibility_branches(self):
        self.assertAlmostEqual(
            score_answer(_question("flexibility"), "可以直接乘，也可以拆开，还能凑整")["flexibility"], 0.15
        )
        self.assertAlmostEqual(
            score_answer(_question("flexibility"), "直接乘和凑整")["flexibility"], 0.08
        )
        self.assertAlmostEqual(
            score_answer(_question("flexibility"), "只会直接乘")["flexibility"], 0.0
        )

    def test_anxiety_branches(self):
        self.assertAlmostEqual(
            score_answer(_question("anxiety_probe"), "有点害怕")["math_anxiety"], 0.15
        )
        self.assertAlmostEqual(
            score_answer(_question("anxiety_probe"), "还好吧")["math_anxiety"], 0.05
        )
        self.assertAlmostEqual(
            score_answer(_question("anxiety_probe"), "挺期待的")["math_anxiety"], -0.05
        )


class ComputeFinalResultTest(unittest.TestCase):
    def test_cognitive_stage_inference(self):
        self.assertEqual(compute_final_result({}).cognitive_stage, "concrete")
        self.assertEqual(
            compute_final_result({"abstract_thinking": [0.15]}).cognitive_stage, "transitional"
        )
        self.assertEqual(
            compute_final_result({"abstract_thinking": [0.4]}).cognitive_stage, "formal"
        )

    def test_full_profile(self):
        result = compute_final_result({
            "abstract_thinking": [0.4, 0.4],
            "concrete_hint": [0.1],
            "working_memory": [0.2],
            "metacognition": [0.2],
            "flexibility": [0.15],
            "math_anxiety": [0.15],
        })
        self.assertEqual(result.cognitive_stage, "formal")
        self.assertEqual(result.working_memory_capacity, "high")
        self.assertAlmostEqual(result.metacognition_level, 0.6)
        self.assertAlmostEqual(result.executive_function["flexibility"], 0.7)
        self.assertAlmostEqual(result.math_anxiety, 0.5)
        self.assertAlmostEqual(result.confidence, 0.8)


class FlowTest(unittest.TestCase):
    def test_get_next_question(self):
        self.assertEqual(get_next_question([]).id, "conservation")
        self.assertEqual(get_next_question(["conservation"]).id, "hypothetical")
        all_ids = [q.id for q in DIAGNOSTIC_QUESTIONS]
        self.assertIsNone(get_next_question(all_ids))

    def test_get_assessment_summary(self):
        r = AssessmentResult(cognitive_stage="formal", working_memory_capacity="high")
        summary = get_assessment_summary(r)
        self.assertIn("抽象思维能力较强", summary)
        self.assertIn("较多信息", summary)

        r2 = AssessmentResult(math_anxiety=0.6, metacognition_level=0.6)
        summary2 = get_assessment_summary(r2)
        self.assertIn("数学焦虑偏高", summary2)
        self.assertIn("元认知能力不错", summary2)


class BayesianUpdateTest(unittest.TestCase):
    def test_weighted_update(self):
        self.assertAlmostEqual(_weighted_update(0.3, 0.9, 0.5), 0.6)
        self.assertEqual(_weighted_update(1.0, 2.0, 1.0), 1.0)   # 上封顶
        self.assertEqual(_weighted_update(0.0, -1.0, 0.5), 0.0)  # 下封顶

    def test_update_cognitive_from_interaction(self):
        daily = _make_student()
        daily.cognitive_profile.abstract_thinking = 0.3
        update_cognitive_from_interaction(daily, {"source": "daily", "abstract_thinking_evidence": 0.8})
        self.assertAlmostEqual(daily.cognitive_profile.abstract_thinking, 0.45)

        diagnostic = _make_student()
        diagnostic.cognitive_profile.abstract_thinking = 0.3
        update_cognitive_from_interaction(
            diagnostic, {"source": "diagnostic", "abstract_thinking_evidence": 0.8}
        )
        self.assertAlmostEqual(diagnostic.cognitive_profile.abstract_thinking, 0.55)

        high_wm = _make_student()
        update_cognitive_from_interaction(high_wm, {"working_memory_evidence": 0.7})
        self.assertEqual(high_wm.cognitive_profile.working_memory_capacity, "high")

        low_wm = _make_student()
        update_cognitive_from_interaction(low_wm, {"working_memory_evidence": 0.1})
        self.assertEqual(low_wm.cognitive_profile.working_memory_capacity, "low")

        s = _make_student()
        s.cognitive_profile.abstract_thinking = 0.3
        s.cognitive_profile.assessment_confidence = 0.0
        update_cognitive_from_interaction(s, {"source": "diagnostic", "abstract_thinking_evidence": 0.9})
        self.assertEqual(s.cognitive_profile.cognitive_stage, "transitional")
        self.assertAlmostEqual(s.cognitive_profile.assessment_confidence, 0.05)
        self.assertTrue(s.cognitive_profile.last_assessed)
        self.assertTrue(s.cognitive_profile.last_updated)

    def test_decay_and_reassess(self):
        no_assessed = _make_student()
        no_assessed.cognitive_profile.assessment_confidence = 0.8
        apply_cognitive_decay(no_assessed)
        self.assertEqual(no_assessed.cognitive_profile.assessment_confidence, 0.8)

        stale = _make_student()
        stale.cognitive_profile.assessment_confidence = 0.8
        stale.cognitive_profile.last_assessed = (datetime.now() - timedelta(days=60)).isoformat()
        apply_cognitive_decay(stale)
        self.assertLess(stale.cognitive_profile.assessment_confidence, 0.8)

        low_conf = _make_student()
        low_conf.cognitive_profile.assessment_confidence = 0.2
        self.assertTrue(should_reassess(low_conf))

        fresh = _make_student()
        fresh.cognitive_profile.assessment_confidence = 0.8
        fresh.cognitive_profile.last_assessed = datetime.now().isoformat()
        self.assertFalse(should_reassess(fresh))

        too_old = _make_student()
        too_old.cognitive_profile.assessment_confidence = 0.8
        too_old.cognitive_profile.last_assessed = (datetime.now() - timedelta(days=100)).isoformat()
        self.assertTrue(should_reassess(too_old))

        no_date = _make_student()
        no_date.cognitive_profile.assessment_confidence = 0.8
        self.assertTrue(should_reassess(no_date))


if __name__ == "__main__":
    unittest.main()
