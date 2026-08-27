"""防沉迷机制：认知负荷感知（SAFE-P1-2 + 架构优化 F2）。

策略：单机本地应用，不强制阻断，采用「温柔提醒」方式。
F2 改进：
1. 认知负荷估算（连续错误、状态停留、掌握度）
2. 高认知负荷时更早提醒休息（25分钟）
3. 休息建议具体化（做什么、多久）
"""

from datetime import datetime

from backend.models.student import Student

# 配置（未来可由家长端设置，当前用默认值）
DAILY_LIMIT_MINUTES = 60      # 每日学习时长上限
NIGHT_START_HOUR = 22         # 夜间限制开始
NIGHT_END_HOUR = 6            # 夜间限制结束
HIGH_LOAD_BREAK_MINUTES = 25  # 高认知负荷提醒休息
MEDIUM_LOAD_BREAK_MINUTES = 40
LOW_LOAD_BREAK_MINUTES = 60


def today_minutes(student: Student) -> int:
    """统计今日累计学习时长（分钟）。"""
    today = student.today_iso()
    return sum(
        h.duration_minutes for h in student.session_history if h.date == today
    )


def estimate_cognitive_load(student: Student) -> float:
    """估算当前认知负荷（0-1，F2）。"""
    load = 0.0
    sess = student.current_session

    # 1. 连续错误增加认知负荷
    load += min(sess.consecutive_wrong * 0.15, 0.45)

    # 2. 同一状态停留越久，认知负荷越高
    load += min(sess.turns_in_current_state * 0.05, 0.3)

    # 3. 题目难度（掌握度低的知识点负荷高）
    if sess.topic_id:
        mastery = student.mastery_score(sess.topic_id)
        load += (1 - mastery) * 0.2  # 不熟练的知识点负荷高

    # 4. 连续负面情绪增加负荷
    load += min(sess.consecutive_negative_turns * 0.05, 0.15)

    return min(load, 1.0)


def check_break_needed(student: Student) -> str | None:
    """检查是否需要休息（基于认知负荷+时间，F2）。

    Returns: 休息建议，或 None。
    """
    minutes = today_minutes(student)
    load = estimate_cognitive_load(student)

    # 高认知负荷：25分钟就提醒
    if load > 0.6 and minutes >= HIGH_LOAD_BREAK_MINUTES:
        return (
            "这几道题挺有挑战性的，大脑已经工作25分钟了！我们休息5分钟吧，"
            "站起来走走，看看远处，让大脑充充电。回来我们再做最后一道～"
        )
    # 中等认知负荷：40分钟提醒
    if load > 0.3 and minutes >= MEDIUM_LOAD_BREAK_MINUTES:
        return (
            "已经学了40分钟了，做得很好！我们休息一下，喝口水，"
            "活动活动肩膀，伸个懒腰～"
        )
    # 常规：60分钟强制提醒
    if minutes >= LOW_LOAD_BREAK_MINUTES:
        return (
            "今天已经学了60分钟了，非常棒！今天就到这里吧，明天继续。"
            "记得每天坚持比一次学很久更有效哦。"
        )
    return None


def check_time_limit(student: Student) -> str | None:
    """返回应展示的时间提醒（字符串），无则返回 None。

    优先级：夜间 > 认知负荷休息建议 > 今日超时。
    只做提醒，不做强制阻断。
    """
    now = datetime.now()

    # 1. 夜间限制
    if now.hour >= NIGHT_START_HOUR or now.hour < NIGHT_END_HOUR:
        return "这么晚啦，该睡觉了～小圆明天等你哦🌙"

    # 2. 认知负荷感知休息建议（F2）
    break_hint = check_break_needed(student)
    if break_hint:
        return break_hint

    # 3. 每日时长上限（兜底，正常 60 分钟已含在 check_break_needed）
    minutes = today_minutes(student)
    if minutes >= DAILY_LIMIT_MINUTES - 10:
        return f"今天学到 {minutes} 分钟啦，快到我们的休息时间了，做完这题就休息好吗？"

    return None
