"""H1「掌握度验证」扩展单元测试（架构优化 P3）。

用标准库 unittest，无需 pytest / FastAPI / 网络。
覆盖五项验收：
  1. schedule_delayed_check(days=7) next_review 正确
  2. schedule_verification 达标登记且防重
  3. get_due_verifications 到期返回（1 天 + 7 天合并、按到期排序、非 delayed_check 不入）
  4. 7 天验证失败追加 concept_forgetting Gap（且不重复叠加）
  5. 结算校验：mastery_updates 不含目标知识点时不结算、含时才结算
"""

import unittest
from datetime import date, timedelta

from backend.agent.chat import _delayed_check_settles
from backend.models.student import MasteryRecord, ReviewSchedule, Student
from backend.services.mastery_tracker import (
    get_due_verifications,
    record_delayed_check_result,
    schedule_delayed_check,
    schedule_verification,
)

TOPIC = "6a_jiafa"


def _make_student() -> Student:
    return Student(id="test", name="小明")


class ScheduleDelayedCheckTest(unittest.TestCase):
    def test_days_param_sets_next_review_and_interval(self):
        """days=7：next_review = today+7，interval_days=7，delayed_check=True。"""
        s = _make_student()
        ok = schedule_delayed_check(s, TOPIC, days=7)
        self.assertTrue(ok)
        self.assertEqual(len(s.review_schedules), 1)
        rs = s.review_schedules[0]
        self.assertEqual(rs.next_review, (date.today() + timedelta(days=7)).isoformat())
        self.assertEqual(rs.interval_days, 7)
        self.assertTrue(rs.delayed_check)

    def test_default_days_is_one(self):
        """缺省 days=1：行为与既有次日延迟验证一致（不回退）。"""
        s = _make_student()
        schedule_delayed_check(s, TOPIC)
        rs = s.review_schedules[0]
        self.assertEqual(rs.next_review, (date.today() + timedelta(days=1)).isoformat())
        self.assertEqual(rs.interval_days, 1)


class ScheduleVerificationTest(unittest.TestCase):
    def test_registers_7day_check(self):
        """掌握达标登记：新建 7 天延迟验证排期。"""
        s = _make_student()
        ok = schedule_verification(s, TOPIC)
        self.assertTrue(ok)
        self.assertEqual(len(s.review_schedules), 1)
        rs = s.review_schedules[0]
        self.assertEqual(rs.interval_days, 7)
        self.assertTrue(rs.delayed_check)

    def test_dedup_no_duplicate_schedule(self):
        """防重：同一知识点重复登记不新建排期（升级而非叠加）。"""
        s = _make_student()
        self.assertTrue(schedule_verification(s, TOPIC))
        self.assertTrue(schedule_verification(s, TOPIC))
        self.assertEqual(len(s.review_schedules), 1)
        rs = s.review_schedules[0]
        self.assertEqual(rs.interval_days, 7)
        self.assertTrue(rs.delayed_check)


class GetDueVerificationsTest(unittest.TestCase):
    def test_due_returns_merged_sorted(self):
        """到期返回：1 天与 7 天两类合并、按 next_review 升序、非 delayed_check 不入。"""
        s = _make_student()
        s.review_schedules.append(
            ReviewSchedule(
                topic_id=TOPIC,
                topic_name="有理数加法",
                next_review=(date.today() - timedelta(days=1)).isoformat(),
                interval_days=1,
                delayed_check=True,
            )
        )
        s.review_schedules.append(
            ReviewSchedule(
                topic_id="6a_jianfa",
                topic_name="有理数减法",
                next_review=date.today().isoformat(),
                interval_days=7,
                delayed_check=True,
            )
        )
        s.review_schedules.append(
            ReviewSchedule(
                topic_id="6a_chengfa",
                topic_name="有理数乘法",
                next_review=date.today().isoformat(),
                interval_days=3,
                delayed_check=False,
            )
        )
        due = get_due_verifications(s)
        self.assertEqual([r.topic_id for r in due], [TOPIC, "6a_jianfa"])

    def test_not_due_returns_empty(self):
        """未来到期不返回。"""
        s = _make_student()
        schedule_delayed_check(s, TOPIC, days=7)
        self.assertEqual(get_due_verifications(s), [])


class ConceptForgettingGapTest(unittest.TestCase):
    def _mastered_student(self) -> Student:
        s = _make_student()
        s.mastery[TOPIC] = MasteryRecord(
            score=0.9, confidence=0.8, attempts_correct=1, attempts_total=1
        )
        return s

    def test_failure_appends_concept_forgetting_gap(self):
        """7 天验证失败：追加 concept_forgetting Gap，字段齐全。"""
        s = self._mastered_student()
        schedule_verification(s, TOPIC)
        result = record_delayed_check_result(s, TOPIC, False)
        self.assertTrue(result["rolled_back"])

        gaps = [g for g in s.gaps if g.topic_id == TOPIC and g.category == "concept_forgetting"]
        self.assertEqual(len(gaps), 1)
        g = gaps[0]
        self.assertEqual(g.type, "concept")
        self.assertEqual(g.status, "open")
        self.assertEqual(g.evidence, "delayed_check_result=false")
        self.assertTrue(g.root_cause)
        self.assertTrue(g.repair_strategy)
        self.assertEqual(g.occurrence_count, 1)

    def test_no_duplicate_gap_on_repeat_failure(self):
        """同知识点已有 open gap 时不重复叠加。"""
        s = self._mastered_student()
        schedule_verification(s, TOPIC)
        record_delayed_check_result(s, TOPIC, False)
        record_delayed_check_result(s, TOPIC, False)

        gaps = [g for g in s.gaps if g.topic_id == TOPIC and g.category == "concept_forgetting"]
        self.assertEqual(len(gaps), 1)


class SettlementValidationTest(unittest.TestCase):
    def test_settles_only_when_topic_in_mastery_updates(self):
        """结算校验：mastery_updates 不含目标知识点时不结算、含时才结算。"""
        self.assertFalse(_delayed_check_settles({"mastery_updates": {"6a_jianfa": 0.8}}, TOPIC))
        self.assertTrue(_delayed_check_settles({"mastery_updates": {TOPIC: 0.8}}, TOPIC))
        self.assertFalse(_delayed_check_settles({}, TOPIC))
        self.assertFalse(_delayed_check_settles(None, TOPIC))
        self.assertFalse(_delayed_check_settles({"mastery_updates": {TOPIC: 0.8}}, ""))


if __name__ == "__main__":
    unittest.main()
