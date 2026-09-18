"""间隔复习调度（FSRS-6）单元测试。

用标准库 unittest，无需 pytest / FastAPI / 网络。
模拟时间流逝通过手工改写 ReviewSchedule.due / last_reviewed 实现。
"""

import unittest
from datetime import date, datetime, timedelta, timezone

from backend.models.student import ReviewSchedule, Student
from backend.services.repetition import (
    get_due_reviews,
    record_review,
    schedule_review,
)

TOPIC = "6a_jiafa"


def _make_student() -> Student:
    return Student(id="test", name="小明")


class RepetitionTest(unittest.TestCase):
    def test_schedule_review_initializes_fsrs_state(self):
        student = _make_student()
        schedule_review(student, TOPIC, 0.6)

        self.assertEqual(len(student.review_schedules), 1)
        rs = student.review_schedules[0]
        # 0.6 → 5 天档
        self.assertEqual(rs.interval_days, 5)
        self.assertGreater(rs.stability, 0.0)
        self.assertEqual(rs.state, 2)
        self.assertNotEqual(rs.due, "")
        self.assertEqual(rs.next_review, (date.today() + timedelta(days=5)).isoformat())

    def test_record_review_good_increases_interval(self):
        student = _make_student()
        schedule_review(student, TOPIC, 0.6)
        rs = student.review_schedules[0]
        old_stability = rs.stability
        old_next_review = rs.next_review

        ten_days_ago = datetime.now(timezone.utc) - timedelta(days=10)
        rs.due = ten_days_ago.isoformat()
        rs.last_reviewed = ten_days_ago.date().isoformat()

        record_review(student, TOPIC, True)

        self.assertEqual(rs.review_count, 1)
        self.assertGreater(rs.stability, old_stability)
        self.assertGreater(rs.next_review, old_next_review)
        self.assertEqual(student.review_logs[-1].rating, 3)

    def test_record_review_again_breaks_interval(self):
        student = _make_student()
        schedule_review(student, TOPIC, 0.6)
        rs = student.review_schedules[0]
        old_stability = rs.stability

        ten_days_ago = datetime.now(timezone.utc) - timedelta(days=10)
        rs.due = ten_days_ago.isoformat()
        rs.last_reviewed = ten_days_ago.date().isoformat()

        record_review(student, TOPIC, False)

        self.assertEqual(rs.review_count, 1)
        self.assertLess(rs.stability, old_stability)
        self.assertLess(rs.interval_days, 5)
        self.assertEqual(student.review_logs[-1].rating, 1)

    def test_get_due_reviews_filters(self):
        student = _make_student()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        student.review_schedules.append(
            ReviewSchedule(topic_id="due_a", next_review=yesterday)
        )
        student.review_schedules.append(
            ReviewSchedule(topic_id="due_b", next_review=tomorrow)
        )

        due = get_due_reviews(student)

        self.assertEqual(len(due), 1)
        self.assertEqual(due[0].topic_id, "due_a")

    def test_review_log_capped_at_200(self):
        student = _make_student()
        schedule_review(student, TOPIC, 0.3)

        for _ in range(210):
            record_review(student, TOPIC, True)

        self.assertEqual(len(student.review_logs), 200)
        self.assertEqual(student.review_logs[-1].rating, 3)

    def test_legacy_schedule_migration(self):
        student = _make_student()
        student.review_schedules.append(
            ReviewSchedule(
                topic_id=TOPIC,
                next_review=(date.today() + timedelta(days=2)).isoformat(),
                interval_days=2,
            )
        )

        record_review(student, TOPIC, True)

        rs = student.review_schedules[0]
        self.assertEqual(rs.review_count, 1)
        self.assertEqual(rs.state, 2)
        self.assertGreater(rs.stability, 0.0)


if __name__ == "__main__":
    unittest.main()
