"""BKT（贝叶斯知识追踪）学生级参数估计单元测试（进度表 135）。

用标准库 unittest，无需 pytest / FastAPI / 网络。
覆盖规格 §7 全部验收点：内核公式单调性、滞回锁存、同日不遗忘、隔天 FSRS 阻尼、
观测清洗、s_u 网格可复现、bkt_obs 聚合对账、P(L0) 冷启动先验初始化。
"""

import unittest
from datetime import date, timedelta

from backend.agent.assessment import apply_eval
from backend.models.student import MasteryRecord, ReviewLog, ReviewSchedule, Student
from backend.services.bkt import (
    PRIORS_BY_TYPE,
    estimate_learn_offset,
    is_mastered,
    p_known,
    update_bkt,
)

TOPIC = "6a_jiafa"


def _make_student() -> Student:
    return Student(id="test", name="小明")


class BktKernelTest(unittest.TestCase):
    def test_cold_start_prior(self):
        """P(L0) 冷启动：无 BKT 状态返回先验；首次更新即离开 0，不与真掌握=0 混淆。"""
        s = _make_student()
        self.assertAlmostEqual(p_known(s, TOPIC), PRIORS_BY_TYPE["default"]["L0"])

        update_bkt(s, TOPIC, True)
        rec = s.mastery[TOPIC]
        self.assertGreater(rec.p_known, 0.0)
        self.assertGreater(rec.p_known, PRIORS_BY_TYPE["default"]["L0"])

    def test_correct_increases_incorrect_decreases(self):
        """内核公式单调性：答对升、答错降（相对先验/上一轮）。"""
        s = _make_student()
        update_bkt(s, TOPIC, True)
        p1 = s.mastery[TOPIC].p_known
        self.assertGreater(p1, PRIORS_BY_TYPE["default"]["L0"])

        update_bkt(s, TOPIC, False)
        p2 = s.mastery[TOPIC].p_known
        self.assertLess(p2, p1)

        s2 = _make_student()
        update_bkt(s2, TOPIC, False)
        self.assertLess(s2.mastery[TOPIC].p_known, PRIORS_BY_TYPE["default"]["L0"])

    def test_mastery_hysteresis(self):
        """滞回锁存：≥0.90 进入、<0.80 退出、0.85 区间保持。"""
        s = _make_student()
        rec = MasteryRecord()
        s.mastery[TOPIC] = rec

        rec.p_known = 0.95
        self.assertTrue(is_mastered(s, TOPIC))
        rec.p_known = 0.85
        self.assertTrue(is_mastered(s, TOPIC))
        rec.p_known = 0.79
        self.assertFalse(is_mastered(s, TOPIC))
        rec.p_known = 0.91
        self.assertTrue(is_mastered(s, TOPIC))

    def test_same_day_no_forgetting(self):
        """同日（Δt=0）不遗忘；隔天（Δt≥1 且 stability>0）应用 FSRS 阻尼。"""
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        s_today = _make_student()
        rec = MasteryRecord()
        rec.p_known = 0.7
        rec.last_bkt_update = today
        s_today.mastery[TOPIC] = rec
        s_today.review_schedules.append(ReviewSchedule(topic_id=TOPIC, stability=5.0))
        update_bkt(s_today, TOPIC, True)

        s_yest = _make_student()
        rec2 = MasteryRecord()
        rec2.p_known = 0.7
        rec2.last_bkt_update = yesterday
        s_yest.mastery[TOPIC] = rec2
        s_yest.review_schedules.append(ReviewSchedule(topic_id=TOPIC, stability=5.0))
        update_bkt(s_yest, TOPIC, True)

        self.assertLess(s_yest.mastery[TOPIC].p_known, s_today.mastery[TOPIC].p_known)

    def test_no_schedule_or_zero_stability_skips_forgetting(self):
        """无 ReviewSchedule 或 stability≤0 时跳过遗忘阻尼。"""
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        base = _make_student()
        rec = MasteryRecord()
        rec.p_known = 0.7
        rec.last_bkt_update = today
        base.mastery[TOPIC] = rec
        update_bkt(base, TOPIC, True)

        no_sched = _make_student()
        rec2 = MasteryRecord()
        rec2.p_known = 0.7
        rec2.last_bkt_update = yesterday
        no_sched.mastery[TOPIC] = rec2
        update_bkt(no_sched, TOPIC, True)
        self.assertAlmostEqual(no_sched.mastery[TOPIC].p_known, base.mastery[TOPIC].p_known)

        zero_stab = _make_student()
        rec3 = MasteryRecord()
        rec3.p_known = 0.7
        rec3.last_bkt_update = yesterday
        zero_stab.mastery[TOPIC] = rec3
        zero_stab.review_schedules.append(ReviewSchedule(topic_id=TOPIC, stability=0.0))
        update_bkt(zero_stab, TOPIC, True)
        self.assertAlmostEqual(zero_stab.mastery[TOPIC].p_known, base.mastery[TOPIC].p_known)

    def test_forgetting_factor_formula(self):
        """FSRS 可提取性 R 公式自洽：t=S 时 R=0.9。"""
        from backend.services import bkt

        s = 5.0
        r = (1.0 + bkt.FACTOR * s / s) ** bkt.DECAY
        self.assertAlmostEqual(r, 0.9, places=6)


