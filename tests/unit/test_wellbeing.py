"""防沉迷（认知负荷感知 + 分级休息提醒）单元测试（架构优化 F2 + I2）。

用标准库 unittest + unittest.mock，无需 pytest / FastAPI / 网络。
覆盖：
  - estimate_cognitive_load 各分项贡献与封顶（连续错误 0.15 步进封顶 0.45、
    状态停留 0.05 步进封顶 0.3、掌握度、负面情绪 0.05 步进封顶 0.15、总分封顶 1.0）
  - today_minutes 仅统计今日会话
  - check_break_needed 三档（高负荷 25 / 中负荷 40 / 常规 60）分钟数与休息文案
  - check_time_limit 优先级：夜间 > 认知负荷休息建议 > 每日上限
  - YAML 缺失时三档阈值回退代码常量默认值（I2 兜底路径）
"""

import unittest
from datetime import date, datetime
from unittest.mock import patch

from backend.models.student import MasteryRecord, SessionSummary, Student
from backend.services import wellbeing


def _make_student(
    consecutive_wrong: int = 0,
    turns: int = 0,
    topic_id: str = "",
    mastery: float = 0.0,
    negative: int = 0,
    minutes: int = 0,
) -> Student:
    s = Student(id="test", name="小明")
    s.current_session.consecutive_wrong = consecutive_wrong
    s.current_session.turns_in_current_state = turns
    s.current_session.topic_id = topic_id
    s.current_session.consecutive_negative_turns = negative
    if topic_id:
        s.mastery[topic_id] = MasteryRecord(score=mastery)
    if minutes:
        s.session_history.append(
            SessionSummary(date=date.today().isoformat(), duration_minutes=minutes)
        )
    return s


def _fake_now(hour: int):
    class _FakeDatetime:
        @staticmethod
        def now():
            return datetime(2026, 9, 19, hour, 0, 0)

    return _FakeDatetime


class EstimateCognitiveLoadTest(unittest.TestCase):
    def test_consecutive_wrong_step_and_cap(self):
        self.assertAlmostEqual(
            wellbeing.estimate_cognitive_load(_make_student(consecutive_wrong=2)), 0.3
        )
        self.assertAlmostEqual(
            wellbeing.estimate_cognitive_load(_make_student(consecutive_wrong=5)), 0.45
        )

    def test_turns_in_state_step_and_cap(self):
        self.assertAlmostEqual(wellbeing.estimate_cognitive_load(_make_student(turns=2)), 0.1)
        self.assertAlmostEqual(wellbeing.estimate_cognitive_load(_make_student(turns=8)), 0.3)

    def test_mastery_contribution_and_no_topic(self):
        self.assertAlmostEqual(
            wellbeing.estimate_cognitive_load(_make_student(topic_id="6a_jiafa", mastery=0.5)), 0.1
        )
        self.assertAlmostEqual(wellbeing.estimate_cognitive_load(_make_student()), 0.0)

    def test_negative_turns_step_and_cap(self):
        self.assertAlmostEqual(wellbeing.estimate_cognitive_load(_make_student(negative=2)), 0.1)
        self.assertAlmostEqual(wellbeing.estimate_cognitive_load(_make_student(negative=4)), 0.15)

    def test_total_capped_at_one(self):
        s = _make_student(
            consecutive_wrong=5, turns=10, topic_id="6a_jiafa", mastery=0.0, negative=10
        )
        self.assertEqual(wellbeing.estimate_cognitive_load(s), 1.0)


class TodayMinutesTest(unittest.TestCase):
    def test_sums_only_today_sessions(self):
        s = Student(id="test", name="小明")
        today = date.today().isoformat()
        s.session_history.append(SessionSummary(date=today, duration_minutes=15))
        s.session_history.append(SessionSummary(date=today, duration_minutes=10))
        s.session_history.append(SessionSummary(date="2020-01-01", duration_minutes=99))
        self.assertEqual(wellbeing.today_minutes(s), 25)


class CheckBreakNeededTest(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(wellbeing, "load_prompts", return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_high_load_break_message(self):
        msg = wellbeing.check_break_needed(_make_student(consecutive_wrong=5, turns=8, minutes=25))
        self.assertIn("25分钟", msg)
        self.assertIn("休息5分钟", msg)
        self.assertIn("站起来走走", msg)

    def test_medium_load_break_message(self):
        msg = wellbeing.check_break_needed(_make_student(consecutive_wrong=2, turns=1, minutes=40))
        self.assertIn("40分钟", msg)
        self.assertIn("喝口水", msg)

    def test_low_load_daily_end_message(self):
        msg = wellbeing.check_break_needed(_make_student(minutes=60))
        self.assertIn("今天到这里吧", msg)

    def test_no_break_when_under_threshold(self):
        self.assertIsNone(wellbeing.check_break_needed(_make_student(consecutive_wrong=1, minutes=10)))


class CheckTimeLimitTest(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(wellbeing, "load_prompts", return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_night_takes_priority_over_break(self):
        s = _make_student(consecutive_wrong=5, turns=8, minutes=25)
        with patch.object(wellbeing, "datetime", _fake_now(23)):
            self.assertIn("该睡觉了", wellbeing.check_time_limit(s))

    def test_early_morning_is_night(self):
        with patch.object(wellbeing, "datetime", _fake_now(5)):
            self.assertIn("该睡觉了", wellbeing.check_time_limit(_make_student()))

    def test_daytime_returns_break_hint(self):
        s = _make_student(consecutive_wrong=5, turns=8, minutes=25)
        with patch.object(wellbeing, "datetime", _fake_now(15)):
            self.assertIn("休息5分钟", wellbeing.check_time_limit(s))

    def test_daytime_daily_reminder_and_no_message(self):
        s = _make_student(minutes=50)
        with patch.object(wellbeing, "datetime", _fake_now(15)):
            self.assertIn("50 分钟", wellbeing.check_time_limit(s))
        with patch.object(wellbeing, "datetime", _fake_now(15)):
            self.assertIsNone(wellbeing.check_time_limit(_make_student(minutes=10)))


class WellbeingThresholdsTest(unittest.TestCase):
    def test_defaults_without_yaml_and_override(self):
        with patch.object(wellbeing, "load_prompts", return_value={}):
            self.assertEqual(
                wellbeing._break_thresholds(),
                {"high": 25, "normal": 40, "max_daily": 60},
            )
        with patch.object(
            wellbeing,
            "load_prompts",
            return_value={"wellbeing": {"high_load_break_minutes": 30}},
        ):
            t = wellbeing._break_thresholds()
        self.assertEqual(t["high"], 30)
        self.assertEqual(t["normal"], 40)
        self.assertEqual(t["max_daily"], 60)


if __name__ == "__main__":
    unittest.main()
