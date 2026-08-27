"""周学习报告生成器。

统计本周学习数据，对比上周，生成可视化报告。
本周定义：周一到周日（自然周）。
"""

from datetime import datetime, timedelta, date

from backend.models.student import Student


def generate_weekly_report(student: Student) -> dict:
    """生成本周学习报告。"""
    today = date.today()
    # 本周一
    week_start = today - timedelta(days=today.weekday())
    # 上周一
    last_week_start = week_start - timedelta(days=7)
    last_week_end = week_start - timedelta(days=1)

    def _parse_date(s: str) -> date | None:
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    # 本周会话
    this_week = [
        s for s in student.session_history
        if _parse_date(s.date) and _parse_date(s.date) >= week_start
    ]
    # 上周会话
    last_week = [
        s for s in student.session_history
        if _parse_date(s.date) and last_week_start <= _parse_date(s.date) <= last_week_end
    ]

    # 统计
    this_minutes = sum(s.duration_minutes for s in this_week)
    last_minutes = sum(s.duration_minutes for s in last_week)

    this_days = len(set(s.date for s in this_week))
    last_days = len(set(s.date for s in last_week))

    this_badges = list(set(b for s in this_week for b in s.new_badges))

    # 掌握知识点数（mastery >= 0.7）
    mastered_count = sum(1 for rec in student.mastery.values() if rec.score >= 0.7)

    return {
        "week_start": week_start.isoformat(),
        "week_end": today.isoformat(),
        "study_days": this_days,
        "study_minutes": this_minutes,
        "sessions_count": len(this_week),
        "new_badges": this_badges,
        "mastered_count": mastered_count,
        "open_gaps_count": len(student.open_gaps()),
        "streak_chain": student.streak_chain,
        # 对比上周
        "vs_last_week": {
            "minutes_delta": this_minutes - last_minutes,
            "days_delta": this_days - last_days,
            "sessions_delta": len(this_week) - len(last_week),
        }
    }
