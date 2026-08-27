"""家长通知机制（架构优化 F1）。

触发条件：
1. 严重危机（severe）— 立即通知
2. 连续3天未学习 — 提醒
3. 周学习时长异常（<30分钟 或 >300分钟）— 提醒
4. 数学焦虑持续升高 — 提醒

通知方式（当前）：生成通知记录保存到学生数据 + 提供 API 查询。
"""

from datetime import date, datetime, timedelta

from backend.models.student import Student
from backend.services.wellbeing import today_minutes


def check_and_notify(student: Student) -> list[dict]:
    """检查是否需要通知家长，返回新增的通知列表（去重后追加到档案）。"""
    from backend.services.storage import get_storage

    notifications: list[dict] = []
    now = datetime.now()
    today = date.today()

    # 1. 严重危机 — 立即通知
    if student.crisis_events:
        latest = student.crisis_events[-1]
        if latest.get("level") == "severe" and not _has_recent(student, "crisis", today):
            notifications.append({
                "id": f"crisis_{now.strftime('%Y%m%d%H%M%S')}",
                "student_id": student.id,
                "type": "crisis",
                "severity": "high",
                "title": "需要关注：孩子表达了负面情绪",
                "message": (
                    f"在今天的学习中，{student.name}提到了负面情绪，小圆已经进行了心理疏导。"
                    "建议家长与孩子聊一聊，给予关心和支持。如情况持续，请寻求专业心理帮助。"
                    "心理援助热线：400-161-9995"
                ),
                "created_at": now.isoformat(),
                "read": False,
            })

    # 2. 连续未学习（≥3天）
    last_date = student.last_session_date()
    if last_date:
        try:
            days_absent = (today - date.fromisoformat(last_date)).days
            if days_absent >= 3 and not _has_recent(student, "absence", today):
                notifications.append({
                    "id": f"absence_{today.isoformat()}",
                    "student_id": student.id,
                    "type": "absence",
                    "severity": "low",
                    "title": f"{student.name}已连续{days_absent}天未学习",
                    "message": (
                        f"{student.name}上次学习是{days_absent}天前。"
                        "适当的坚持很重要，可以鼓励孩子每天花15分钟和小圆一起学数学。"
                    ),
                    "created_at": now.isoformat(),
                    "read": False,
                })
        except ValueError:
            pass

    # 3. 周学习时长异常（本周 <30 或 >300 分钟）
    week_start = today - timedelta(days=today.weekday())
    week_sessions = [
        s for s in student.session_history
        if s.date.startswith(week_start.isoformat())
    ]
    week_minutes = sum(s.duration_minutes for s in week_sessions)
    if not _has_recent(student, "abnormal_time", today):
        if week_minutes < 30 and student.total_sessions >= 3:
            notifications.append({
                "id": f"abnormal_{today.isoformat()}",
                "student_id": student.id,
                "type": "abnormal_time",
                "severity": "low",
                "title": "本周学习时长偏少",
                "message": f"本周{student.name}学习约{week_minutes}分钟，比平时少一些。可以鼓励孩子保持每天一点点的学习节奏。",
                "created_at": now.isoformat(),
                "read": False,
            })
        elif week_minutes > 300:
            notifications.append({
                "id": f"abnormal_{today.isoformat()}",
                "student_id": student.id,
                "type": "abnormal_time",
                "severity": "medium",
                "title": "本周学习时长偏多",
                "message": f"本周{student.name}学习约{week_minutes}分钟，注意适当休息，保护视力。",
                "created_at": now.isoformat(),
                "read": False,
            })

    # 4. 数学焦虑持续升高
    if student.cognitive_profile.math_anxiety >= 0.6 and not _has_recent(student, "anxiety", today):
        notifications.append({
            "id": f"anxiety_{today.isoformat()}",
            "student_id": student.id,
            "type": "anxiety",
            "severity": "medium",
            "title": "孩子近期数学焦虑偏高",
            "message": (
                f"小圆观察到{student.name}最近面对数学有些紧张。建议多鼓励、少施压，"
                "从简单的题目建立信心，及时肯定她的努力。"
            ),
            "created_at": now.isoformat(),
            "read": False,
        })

    if notifications:
        student.parent_notifications.extend(notifications)
        storage = get_storage()
        storage.save(student)

    return notifications


def _has_recent(student: Student, ntype: str, today: date) -> bool:
    """判断今天是否已生成过同类型通知（去重）。"""
    return any(
        n.get("type") == ntype and n.get("created_at", "").startswith(today.isoformat())
        for n in student.parent_notifications
    )
