"""I2「配置化管理」单元测试（架构优化 P3/I2）。

用标准库 unittest + unittest.mock，无需 pytest / FastAPI / 网络。
覆盖：
  1. load_prompts 返回 dict 且含顶层键
  2. YAML 缺失 / 损坏时返回 {} 不抛异常
  3. strategy_params 白名单规范化（非法类型/未知键被丢弃，下游回默认）
  4. wellbeing 三档分钟数读取与默认兜底一致
  5. 无 YAML 时 persona / strategy / wellbeing 行为不变（默认兜底路径）
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import config as config_module
from backend.agent import persona
from backend.agent import state_engine
from backend.agent import strategy_engine
from backend.models.student import Student
from backend.services import wellbeing


def _reset_prompts_cache() -> None:
    """清空 load_prompts 进程内缓存，确保下一次调用重新读取文件。"""
    config_module._PROMPTS_CACHE = {}
    config_module._PROMPTS_CACHE_MTIME = -1.0


def _write_temp_yaml(content: str) -> Path:
    """写一个临时 YAML 文件并返回路径（调用方负责清理）。"""
    f = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
    try:
        f.write(content)
    finally:
        f.close()
    return Path(f.name)


class LoadPromptsTest(unittest.TestCase):
    def setUp(self) -> None:
        _reset_prompts_cache()

    def test_returns_dict_with_top_level_keys(self):
        """① load_prompts 返回 dict 且含全部顶层键。"""
        data = config_module.load_prompts()
        self.assertIsInstance(data, dict)
        for key in (
            "system_prompt",
            "mode_a_prompt",
            "mode_b_prompt",
            "mode_weekend_prompt",
            "strategy_params",
            "wellbeing",
        ):
            self.assertIn(key, data)

    def test_missing_file_returns_empty_dict(self):
        """② YAML 缺失时返回 {} 且不抛异常。"""
        missing = Path(tempfile.gettempdir()) / "no_such_prompts_12345.yaml"
        with patch.object(config_module, "_PROMPTS_FILE", missing):
            _reset_prompts_cache()
            self.assertEqual(config_module.load_prompts(), {})

    def test_corrupt_file_returns_empty_dict(self):
        """② YAML 损坏（解析失败）时返回 {} 且不抛异常。"""
        path = _write_temp_yaml(": not: valid: yaml: {{{{\n")
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        with patch.object(config_module, "_PROMPTS_FILE", path):
            _reset_prompts_cache()
            self.assertEqual(config_module.load_prompts(), {})


class StrategyParamsNormalizationTest(unittest.TestCase):
    def setUp(self) -> None:
        _reset_prompts_cache()

    def test_illegal_type_dropped_and_falls_back_to_default(self):
        """③ strategy_params 白名单规范化：非法类型（字符串数字）回默认。"""
        yaml_text = (
            "strategy_params:\n"
            "  max_consecutive_wrong_analogy: \"2\"\n"  # 字符串数字 → 非法，丢弃
            "  mastery_threshold: 0.9\n"                # 合法，保留
            "  unknown_key: 5\n"                        # 未知键 → 丢弃
        )
        path = _write_temp_yaml(yaml_text)
        self.addCleanup(lambda: path.unlink(missing_ok=True))

        with patch.object(config_module, "_PROMPTS_FILE", path):
            _reset_prompts_cache()
            sp = config_module.load_prompts()["strategy_params"]
            self.assertNotIn("max_consecutive_wrong_analogy", sp)
            self.assertNotIn("unknown_key", sp)
            self.assertEqual(sp["mastery_threshold"], 0.9)
            # 下游按代码常量兜底默认值
            self.assertEqual(
                strategy_engine._strategy_thresholds()["consecutive_wrong_analogy"], 2
            )
            self.assertEqual(
                strategy_engine._strategy_thresholds()["mastery_threshold"], 0.9
            )


class WellbeingConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        _reset_prompts_cache()

    def test_defaults_without_yaml(self):
        """④ 无 YAML 时三档分钟数与代码常量默认一致。"""
        with patch.object(wellbeing, "load_prompts", return_value={}):
            self.assertEqual(
                wellbeing._break_thresholds(),
                {"high": 25, "normal": 40, "max_daily": 60},
            )

    def test_override_from_yaml(self):
        """④ YAML 覆盖高负荷分钟数，其余保持默认。"""
        path = _write_temp_yaml("wellbeing:\n  high_load_break_minutes: 30\n")
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        with patch.object(config_module, "_PROMPTS_FILE", path):
            _reset_prompts_cache()
            t = wellbeing._break_thresholds()
        self.assertEqual(t["high"], 30)
        self.assertEqual(t["normal"], 40)
        self.assertEqual(t["max_daily"], 60)


class NoYamlBehaviorTest(unittest.TestCase):
    """⑤ 无 YAML（load_prompts 返回 {}）时各模块行为与默认一致。"""

    def test_strategy_select_deterministic(self):
        s = Student(id="t", name="小明")
        ctx = {"consecutive_wrong": 2, "mastery": 0.4, "step_count": 2}
        r1 = strategy_engine.select_strategy(s, "equation", ctx)
        r2 = strategy_engine.select_strategy(s, "equation", ctx)
        self.assertIsNotNone(r1)
        self.assertEqual(r1.id, r2.id)

    def test_strategy_same_result_with_and_without_yaml(self):
        s = Student(id="t", name="小明")
        ctx = {"consecutive_wrong": 2, "mastery": 0.4, "step_count": 2}
        with patch.object(strategy_engine, "load_prompts", return_value={}):
            r_no_yaml = strategy_engine.select_strategy(s, "equation", ctx)
        r_default = strategy_engine.select_strategy(s, "equation", ctx)
        self.assertEqual(r_no_yaml.id, r_default.id)

    def test_state_engine_deterministic_without_yaml(self):
        with patch.object(state_engine, "load_prompts", return_value={}):
            r = state_engine.decide_next_state(
                "CORE_DERIVE",
                consecutive_wrong=3,
                turns_in_current_state=0,
                abstract_thinking=0.2,
            )
        self.assertEqual(r.new_state, "ANALOGY_EXPLANATION")

    def test_persona_core_falls_back(self):
        with patch.object(persona, "load_prompts", return_value={}):
            self.assertEqual(persona._persona_core(), persona.PERSONA_CORE)

    def test_mode_instructions_falls_back(self):
        with patch.object(persona, "load_prompts", return_value={}):
            a = persona._mode_instructions("A")
            b = persona._mode_instructions("B")
        self.assertIn("深度成长模式", a)
        self.assertIn("保底维稳模式", b)

    def test_wellbeing_falls_back_to_defaults(self):
        with patch.object(wellbeing, "load_prompts", return_value={}):
            self.assertEqual(
                wellbeing._break_thresholds(),
                {"high": 25, "normal": 40, "max_daily": 60},
            )


if __name__ == "__main__":
    unittest.main()
