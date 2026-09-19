"""确定性状态机集成测试（真实 Student 模型）。

用真实 Student 模型驱动 backend.agent.state_engine.update_consecutive_counts /
decide_next_state，验证连续答对推进、连续答错回退、同状态停留 ≥8 轮触发
BREAK_SUGGESTION，并校验状态字段在 Student 对象上持久化（含存储往返）。
另通过 backend.agent.assessment.apply_eval（仅用构造的 eval 字典，不依赖 LLM）
验证评估 → 状态转移的完整接线。全程无网络、无 LLM 调用、不触碰 data/。
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.agent.assessment import apply_eval
from backend.agent.state_engine import decide_next_state, update_consecutive_counts
from backend.models.student import Student
from backend.services.storage import StudentStorage


class StateMachineTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._students_dir = Path(self._tmp.name) / "students"
        self._config_file = Path(self._tmp.name) / "config.json"
        self._patches = [
            mock.patch("backend.config.STUDENTS_DIR", self._students_dir),
            mock.patch("backend.services.storage.STUDENTS_DIR", self._students_dir),
            mock.patch("backend.config.CONFIG_FILE", self._config_file),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()


class ConsecutiveCountsTest(StateMachineTestBase):
    def test_consecutive_correct_promotes(self):
        student = Student(id="stu_correct", name="小明")
        student.current_session.state = "BLIND_SPOT"

        update_consecutive_counts(student, {"independent_success": True}, "BLIND_SPOT")
        update_consecutive_counts(student, {"independent_success": True}, "BLIND_SPOT")

        sess = student.current_session
        self.assertEqual(sess.consecutive_correct, 2)
        self.assertEqual(sess.consecutive_wrong, 0)

        result = decide_next_state("BLIND_SPOT", consecutive_correct=2, consecutive_wrong=0)
        self.assertEqual(result.new_state, "CORE_DERIVE")
        self.assertEqual(result.source, "rule")

    def test_consecutive_wrong_falls_back(self):
        student = Student(id="stu_wrong", name="小红")
        student.current_session.state = "EXAMPLE_CHECK"

        for _ in range(3):
            update_consecutive_counts(student, {"independent_success": False}, "EXAMPLE_CHECK")

        sess = student.current_session
        self.assertEqual(sess.consecutive_wrong, 3)
        self.assertEqual(sess.consecutive_correct, 0)

        result = decide_next_state("EXAMPLE_CHECK", consecutive_wrong=3, turns_in_current_state=0)
        self.assertEqual(result.new_state, "CORE_DERIVE")
        self.assertEqual(result.source, "rule")

    def test_break_suggestion_after_max_turns(self):
        result = decide_next_state("CORE_DERIVE", turns_in_current_state=8)
        self.assertEqual(result.new_state, "BREAK_SUGGESTION")
        self.assertEqual(result.source, "rule")

    def test_counts_persist_through_storage(self):
        student = Student(id="stu_persist", name="小刚")
        student.current_session.state = "BLIND_SPOT"
        update_consecutive_counts(student, {"independent_success": True}, "BLIND_SPOT")
        update_consecutive_counts(student, {"independent_success": True}, "BLIND_SPOT")

        storage = StudentStorage()
        storage.save(student)
        loaded = storage.load("stu_persist")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.current_session.consecutive_correct, 2)
        self.assertEqual(loaded.current_session.state, "BLIND_SPOT")


class ApplyEvalWiringTest(StateMachineTestBase):
    def test_apply_eval_transitions_state(self):
        student = Student(id="stu_eval", name="小丽")
        student.current_session.state = "BLIND_SPOT"
        student.current_session.consecutive_correct = 1

        new_badges = apply_eval(student, {"independent_success": True}, suppress_combo=True)

        self.assertIsInstance(new_badges, list)
        self.assertEqual(student.current_session.state, "CORE_DERIVE")
        self.assertEqual(student.current_session.consecutive_correct, 0)
        self.assertEqual(student.current_session.turns_in_current_state, 0)


if __name__ == "__main__":
    unittest.main()
