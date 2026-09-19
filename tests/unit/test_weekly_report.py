"""周学习报告生成器单元测试（V-P2-1 + 架构优化 G1 洞察/建议）。

用标准库 unittest，无需 pytest / FastAPI / 网络。
覆盖周界计算、本周/上周统计对比、洞察三类（progress/gap/error_pattern）、
suggestions ≤3 条且具体可操作、连续跳过提示。
"""

import unittest
from datetime import date, timedelta

from backend.models.student import Gap, MasteryRecord, SessionSummary, Student
from backend.services.weekly_report import (
    _generate_insights,
    _generate_suggestions,
    _skip_alerts,
    generate_weekly_report,
)


def _make_student() -> Student:
    return Student(id="test", name="小明")


class ReportStructureTest(unittest.TestCase):
    def test_structure_and_week_bounds(self):
        r = generate_weekly_report(_make_student())
        self.assertEqual(r["week_end"], date.today().isoformat())
        expected_start = date.today() - timedelta(days=date.today().weekday())
        self.assertEqual(r["week_start"], expected_start.isoformat())
        for key in (
            "study_days",
            "study_minutes",
            "sessions_count",
            "new_badges",
            "mastered_count",
            "open_gaps_count",
            "vs_last_week",
            "insights",
            "suggestions",
            "skipped_topic_alerts",
        ):
            self.assertIn(key, r)

    def test_empty_student(self):
        r = generate_weekly_report(_make_student())
        self.assertEqual(r["study_minutes"], 0)
        self.assertEqual(r["sessions_count"], 0)
        self.assertEqual(r["insights"], [])
        self.assertLessEqual(len(r["suggestions"]), 3)


class StatisticsTest(unittest.TestCase):
    def test_week_vs_last_week_minutes_delta(self):
        s = _make_student()
        week_start = date.today() - timedelta(days=date.today().weekday())
        s.session_history = [
            SessionSummary(date=week_start.isoformat(), duration_minutes=20),
            SessionSummary(date=date.today().isoformat(), duration_minutes=10),
            SessionSummary(date=(week_start - timedelta(days=3)).isoformat(), duration_minutes=15),
        ]
        r = generate_weekly_report(s)
        self.assertEqual(r["study_minutes"], 30)
        self.assertEqual(r["sessions_count"], 2)
        self.assertEqual(r["vs_last_week"]["minutes_delta"], 15)

    def test_mastered_and_gaps_count(self):
        s = _make_student()
        s.mastery["6a_jiafa"] = MasteryRecord(score=0.8)
        s.mastery["6a_chengfa"] = MasteryRecord(score=0.3)
        s.gaps.append(Gap(topic_id="6a_jianfa", status="open"))
        r = generate_weekly_report(s)
        self.assertEqual(r["mastered_count"], 1)
        self.assertEqual(r["open_gaps_count"], 1)


class InsightsTest(unittest.TestCase):
    def test_progress_type(self):
        s = _make_student()
        s.mastery["6a_jiafa"] = MasteryRecord(score=0.8, confidence=0.6)
        insights = _generate_insights(s, [], [])
        types = [i["type"] for i in insights]
        self.assertIn("progress", types)
        progress = [i for i in insights if i["type"] == "progress"][0]
        self.assertIn("有理数加法", progress["title"])

    def test_gap_type(self):
        s = _make_student()
        s.gaps.append(Gap(topic_id="6a_jiafa", topic_name="有理数加法", status="open"))
        insights = _generate_insights(s, [], [])
        types = [i["type"] for i in insights]
        self.assertIn("gap", types)
        gap = [i for i in insights if i["type"] == "gap"][0]
        self.assertIn("1 个知识漏洞", gap["title"])
        self.assertIn("有理数加法", gap["detail"])

    def test_error_pattern_type(self):
        s = _make_student()
        s.gaps.append(
            Gap(topic_id="6a_jiafa", status="recurring", category="calc_sign", occurrence_count=3)
        )
        insights = _generate_insights(s, [], [])
        types = [i["type"] for i in insights]
        self.assertIn("error_pattern", types)
        err = [i for i in insights if i["type"] == "error_pattern"][0]
        self.assertIn("符号错误", err["title"])
        self.assertIn("3 次", err["detail"])

    def test_time_change_type(self):
        s = _make_student()
        this_week = [SessionSummary(date=date.today().isoformat(), duration_minutes=30)]
        last_week = [
            SessionSummary(date=(date.today() - timedelta(days=7)).isoformat(), duration_minutes=10)
        ]
        insights = _generate_insights(s, this_week, last_week)
        self.assertIn("time_change", [i["type"] for i in insights])

    def test_streak_type(self):
        s = _make_student()
        s.streak_chain = 7
        insights = _generate_insights(s, [], [])
        self.assertIn("streak", [i["type"] for i in insights])


class SuggestionsTest(unittest.TestCase):
    def test_prioritize_gap(self):
        s = _make_student()
        s.gaps.append(
            Gap(topic_id="6a_jiafa", topic_name="有理数加法", type="concept", status="open")
        )
        suggestions = _generate_suggestions(s)
        self.assertTrue(suggestions)
        self.assertIn("有理数加法", suggestions[0])

    def test_capped_at_three(self):
        s = _make_student()
        s.gaps.append(
            Gap(topic_id="6a_jiafa", topic_name="有理数加法", type="concept", status="open")
        )
        s.cognitive_profile.abstract_thinking = 0.2
        s.streak_chain = 0
        self.assertLessEqual(len(_generate_suggestions(s)), 3)


class SkipAlertsTest(unittest.TestCase):
    def test_skip_alerts(self):
        s = _make_student()
        s.skipped_topics = {"6a_jiafa": 3, "6a_chengfa": 1}
        alerts = _skip_alerts(s)
        self.assertEqual(len(alerts), 1)
        self.assertIn("有理数加法", alerts[0])

    def test_skip_alerts_capped_at_three(self):
        s = _make_student()
        s.skipped_topics = {
            "6a_jiafa": 3,
            "6a_chengfa": 3,
            "6a_chufa": 3,
            "6a_jianfa": 3,
        }
        self.assertLessEqual(len(_skip_alerts(s)), 3)


if __name__ == "__main__":
    unittest.main()
