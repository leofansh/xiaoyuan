"""内容安全过滤（ContentFilter）单元测试。

覆盖规格 §安全红线：不适合内容直接拦截、敏感话题转专门引导、正常数学内容放行、
拦截/敏感计数、单例与便捷入口、不适合关键词优先级高于敏感话题。
纯标准库 unittest，无 LLM / 网络。
"""

import unittest

from backend.services.content_filter import (
    ContentFilter,
    filter_llm_output,
    get_content_filter,
)


class ContentFilterBlockTest(unittest.TestCase):
    def setUp(self):
        self.cf = ContentFilter()

    def test_empty_text_passthrough(self):
        text, flagged = self.cf.filter_output("")
        self.assertEqual(text, "")
        self.assertFalse(flagged)

    def test_normal_math_passthrough(self):
        text, flagged = self.cf.filter_output("2+3=5，所以答案是 5")
        self.assertEqual(text, "2+3=5，所以答案是 5")
        self.assertFalse(flagged)

    def test_inappropriate_keyword_blocked(self):
        text, flagged = self.cf.filter_output("给你看个色情网站")
        self.assertTrue(flagged)
        self.assertEqual(text, self.cf._safe_response())

    def test_suicide_method_blocked(self):
        _, flagged = self.cf.filter_output("自杀方式有哪些")
        self.assertTrue(flagged)

    def test_sensitive_politics_guided(self):
        text, flagged = self.cf.filter_output("我们聊聊政治吧")
        self.assertTrue(flagged)
        self.assertEqual(text, self.cf._sensitive_topic_response("politics"))

    def test_sensitive_violence_guided(self):
        text, flagged = self.cf.filter_output("今天有人打架斗殴")
        self.assertTrue(flagged)
        self.assertIn("家长和老师", text)

    def test_sensitive_dark_guided(self):
        text, flagged = self.cf.filter_output("讲个鬼故事")
        self.assertTrue(flagged)
        self.assertEqual(text, self.cf._sensitive_topic_response("dark"))

    def test_inappropriate_priority_over_sensitive(self):
        # "暴力" 同时可命中不适合关键词，应先于敏感话题被直接拦截
        text, flagged = self.cf.filter_output("暴力和政治")
        self.assertTrue(flagged)
        self.assertEqual(text, self.cf._safe_response())
        self.assertNotEqual(text, self.cf._sensitive_topic_response("violence"))


class ContentFilterStatsTest(unittest.TestCase):
    def test_stats_counting(self):
        cf = ContentFilter()
        self.assertEqual(cf._stats, {"blocked": 0, "sensitive": 0})
        cf.filter_output("毒品不能碰")
        self.assertEqual(cf._stats["blocked"], 1)
        cf.filter_output("关于政府你怎么看")
        self.assertEqual(cf._stats["blocked"], 1)
        self.assertEqual(cf._stats["sensitive"], 1)


class ContentFilterGlobalTest(unittest.TestCase):
    def test_singleton(self):
        self.assertIs(get_content_filter(), get_content_filter())

    def test_filter_llm_output_convenience(self):
        text, flagged = filter_llm_output("淫秽内容")
        self.assertTrue(flagged)
        self.assertEqual(text, get_content_filter()._safe_response())


if __name__ == "__main__":
    unittest.main()
