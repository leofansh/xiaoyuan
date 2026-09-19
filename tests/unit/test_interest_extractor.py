"""兴趣提取与兴趣 → 数学情境映射单元测试（架构优化 C3 + 规格 13.7.3）。

用标准库 unittest，无需 pytest / FastAPI / 网络。
覆盖 INTEREST_MATH_CONTEXTS 映射（匹配/不匹配不强行关联）、兴趣提取去重、
挫败时不强行用兴趣情境、趣味化模板填充与按知识点取模板。
"""

import unittest

from backend.models.student import Student
from backend.services.interest_extractor import (
    INTEREST_MATH_CONTEXTS,
    OPENING_PROBLEMS,
    _fill_templates,
    extract_interests,
    get_math_context_for_interest,
    get_opening_problem,
    get_topic_templates,
    should_use_interest_context,
)


def _make_student(interests=None, consecutive_wrong: int = 0) -> Student:
    s = Student(id="test", name="小明")
    s.interests = interests or []
    s.current_session.consecutive_wrong = consecutive_wrong
    return s


class MathContextTest(unittest.TestCase):
    def test_matching_topic_returns_context(self):
        ctx = get_math_context_for_interest("烘焙", "比例")
        self.assertEqual(ctx, INTEREST_MATH_CONTEXTS["烘焙"]["contexts"][0])
        self.assertIn("面粉", ctx)

    def test_mismatched_topic_returns_none(self):
        self.assertIsNone(get_math_context_for_interest("烘焙", "概率"))

    def test_unknown_interest_returns_none(self):
        self.assertIsNone(get_math_context_for_interest("编程", "概率"))

    def test_no_topic_returns_first_context(self):
        self.assertEqual(
            get_math_context_for_interest("音乐", ""),
            INTEREST_MATH_CONTEXTS["音乐"]["contexts"][0],
        )

    def test_all_interests_have_at_least_five_contexts(self):
        for interest, info in INTEREST_MATH_CONTEXTS.items():
            self.assertGreaterEqual(
                len(info["contexts"]), 5,
                f"{interest} 应有至少 5 条情境，当前 {len(info['contexts'])} 条",
            )

    def test_new_contexts_reachable_for_matching_topic(self):
        for interest in ("烘焙", "游戏"):
            info = INTEREST_MATH_CONTEXTS[interest]
            topic = info["topics"][0]
            self.assertIsNotNone(get_math_context_for_interest(interest, topic))
            new_contexts = info["contexts"][3:5]
            self.assertEqual(len(new_contexts), 2)
            for ctx in new_contexts:
                self.assertTrue(ctx.strip().endswith("？"), f"{interest} 新情境应以问号结尾")


class ExtractInterestsTest(unittest.TestCase):
    def test_extract_new_interests(self):
        self.assertEqual(extract_interests("我喜欢烘焙，平时也画画", []), ["烘焙", "画画"])

    def test_dedup_existing(self):
        self.assertEqual(extract_interests("我最近在烘焙", ["烘焙"]), [])

    def test_empty_message(self):
        self.assertEqual(extract_interests("", []), [])


class ShouldUseInterestContextTest(unittest.TestCase):
    def test_returns_interest_when_matched(self):
        s = _make_student(interests=["烘焙"])
        self.assertEqual(should_use_interest_context(s, "比例"), "烘焙")

    def test_none_when_no_interests(self):
        self.assertIsNone(should_use_interest_context(_make_student(), "比例"))

    def test_none_when_frustrated(self):
        s = _make_student(interests=["烘焙"], consecutive_wrong=2)
        self.assertIsNone(should_use_interest_context(s, "比例"))

    def test_none_when_topic_mismatched(self):
        s = _make_student(interests=["烘焙"])
        self.assertIsNone(should_use_interest_context(s, "概率"))


class TopicTemplatesTest(unittest.TestCase):
    def test_fill_templates_deterministic(self):
        templates = ["{兴趣}用了{数字}克糖", "{数字}+{数字}"]
        filled1 = _fill_templates(templates, "游戏", seed=42)
        filled2 = _fill_templates(templates, "游戏", seed=42)
        self.assertEqual(filled1, filled2)
        self.assertIn("游戏", filled1[0])
        self.assertNotIn("{", filled1[0])

    def test_fill_templates_neutral_fallback(self):
        filled = _fill_templates(["{兴趣}商店"], "", seed=1)
        self.assertIn("生活里", filled[0])

    def test_get_topic_templates_exact_match(self):
        templates = get_topic_templates("分数运算", "烘焙")
        self.assertTrue(templates)
        self.assertTrue(all("{" not in t for t in templates))
        self.assertIn("烘焙", templates[0])

    def test_get_topic_templates_contains_match(self):
        templates = get_topic_templates("分数", "烘焙")
        self.assertTrue(templates)

    def test_get_topic_templates_no_match(self):
        self.assertEqual(get_topic_templates("", ""), [])


class OpeningProblemTest(unittest.TestCase):
    def test_unknown_interest_falls_back_to_first(self):
        self.assertEqual(get_opening_problem("不存在的兴趣"), OPENING_PROBLEMS["烘焙"][0])


if __name__ == "__main__":
    unittest.main()
