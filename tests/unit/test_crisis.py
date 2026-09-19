"""心理危机检测与干预（crisis）单元测试。

覆盖规格 §安全红线四级分类：severe 直接触发、moderate/implicit 需上下文、
support 关怀流程、轻度情绪不误判（"今天好累"不触发）、游戏语境排除（A4）、
干预话术与事件记录。
纯标准库 unittest，无 LLM / 网络。
"""

import unittest

from backend.services.crisis import (
    _is_game_report,
    crisis_intervention,
    detect_crisis,
    record_crisis,
)


class _FakeStudent:
    def __init__(self, name="小明"):
        self.name = name

    def today_iso(self):
        return "2026-09-19"


class CrisisSevereTest(unittest.TestCase):
    def test_empty_message_returns_none(self):
        self.assertIsNone(detect_crisis(""))
        self.assertIsNone(detect_crisis(None))

    def test_severe_keyword_triggers(self):
        self.assertEqual(detect_crisis("我觉得活着没意思"), "severe")

    def test_severe_want_to_die_triggers(self):
        self.assertEqual(detect_crisis("我不想活了"), "severe")


class CrisisModerateContextTest(unittest.TestCase):
    def test_moderate_without_context_not_triggered(self):
        self.assertIsNone(detect_crisis("我快撑不住了"))

    def test_moderate_with_context_triggered(self):
        self.assertEqual(
            detect_crisis("我快撑不住了", {"consecutive_negative_turns": 2}),
            "moderate",
        )

    def test_moderate_below_threshold_not_triggered(self):
        self.assertIsNone(
            detect_crisis("我绝望了", {"consecutive_negative_turns": 1})
        )

    def test_implicit_without_context_not_triggered(self):
        self.assertIsNone(detect_crisis("明天见不到我了"))

    def test_implicit_with_context_triggered(self):
        self.assertEqual(
            detect_crisis("我要是消失了就好了", {"consecutive_negative_turns": 3}),
            "moderate",
        )


class CrisisNoFalsePositiveTest(unittest.TestCase):
    def test_mild_emotion_not_crisis(self):
        self.assertIsNone(detect_crisis("今天好累"))
        self.assertIsNone(detect_crisis("好烦啊"))
        self.assertIsNone(detect_crisis("我不想上学了"))

    def test_game_context_excluded(self):
        # 含"想死"但明确是游戏语境（≥2 个游戏词），不视为危机
        self.assertIsNone(detect_crisis("王者荣耀排位输了，我真想死"))

    def test_single_game_word_not_excluded(self):
        # 仅一个游戏词不足以判定游戏语境，危机词仍应触发
        self.assertEqual(detect_crisis("这个游戏我想死了"), "severe")

    def test_game_report_dedup(self):
        # "打游戏" 命中后其子串 "游戏" 不重复计数
        self.assertFalse(_is_game_report("打游戏"))
        self.assertTrue(_is_game_report("打游戏排位"))


class CrisisSupportTest(unittest.TestCase):
    def test_bullying_support(self):
        self.assertEqual(detect_crisis("同学总被欺负"), "support")

    def test_family_support(self):
        self.assertEqual(detect_crisis("爸妈吵架了"), "support")


class CrisisInterventionTest(unittest.TestCase):
    def test_severe_intervention_has_hotline(self):
        text = crisis_intervention("severe")
        self.assertIn("400-161-9995", text)

    def test_moderate_intervention(self):
        self.assertIn("压力好大", crisis_intervention("moderate"))

    def test_support_intervention(self):
        self.assertIn("告诉信任的大人", crisis_intervention("support"))

    def test_unknown_level_empty(self):
        self.assertEqual(crisis_intervention("nope"), "")


class CrisisRecordTest(unittest.TestCase):
    def test_record_severe_appends_event_and_risk(self):
        s = _FakeStudent("小红")
        risks = record_crisis(s, "severe", "我不想活了")
        self.assertEqual(len(s.crisis_events), 1)
        self.assertEqual(s.crisis_events[0]["level"], "severe")
        self.assertEqual(s.crisis_events[0]["date"], "2026-09-19")
        self.assertEqual(len(risks), 1)
        self.assertIn("小红", risks[0])

    def test_record_truncates_long_message(self):
        s = _FakeStudent("小明")
        record_crisis(s, "support", "长" * 300)
        self.assertEqual(len(s.crisis_events[0]["message"]), 200)

    def test_record_support_info_level(self):
        s = _FakeStudent("小明")
        risks = record_crisis(s, "support", "被欺负")
        self.assertTrue(risks[0].startswith("ℹ️"))


if __name__ == "__main__":
    unittest.main()