class BktObservationTest(unittest.TestCase):
    def test_apply_eval_cleaning(self):
        """观测清洗：缺省 False（LLM 未作答）轮不入 BKT；显式 bool 才入。"""
        s = _make_student()
        apply_eval(s, {"mastery_updates": {"6a_jiafa": 0.9}})
        self.assertEqual(s.bkt_obs_total, 0)
        rec = s.mastery.get("6a_jiafa")
        self.assertTrue(rec is None or rec.p_known == 0.0)

        s2 = _make_student()
        apply_eval(s2, {"mastery_updates": {"6a_jiafa": 0.9}, "independent_success": True})
        self.assertEqual(s2.bkt_obs_total, 1)
        self.assertEqual(s2.bkt_obs_correct, 1)
        self.assertGreater(s2.mastery["6a_jiafa"].p_known, 0.0)

        s3 = _make_student()
        apply_eval(s3, {"mastery_updates": {"6a_jiafa": 0.2}, "independent_success": False})
        self.assertEqual(s3.bkt_obs_total, 1)
        self.assertEqual(s3.bkt_obs_correct, 0)
        self.assertGreater(s3.mastery["6a_jiafa"].p_known, 0.0)

    def test_delayed_check_failure_forgetting(self):
        """延迟验证失败：correct=False + 显式遗忘回退（logit −1.5）。"""
        from backend.services.mastery_tracker import record_delayed_check_result

        s = _make_student()
        for _ in range(5):
            update_bkt(s, TOPIC, True)
        before = s.mastery[TOPIC].p_known

        result = record_delayed_check_result(s, TOPIC, False)

        self.assertTrue(result["rolled_back"])
        self.assertLess(s.mastery[TOPIC].p_known, before)
        self.assertEqual(s.bkt_obs_total, 6)

    def test_bkt_obs_aggregation(self):
        """bkt_obs 聚合对账：多次观测后计数与逐条观测一致。"""
        s = _make_student()
        for _ in range(7):
            update_bkt(s, TOPIC, True)
        for _ in range(3):
            update_bkt(s, TOPIC, False)
        self.assertEqual(s.bkt_obs_total, 10)
        self.assertEqual(s.bkt_obs_correct, 7)
        self.assertEqual(s.mastery[TOPIC].bkt_n, 10)

    def test_random_100_reconciliation(self):
        """随机 100 次作答对账（固定种子，可复现）。"""
        import random

        rng = random.Random(135)
        s = _make_student()
        expected_correct = 0
        for _ in range(100):
            correct = rng.random() < 0.6
            update_bkt(s, TOPIC, correct)
            if correct:
                expected_correct += 1
        self.assertEqual(s.bkt_obs_total, 100)
        self.assertEqual(s.bkt_obs_correct, expected_correct)
        self.assertEqual(s.mastery[TOPIC].bkt_n, 100)


class BktOffsetTest(unittest.TestCase):
    def test_estimate_learn_offset_grid(self):
        """s_u 1-D 网格可复现：全对→正向偏移，全错→负向偏移，无观测→0.5。"""
        s = _make_student()
        for i in range(10):
            s.review_logs.append(
                ReviewLog(topic_id=TOPIC, rating=3, review_datetime=f"2026-01-01T{i:02d}:00:00")
            )
        off_high = estimate_learn_offset(s)
        self.assertGreater(off_high, 0.5)

        s2 = _make_student()
        for i in range(10):
            s2.review_logs.append(
                ReviewLog(topic_id=TOPIC, rating=1, review_datetime=f"2026-01-01T{i:02d}:00:00")
            )
        off_low = estimate_learn_offset(s2)
        self.assertLess(off_low, 0.5)

        self.assertAlmostEqual(estimate_learn_offset(s), off_high)
        self.assertEqual(estimate_learn_offset(_make_student()), 0.5)


if __name__ == "__main__":
    unittest.main()
