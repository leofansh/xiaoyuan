"""JSON 存储层单元测试。

用标准库 unittest，无需 pytest / FastAPI / 网络。
通过临时目录替换 storage.STUDENTS_DIR 模块级全局，绝不动真实 data/ 目录。
覆盖原子读写、自动备份与保留数量、路径清洗、list_all 容错、
学习链（touch_streak）、模式记录、心情打卡。
"""

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from backend.models.student import Badge, Gap, MasteryRecord, Student
from backend.services import storage


class StorageTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = storage.STUDENTS_DIR
        storage.STUDENTS_DIR = Path(self._tmp.name)

    def tearDown(self):
        storage.STUDENTS_DIR = self._orig
        self._tmp.cleanup()


class StorageIOTest(StorageTestBase):
    def test_new_student_id_unique_and_prefixed(self):
        id1 = storage.new_student_id()
        id2 = storage.new_student_id()
        self.assertTrue(id1.startswith("stu_"))
        self.assertNotEqual(id1, id2)
        self.assertEqual(len(id1), 4 + 10)

    def test_save_load_roundtrip(self):
        s = Student(id="stu_rt", name="小明")
        s.mastery["6a_jiafa"] = MasteryRecord(score=0.8, confidence=0.9)
        s.gaps.append(
            Gap(topic_id="6a_jiafa", type="concept", category="concept_misunderstanding")
        )
        st = storage.StudentStorage()
        st.save(s)

        loaded = st.load("stu_rt")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "小明")
        self.assertAlmostEqual(loaded.mastery["6a_jiafa"].score, 0.8)
        self.assertEqual(loaded.gaps[0].topic_id, "6a_jiafa")
        self.assertEqual(loaded.gaps[0].category, "concept_misunderstanding")

    def test_load_missing_returns_none(self):
        st = storage.StudentStorage()
        self.assertIsNone(st.load("nonexistent"))

    def test_create_persists_and_assigns_id(self):
        st = storage.StudentStorage()
        s = st.create("小明", grade=7)
        self.assertTrue(s.id.startswith("stu_"))
        self.assertEqual(s.grade, 7)
        self.assertEqual(s.name, "小明")

        loaded = st.load(s.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "小明")

    def test_save_sets_last_active_and_no_tmp_left(self):
        s = Student(id="stu_x", name="n")
        st = storage.StudentStorage()
        st.save(s)
        self.assertNotEqual(s.last_active, "")
        self.assertEqual(list(storage.STUDENTS_DIR.glob("*.tmp")), [])

    def test_save_backs_up_previous_version(self):
        st = storage.StudentStorage()
        s = Student(id="stu_bk", name="n")
        st.save(s)
        backup_dir = storage.STUDENTS_DIR / "backups"
        self.assertFalse(backup_dir.exists())

        st.save(s)
        self.assertTrue(backup_dir.exists())
        self.assertEqual(len(list(backup_dir.glob("stu_bk_*.json"))), 1)

    def test_save_prunes_old_backups(self):
        st = storage.StudentStorage()
        s = Student(id="stu_bk", name="n")
        st.save(s)

        backup_dir = storage.STUDENTS_DIR / "backups"
        backup_dir.mkdir(exist_ok=True)
        for i in range(5):
            (backup_dir / f"stu_bk_2026010{i}_000001.json").write_text("{}", encoding="utf-8")

        st.save(s)
        self.assertEqual(len(list(backup_dir.glob("stu_bk_*.json"))), 3)

    def test_path_sanitizes_separators(self):
        st = storage.StudentStorage()
        p = st._path("a/b\\c")
        self.assertEqual(p.name, "a_b_c.json")
        self.assertEqual(p.parent, storage.STUDENTS_DIR)

    def test_list_all_skips_corrupt_and_non_student(self):
        storage.STUDENTS_DIR.mkdir(parents=True, exist_ok=True)
        (storage.STUDENTS_DIR / "stu_a.json").write_text(
            json.dumps({"id": "a", "name": "A", "grade": 6}), encoding="utf-8"
        )
        (storage.STUDENTS_DIR / "stu_b.json").write_text("{not json", encoding="utf-8")
        (storage.STUDENTS_DIR / "stu_c.json").write_text(
            json.dumps({"id": "c"}), encoding="utf-8"
        )
        (storage.STUDENTS_DIR / "other.txt").write_text("x", encoding="utf-8")

        result = storage.StudentStorage().list_all()
        self.assertEqual([r["id"] for r in result], ["a"])


class StorageBehaviorTest(StorageTestBase):
    def test_touch_streak_new_and_same_day(self):
        s = Student(id="s", name="n")
        self.assertFalse(storage.StudentStorage.touch_streak(s))
        self.assertEqual(s.streak_chain, 1)
        self.assertEqual(s.streak_last_date, date.today().isoformat())

        self.assertFalse(storage.StudentStorage.touch_streak(s))
        self.assertEqual(s.streak_chain, 1)

    def test_touch_streak_badge_and_break(self):
        s = Student(id="s", name="n")
        s.streak_chain = 6
        s.streak_last_date = (date.today() - timedelta(days=1)).isoformat()
        self.assertTrue(storage.StudentStorage.touch_streak(s))
        self.assertEqual(s.streak_chain, 7)
        self.assertIn(Badge.STREAK_7, s.badges)

        s2 = Student(id="s2", name="n")
        s2.streak_chain = 5
        s2.streak_last_date = (date.today() - timedelta(days=2)).isoformat()
        storage.StudentStorage.touch_streak(s2)
        self.assertEqual(s2.streak_chain, 1)

    def test_record_mode_and_baseline(self):
        s = Student(id="s", name="n")
        storage.StudentStorage.record_mode(s, "A")
        self.assertEqual(len(s.mode_history), 1)
        self.assertEqual(s.mode_history[0]["mode"], "A")
        self.assertEqual(s.week_baseline_count, 0)

        storage.StudentStorage.record_mode(s, "B")
        self.assertEqual(s.week_baseline_count, 1)
        storage.StudentStorage.record_mode(s, "B")
        self.assertEqual(s.week_baseline_count, 2)

    def test_add_mood(self):
        s = Student(id="s", name="n")
        storage.StudentStorage.add_mood(s, "😊")
        self.assertEqual(len(s.mood_checkins), 1)
        self.assertEqual(s.mood_checkins[0]["mood"], "😊")


if __name__ == "__main__":
    unittest.main()
