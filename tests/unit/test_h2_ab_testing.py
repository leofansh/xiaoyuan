"""A/B 测试框架通用化单元测试（架构优化 P3 项 H2）。

用标准库 unittest + unittest.mock，无需 pytest / FastAPI / 网络。
覆盖：
- get_variant 确定性分组（同学生同实验同组恒定）
- 分组分布（多学生至少出现 A/B 两组）
- get_ab_test_group 未启用时返回 "" 且不改档案
- config ab_test 规范化（非法值回退默认）
- ApiKeyUpdate 模型带 ab_test 字段可解析
"""

import unittest
from unittest.mock import patch

from backend import config
from backend.main import ApiKeyUpdate
from backend.models.student import Student
from backend.services.ab_testing import ABTest, get_ab_test_group, get_variant


def _make_student(student_id: str = "test") -> Student:
    return Student(id=student_id, name="小明")


class GetVariantTest(unittest.TestCase):
    def test_deterministic_same_student_same_group(self):
        """① 确定性：同一学生同一实验多次调用结果恒定，且始终落在 A/B。"""
        for i in range(50):
            sid = f"stu_{i}"
            for test_id in ("opening", "strategy_prompt"):
                first = get_variant(sid, test_id)
                self.assertIn(first, ("A", "B"))
                for _ in range(3):
                    self.assertEqual(get_variant(sid, test_id), first)

    def test_distribution_has_both_groups(self):
        """② 分布：10 名学生至少出现 A 与 B（否则哈希实现有问题）。"""
        variants = {get_variant(f"stu_{i}", "opening") for i in range(10)}
        self.assertIn("A", variants)
        self.assertIn("B", variants)


class GetAbTestGroupTest(unittest.TestCase):
    def test_disabled_returns_empty_and_no_mutation(self):
        """③ 未启用时返回 "" 且不改动学生档案。"""
        s = _make_student("stu_unchanged")
        disabled = {"enabled": False, "variant_a_ratio": 0.5}
        with patch("backend.services.ab_testing.get_ab_test_config", return_value=disabled):
            group = get_ab_test_group(s)
        self.assertEqual(group, "")
        self.assertEqual(s.ab_test_group, "")

    def test_enabled_lazy_assign_stable(self):
        """已启用且未分组 → 惰性分配并写回；再次调用不重新哈希（分组固定）。"""
        s = _make_student("stu_lazy")
        enabled = {"enabled": True, "variant_a_ratio": 0.5}
        with patch("backend.services.ab_testing.get_ab_test_config", return_value=enabled):
            first = get_ab_test_group(s)
            second = get_ab_test_group(s)
        self.assertIn(first, ("A", "B"))
        self.assertEqual(first, second)
        self.assertEqual(s.ab_test_group, first)


class ConfigNormalizeTest(unittest.TestCase):
    def test_ab_test_normalization_invalid_falls_back(self):
        """④ 规范化：非法/越界值回退默认，合法值原样保留。"""
        default = {"enabled": False, "variant_a_ratio": 0.5}
        self.assertEqual(config._normalize_ab_test(None), default)
        self.assertEqual(config._normalize_ab_test("not-a-dict"), default)
        self.assertEqual(
            config._normalize_ab_test({"enabled": True, "variant_a_ratio": 0.8}),
            {"enabled": True, "variant_a_ratio": 0.8},
        )
        # 越界比例（<=0 或 >=1）回退默认
        for bad_ratio in (0.0, 1.0, 1.5, -0.1, "abc"):
            self.assertEqual(
                config._normalize_ab_test({"enabled": True, "variant_a_ratio": bad_ratio}),
                {"enabled": True, "variant_a_ratio": 0.5},
            )
        # 缺 key 用默认
        self.assertEqual(
            config._normalize_ab_test({"enabled": True}),
            {"enabled": True, "variant_a_ratio": 0.5},
        )


class ApiKeyUpdateModelTest(unittest.TestCase):
    def test_ab_test_field_parses(self):
        """⑤ ApiKeyUpdate 带 ab_test 字段可解析；缺省为 None。"""
        payload = ApiKeyUpdate(ab_test={"enabled": True, "variant_a_ratio": 0.3})
        self.assertIsNotNone(payload.ab_test)
        self.assertEqual(payload.ab_test["enabled"], True)
        self.assertEqual(payload.ab_test["variant_a_ratio"], 0.3)

        empty = ApiKeyUpdate()
        self.assertIsNone(empty.ab_test)
        self.assertEqual(empty.api_key, "")


class ABTestModelTest(unittest.TestCase):
    def test_model_fields_and_defaults(self):
        """ABTest 模型字段与默认值符合文档 H2 定义。"""
        test = ABTest(
            id="opening",
            name="兴趣引入开场",
            description="对比兴趣引入开场与传统开场",
            variant_a={"opening": "interest"},
            variant_b={"opening": "traditional"},
            metrics=["duration", "completion", "active_open"],
            start_date="2026-09-19",
        )
        self.assertEqual(test.end_date, "")
        self.assertTrue(test.active)
        self.assertEqual(test.id, "opening")
        self.assertEqual(get_variant("stu_x", test.id), get_variant("stu_x", test.id))


if __name__ == "__main__":
    unittest.main()
