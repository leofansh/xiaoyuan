"""学生数据模型（Pydantic）单元测试。

用标准库 unittest，无需 pytest / FastAPI / 网络。
覆盖字段默认值、字段约束、模型实例方法（掌握度/漏洞/语言层级推导）
与旧格式数据迁移（B1 掌握度、B2 漏洞分类）。
"""

import unittest

from backend.models.student import (
    Badge,
    CognitiveProfile,
    Gap,
    MasteryRecord,
    SessionSummary,
    Student,
)


class ModelDefaultsTest(unittest.TestCase):
    def test_student_defaults(self):
        s = Student(id="s1", name="小明")
        self.assertEqual(s.grade, 6)
        self.assertEqual(s.textbook, "沪教版五四制2024")
        self.assertEqual(s.language_level, 2)
        self.assertEqual(s.mastery, {})
        self.assertEqual(s.badges, [])
        self.assertEqual(s.session_history, [])
        self.assertEqual(s.total_sessions, 0)
        self.assertEqual(s.streak_chain, 0)

    def test_mastery_record_defaults(self):
        m = MasteryRecord()
        self.assertEqual(m.score, 0.0)
        self.assertEqual(m.confidence, 0.0)
        self.assertEqual(m.attempts_correct, 0)
        self.assertEqual(m.attempts_total, 0)
        self.assertEqual(m.p_known, 0.0)
        self.assertFalse(m.bkt_mastered)

    def test_gap_defaults(self):
        g = Gap(topic_id="6a_jiafa")
        self.assertEqual(g.type, "concept")
        self.assertEqual(g.status, "open")
        self.assertEqual(g.occurrence_count, 1)
        self.assertEqual(g.category, "unknown")
        self.assertIsNone(g.cleared_at)

    def test_cognitive_profile_defaults(self):
        cp = CognitiveProfile()
        self.assertEqual(cp.cognitive_stage, "concrete")
        self.assertEqual(cp.working_memory_capacity, "medium")
        self.assertEqual(cp.abstract_thinking, 0.3)
        self.assertEqual(cp.math_anxiety, 0.2)
        self.assertEqual(cp.executive_function["inhibition"], 0.5)
        self.assertEqual(cp.executive_function["flexibility"], 0.4)


class StudentMethodsTest(unittest.TestCase):
    def _student(self) -> Student:
        return Student(id="s", name="小明")

    def test_avg_mastery(self):
        s = self._student()
        self.assertEqual(s.avg_mastery(), 0.0)
        s.mastery["a"] = MasteryRecord(score=0.6)
        s.mastery["b"] = MasteryRecord(score=0.8)
        self.assertAlmostEqual(s.avg_mastery(), 0.7)

    def test_mastery_score_and_confidence(self):
        s = self._student()
        self.assertEqual(s.mastery_score("missing"), 0.0)
        self.assertEqual(s.mastery_score("missing", 0.5), 0.5)
        s.mastery["a"] = MasteryRecord(score=0.9, confidence=0.7)
        self.assertAlmostEqual(s.mastery_score("a"), 0.9)
        self.assertAlmostEqual(s.mastery_confidence("a"), 0.7)
        self.assertEqual(s.mastery_confidence("missing"), 0.0)

    def test_last_session_date(self):
        s = self._student()
        self.assertEqual(s.last_session_date(), "")
        s.session_history.append(SessionSummary(date="2026-01-01"))
        s.session_history.append(SessionSummary(date="2026-01-02"))
        self.assertEqual(s.last_session_date(), "2026-01-02")

    def test_open_gaps_and_concept_gaps(self):
        s = self._student()
        s.gaps = [
            Gap(topic_id="t1", type="concept", status="open"),
            Gap(topic_id="t2", type="careless", status="recurring"),
            Gap(topic_id="t3", type="concept", status="cleared"),
        ]
        self.assertEqual(len(s.open_gaps()), 2)
        self.assertEqual(len(s.concept_gaps_open()), 1)
        self.assertEqual(s.concept_gaps_open()[0].topic_id, "t1")

    def test_derive_language_level_by_grade(self):
        def student_with_grade(g: int) -> Student:
            s = Student(id="s", name="小明", grade=g)
            s.cognitive_profile.abstract_thinking = 1.0
            return s

        self.assertEqual(student_with_grade(2).derive_language_level(), 1)
        self.assertEqual(student_with_grade(5).derive_language_level(), 2)
        self.assertEqual(student_with_grade(8).derive_language_level(), 3)
        self.assertEqual(student_with_grade(11).derive_language_level(), 4)

    def test_derive_language_level_cognitive_downgrade(self):
        s = Student(id="s", name="小明", grade=8)
        self.assertEqual(s.derive_language_level(), 2)

        s.cognitive_profile.abstract_thinking = 1.0
        self.assertEqual(s.derive_language_level(), 3)

        s2 = Student(id="s2", name="小明", grade=11)
        s2.cognitive_profile.abstract_thinking = 1.0
        s2.cognitive_profile.working_memory_capacity = "low"
        self.assertEqual(s2.derive_language_level(), 3)

        low = Student(id="s3", name="小明", grade=2)
        low.cognitive_profile.working_memory_capacity = "low"
        low.cognitive_profile.abstract_thinking = 0.1
        self.assertEqual(low.derive_language_level(), 1)

    def test_ensure_language_level_updates(self):
        s = Student(id="s", name="小明", grade=9)
        s.cognitive_profile.abstract_thinking = 1.0
        self.assertEqual(s.language_level, 2)
        self.assertEqual(s.ensure_language_level(), 3)
        self.assertEqual(s.language_level, 3)

    def test_legacy_migration(self):
        data = {
            "id": "s1",
            "name": "小明",
            "mastery": {"6a_jiafa": 0.8, "6a_jianfa": 0.5},
            "gaps": [{"topic_id": "6a_jiafa", "type": "concept"}],
        }
        s = Student.model_validate(data)
        rec = s.mastery["6a_jiafa"]
        self.assertIsInstance(rec, MasteryRecord)
        self.assertAlmostEqual(rec.score, 0.8)
        self.assertAlmostEqual(rec.confidence, 0.5)
        self.assertEqual(rec.attempts_total, 1)
        self.assertEqual(s.gaps[0].category, "concept_misunderstanding")
        self.assertEqual(s.gaps[0].occurrence_count, 1)

    def test_badge_catalog(self):
        self.assertIn(Badge.STREAK_7, Badge.ALL)
        self.assertIn(Badge.THINKING_REVERSE, Badge.ALL)
        self.assertIn(Badge.TRUE_CLEAR, Badge.ALL)
        self.assertEqual(Badge.ALL[Badge.STREAK_7]["icon"], "🔗")
        self.assertTrue(Badge.ALL[Badge.THINKING_REVERSE]["desc"])


if __name__ == "__main__":
    unittest.main()
