"""10 大数学思维模型库（thinking_models）单元测试。

覆盖规格 C2：模型库完整性、查询、知识点映射、确定性触发规则优先级
（错误类型 > 连续错 > 认知偏好 > 教学状态 > 兜底最弱项）、掌握度最低项选择。
纯标准库 unittest，无 LLM / 网络（兜底路径仅读本地知识图谱）。
"""

import unittest

from backend.agent.thinking_models import (
    ERROR_TYPE_MODEL_MAP,
    PREFERENCE_MODEL_MAP,
    STATE_MODEL_MAP,
    THINKING_MODELS,
    ThinkingModel,
    _pick_weakest,
    get_model,
    models_for_topic,
    select_thinking_model,
)


class ThinkingModelRegistryTest(unittest.TestCase):
    def test_ten_models_registered(self):
        self.assertEqual(len(THINKING_MODELS), 10)
        for mid, model in THINKING_MODELS.items():
            self.assertEqual(mid, model.id)
            self.assertIsInstance(model, ThinkingModel)

    def test_get_model_known_unknown(self):
        model = get_model("reverse")
        self.assertIsNotNone(model)
        self.assertEqual(model.name, "逆向思维")
        self.assertIsNone(get_model("not_a_model"))


class ThinkingModelTopicTest(unittest.TestCase):
    def test_models_for_topic(self):
        models = models_for_topic("一元一次方程")
        ids = {m.id for m in models}
        self.assertIn("reverse", ids)
        self.assertIn("verification", ids)
        self.assertGreaterEqual(len(models), 1)
        for m in models:
            self.assertIn("一元一次方程", m.typical_topics)

    def test_models_for_unknown_topic_empty(self):
        self.assertEqual(models_for_topic("不存在的知识点"), [])


class ThinkingModelSelectTest(unittest.TestCase):
    def test_error_type_priority(self):
        # 错误类型驱动优先级最高：careless → 检验思维
        self.assertEqual(
            select_thinking_model("6a_jiafa", error_type="careless", state="QUICK_REVIEW"),
            "verification",
        )
        self.assertEqual(select_thinking_model("6a_jiafa", error_type="reading"), "modeling")
        self.assertIn(
            select_thinking_model("6a_jiafa", error_type="concept"),
            {"visualization", "analogy"},
        )

    def test_consecutive_wrong_overrides_preference(self):
        # 连续错(≥2)优先于认知偏好：应选连续错候选中的最弱项，而非偏好项
        result = select_thinking_model(
            "6a_jiafa",
            consecutive_wrong=2,
            learning_preference="visual",
            thinking_model_mastery={"visualization": 0.9, "analogy": 0.8, "decomposition": 0.1},
        )
        self.assertEqual(result, "decomposition")

    def test_preference_driven(self):
        self.assertEqual(
            select_thinking_model("6a_jiafa", learning_preference="visual"),
            "visualization",
        )

    def test_state_driven(self):
        self.assertEqual(
            select_thinking_model("6a_jiafa", state="QUICK_REVIEW"),
            "verification",
        )

    def test_fallback_weakest_by_topic(self):
        # 无其它信号时兜底到知识点声明的思维模型最弱项
        self.assertEqual(select_thinking_model("6a_fangcheng_jie"), "transformation")
        self.assertEqual(
            select_thinking_model(
                "6a_fangcheng_jie",
                thinking_model_mastery={"transformation": 0.9, "reverse": 0.1},
            ),
            "reverse",
        )

    def test_unknown_topic_returns_none(self):
        self.assertIsNone(select_thinking_model("不存在的知识点"))

    def test_pick_weakest_uses_mastery(self):
        self.assertEqual(
            _pick_weakest(["reverse", "verification"], {"reverse": 0.8, "verification": 0.2}),
            "verification",
        )


class ThinkingModelMapsTest(unittest.TestCase):
    def test_all_mapped_models_valid(self):
        for mapping in (ERROR_TYPE_MODEL_MAP, PREFERENCE_MODEL_MAP, STATE_MODEL_MAP):
            for ids in mapping.values():
                for mid in ids:
                    self.assertIn(mid, THINKING_MODELS, f"未知模型 id: {mid}")


if __name__ == "__main__":
    unittest.main()
