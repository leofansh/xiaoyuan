"""防沉迷机制（SAFE-P1-2 轻量版）：面向 K12 学生的用眼/作息保护。

策略选择：单机本地应用，不强制阻断，采用「温柔提醒」方式，
在会话开始时提示，避免给孩子造成挫败感。
"""

from datetime import datetime

from backend.models.student import Student

# 配置（未来可由家长端设置，当前用默认值）
DAILY_LIMIT_MINUTES = 60      # 每日学习时长上限
NIGHT_START_HOUR = 22         # 夜间限制开始
NIGHT_END_HOUR = 6            # 夜间限制结束


def today_minutes(student: Student) -> int:
    """统计今日累计学习时长（分钟）。"""
    today = student.today_iso()
    return sum(
        h.duration_minutes for h in student.session_history if h.date == today
    )


def check_time_limit(student: Student) -> str | None:
    """返回应展示的时间提醒（字符串），无则返回 None。

    优先级：夜间 > 今日超时 > （暂不强制休息）。
    只做提醒，不做强制阻断。
    """
    now = datetime.now()

    # 1. 夜间限制
    if now.hour >= NIGHT_START_HOUR or now.hour < NIGHT_END_HOUR:
        return "这么晚啦，该睡觉了～小圆明天等你哦🌙"

    # 2. 每日时长上限
    minutes = today_minutes(student)
    if minutes >= DAILY_LIMIT_MINUTES:
        return (
            f"今天已经学了大约 {DAILY_LIMIT_MINUTES} 分钟了，眼睛需要休息哦～"
            "不如我们做个眼保健操，明天再来好不好？🌿"
        )
    if minutes >= DAILY_LIMIT_MINUTES - 10:
        return f"今天学到 {minutes} 分钟啦，快到我们的休息时间了，做完这题就休息好吗？"

    return None
