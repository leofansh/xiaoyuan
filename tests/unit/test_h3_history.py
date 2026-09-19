"""H3「对话历史 token 管理」单元测试（架构优化 P3）。

用标准库 unittest，无需 pytest / FastAPI / 网络 / tokenizer。
覆盖七项验收：
  1. estimate_tokens 空串=0、中英文混合估算 >0 且单调
  2. ≤20 轮 + 小 token 原样返回
  3. 超过 20 轮 → 结果轮数 ≤ max_turns 且保留最近轮
  4. 超 token 预算 → 被裁剪且总估算 ≤ max_tokens（允许摘要常数略超容差）
  5. 极端超长单条 → 生成摘要块且 role="assistant"、内容非空
  6. 摘要块截断不抛异常
  7. 裁剪结果不含 role="system"
"""

import unittest

from backend.services.history_manager import (
    build_summary_block,
    estimate_history_tokens,
    estimate_tokens,
    trim_history,
)


def _make_history(turns: int, user_text: str = "老师，这道题怎么做？", assistant_text: str = "我们先看已知条件。") -> list[dict]:
    """构造 turns 轮 user/assistant 交替历史。"""
    h: list[dict] = []
    for i in range(turns):
        h.append({"role": "user", "content": f"{user_text}（第{i}轮）"})
        h.append({"role": "assistant", "content": f"{assistant_text}（第{i}轮）"})
    return h


def _count_turns(history: list[dict]) -> int:
    return sum(1 for m in history if m.get("role") == "user")


class EstimateTokensTest(unittest.TestCase):
    def test_empty_string_returns_zero(self):
        self.assertEqual(estimate_tokens(""), 0)

    def test_mixed_text_positive_and_monotonic(self):
        """中英文混合估算 >0，且文本越长估算越大（只验单调性，不锁死精确值）。"""
        zh = "中文内容测试"
        en = "hello world 123"
        mixed = "中文 hello 123"
        self.assertGreater(estimate_tokens(zh), 0)
        self.assertGreater(estimate_tokens(en), 0)
        self.assertGreater(estimate_tokens(mixed), 0)
        self.assertGreater(estimate_tokens(zh * 2), estimate_tokens(zh))
        self.assertGreater(estimate_tokens(mixed * 2), estimate_tokens(mixed))


class SmallHistoryUntouchedTest(unittest.TestCase):
    def test_within_budget_returns_as_is(self):
        """10 轮 + 小 token：原样返回（内容与顺序一致）。"""
        h = _make_history(10)
        result = trim_history(h, max_turns=20, max_tokens=6000)
        self.assertEqual(result, h)


class OverTurnsTest(unittest.TestCase):
    def test_over_turns_keeps_recent(self):
        """超过 20 轮 → 结果轮数 ≤ max_turns 且保留最近轮。"""
        h = _make_history(30)
        result = trim_history(h, max_turns=20, max_tokens=6000, min_recent_turns=4)
        self.assertLessEqual(_count_turns(result), 20)
        # 最近一轮的内容保留（末尾两条为最后一轮 user/assistant）
        self.assertEqual(result[-1]["content"], h[-1]["content"])
        self.assertEqual(result[-2]["content"], h[-2]["content"])


class OverTokensTest(unittest.TestCase):
    def test_over_tokens_trimmed_under_budget(self):
        """超 token 预算 → 被裁剪且总估算 token ≤ max_tokens（留容差）。"""
        # 每条 user 消息 200 个「中文」→ 约 240 token，25 轮总 token 超预算
        user_text = "中文" * 200
        h = _make_history(25, user_text=user_text)
        self.assertGreater(estimate_history_tokens(h), 6000)

        result = trim_history(h, max_turns=20, max_tokens=6000, min_recent_turns=4)
        self.assertLess(len(result), len(h))
        self.assertLessEqual(_count_turns(result), 20)
        # 允许 +MESSAGE_OVERHEAD 级别的估算误差
        self.assertLessEqual(estimate_history_tokens(result), 6000 + 8)


class ExtremeLongMessageTest(unittest.TestCase):
    def test_extreme_single_message_generates_summary(self):
        """极端超长单条 → 生成摘要块且 role="assistant"、内容非空。"""
        h = []
        for i in range(60):
            content = "甲" * 30000 if i == 59 else f"第{i}轮的问题"
            h.append({"role": "user", "content": content})
            h.append({"role": "assistant", "content": f"第{i}轮的解答"})

        result = trim_history(h, max_turns=20, max_tokens=6000, min_recent_turns=4)
        self.assertEqual(result[0]["role"], "assistant")
        self.assertTrue(result[0]["content"])
        self.assertTrue(result[0]["content"].startswith("[早前对话摘要]"))


class SummaryTruncationTest(unittest.TestCase):
    def test_summary_truncation_does_not_raise(self):
        """摘要块截断（含极小/零/负上限）不抛异常。"""
        h = _make_history(5)
        for cap in (None, 0, -5, 1, 10, 1000):
            text = build_summary_block(h, max_chars=cap)
            self.assertIsInstance(text, str)

    def test_empty_history_returns_empty_summary(self):
        self.assertEqual(build_summary_block([]), "")


class NoSystemRoleTest(unittest.TestCase):
    def test_result_has_no_system_role(self):
        """裁剪结果不含 role="system"（不涉及 system_prompt 位置）。"""
        h = _make_history(40, user_text="中文" * 100)
        result = trim_history(h, max_turns=20, max_tokens=6000)
        for msg in result:
            self.assertNotEqual(msg.get("role"), "system")


if __name__ == "__main__":
    unittest.main()
