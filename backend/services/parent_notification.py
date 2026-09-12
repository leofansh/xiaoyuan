"""家长通知机制（架构优化 F1 + V3.0 规格 11.8 家长角色重塑）。

11.8 家长角色重塑：通知文案全部重写为「不报忧只报喜、不报错率只报进步」。
- 删除/替换所有报错类文案（成绩下降、错误率高、退步、没完成等负面表述）
- 「未学习」类文案改为「今天状态不太好，只做了保底，但守住了学习链条」的积极表述
- 新增「亮点优先」文案结构：孩子今天学会了什么 / 孩子的作品 / 孩子的进步
- 新增「教爸妈」家庭挑战：weekly_teach_parent_challenge（按 ISO 周固定生成）

触发条件（保留原架构，仅改写文案语气）：
1. 亮点优先（每天一条正向亮点）
2. 严重危机（severe）— 立即通知（正向化 + 保留心理援助热线）
3. 连续3天未学习 — 正向化提醒
4. 周学习时长异常 — 正向化提醒（不报时长数字）
5. 数学焦虑持续升高 — 正向化提醒
"""

import hashlib
from datetime import date, datetime, timedelta

from backend.models.student import Student


def check_and_notify(student: Student) -> list[dict]:
    """检查是否需要通知家长，返回新增的通知列表（去重后追加到档案）。"""
    from backend.services.storage import get_storage

    notifications: list[dict] = []
    now = datetime.now()
    today = date.today()

    # 1. 亮点优先：每天一条正向亮点（孩子今天学会了什么 / 作品 / 进步）
    highlight = _build_highlight(student)
    if highlight and not _has_recent(student, "highlight", today):
        notifications.append({
            "id": f"highlight_{today.isoformat()}",
            "student_id": student.id,
            "type": "highlight",
            "severity": "positive",
            "title": "孩子今天的小亮点 ✨",
            "message": highlight,
            "created_at": now.isoformat(),
            "read": False,
        })

    # 2. 严重危机 — 立即通知（正向化：表扬孩子愿意表达，保留心理援助热线）
    if student.crisis_events:
        latest = student.crisis_events[-1]
        if latest.get("level") == "severe" and not _has_recent(student, "crisis", today):
            notifications.append({
                "id": f"crisis_{now.strftime('%Y%m%d%H%M%S')}",
                "student_id": student.id,
                "type": "crisis",
                "severity": "high",
                "title": "孩子今天愿意和我说心里话",
                "message": (
                    f"今天{student.name}愿意把心里话讲给小圆听，这是很勇敢、也很信任的表现。"
                    "小圆已经陪她聊了聊，给了安慰。孩子愿意表达，说明家给了她足够的安全感。"
                    "今晚不妨抱抱她、听她说说。若担心她的情绪，可拨打心理援助热线：400-161-9995。"
                ),
                "created_at": now.isoformat(),
                "read": False,
            })

    # 3. 连续未学习（≥3天）— 正向化：把学习链条接上就是胜利
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
                    "title": f"{student.name}的学习链在等她回来",
                    "message": (
                        f"小圆这几天一直记得{student.name}。休息也是学习的一部分，"
                        "等她准备好了，哪怕只做5分钟保底，把学习链条接上，就是很棒的一天。"
                        "可以先夸夸她愿意坚持的心。"
                    ),
                    "created_at": now.isoformat(),
                    "read": False,
                })
        except ValueError:
            pass

    # 4. 周学习时长异常 — 正向化：不报时长数字，只肯定投入与节奏
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
                "title": "孩子有自己的学习节奏",
                "message": (
                    "小圆很尊重孩子自己的节奏，学得少一点也没关系。"
                    "每天愿意来，学习链条就一直连着。多夸夸她每一次主动打开小圆的瞬间吧。"
                ),
                "created_at": now.isoformat(),
                "read": False,
            })
        elif week_minutes > 300:
            notifications.append({
                "id": f"abnormal_{today.isoformat()}",
                "student_id": student.id,
                "type": "abnormal_time",
                "severity": "low",
                "title": "孩子这周学得特别投入",
                "message": (
                    "孩子这周特别专注，小圆已经提醒她注意休息、保护眼睛啦。"
                    "这份投入很珍贵，记得也夸夸她。"
                ),
                "created_at": now.isoformat(),
                "read": False,
            })

    # 5. 数学焦虑持续升高 — 正向化：肯定勇敢，建议多鼓励
    if student.cognitive_profile.math_anxiety >= 0.6 and not _has_recent(student, "anxiety", today):
        notifications.append({
            "id": f"anxiety_{today.isoformat()}",
            "student_id": student.id,
            "type": "anxiety",
            "severity": "medium",
            "title": "孩子今天被小圆温柔接住了",
            "message": (
                f"{student.name}最近面对数学有点紧张，小圆没有催她，"
                "陪她从最简单的题一点点找回手感。她已经迈出了很勇敢的一步。"
                "多给一点鼓励，她会越来越稳。"
            ),
            "created_at": now.isoformat(),
            "read": False,
        })

    if notifications:
        student.parent_notifications.extend(notifications)
        storage = get_storage()
        storage.save(student)

    return notifications


def weekly_teach_parent_challenge(student: Student) -> dict:
    """「教爸妈」家庭挑战（规格 11.8 第三行）：每周一个家庭小任务。

    孩子学会某个知识点后，把这个知识点教给爸妈，全家完成一个小任务。
    按 ISO 周固定生成：同一周内 challenge_id 不变，知识主题从学生最近掌握的知识点选取。

    返回 {challenge_id, title, description, knowledge_topic, xp_reward}。
    """
    iso = datetime.now().isocalendar()
    year, week = iso[0], iso[1]

    topic = _pick_challenge_topic(student, year, week)
    challenge_id = f"teach_parent_{year}_W{week:02d}"

    return {
        "challenge_id": challenge_id,
        "title": "本周家庭小挑战：孩子当小老师",
        "description": (
            f"这周的小任务：让{student.name}把刚学会的「{topic}」讲给爸爸妈妈听。"
            "不用考她，认真听、认真点头、认真夸就够。讲清楚之后，全家一起用"
            f"「{topic}」完成一件小事（比如一起算笔账、分一次东西）。"
            "教一遍，记得比做十道题还牢。"
        ),
        "knowledge_topic": topic,
        "xp_reward": 50,
    }


def _pick_challenge_topic(student: Student, year: int, week: int) -> str:
    """从学生最近掌握的知识点中，按（学生, 周）确定性选取本周挑战主题。"""
    from backend.knowledge import syllabus

    candidates: list[str] = []
    for tid, rec in (student.mastery or {}).items():
        if rec.score >= 0.6:
            node = syllabus.get_node(tid)
            candidates.append(node.name if node else tid)

    if not candidates and student.session_history:
        last = student.session_history[-1]
        if last.topic_name:
            candidates.append(last.topic_name)
        elif last.topic_id:
            node = syllabus.get_node(last.topic_id)
            candidates.append(node.name if node else last.topic_id)

    if not candidates:
        return "四则运算"

    seed = int(hashlib.md5(f"{student.id}:{year}:{week}".encode("utf-8")).hexdigest(), 16)
    return candidates[seed % len(candidates)]


def _build_highlight(student: Student) -> str | None:
    """构建「亮点优先」正向文案：孩子今天学会了什么 / 孩子的作品 / 孩子的进步。"""
    lines: list[str] = []

    today = student.today_iso()
    today_topics = [
        s.topic_name for s in student.session_history
        if s.date == today and s.topic_name
    ]
    if today_topics:
        names = _dedupe(today_topics)[:3]
        lines.append(f"今天和「{'、'.join(names)}」交了朋友")
    else:
        recent = _recently_mastered(student, limit=3)
        if recent:
            lines.append(f"最近把「{'、'.join(recent)}」学得有模有样")

    creations = student.creations or []
    recent_works = [
        c for c in creations if c.get("created_at", "").startswith(today)
    ] or creations[-2:]
    for c in recent_works:
        if c.get("type") == "teach":
            lines.append("当了一回小老师，把一道题讲得清清楚楚")
            break
        if c.get("type") == "problem":
            lines.append("自己出了一道数学题，当上了出题人")
            break

    if student.badges:
        lines.append(f"已经攒下 {len(student.badges)} 枚成长徽章")
    if student.streak_chain >= 1:
        lines.append(f"学习链已经稳稳连了 {student.streak_chain} 天")

    if not lines:
        return f"小圆已经准备好，要和{student.name}一起慢慢探索数学的世界啦。"
    return "；".join(lines) + "。"


def _recently_mastered(student: Student, limit: int = 3) -> list[str]:
    """最近掌握（score≥0.7）的知识点名称，按最近交互时间排序。"""
    from backend.knowledge import syllabus

    items = [
        (tid, rec) for tid, rec in (student.mastery or {}).items()
        if rec.score >= 0.7
    ]
    items.sort(key=lambda kv: kv[1].last_interaction or "", reverse=True)
    names: list[str] = []
    for tid, _ in items[:limit]:
        node = syllabus.get_node(tid)
        names.append(node.name if node else tid)
    return names


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


def _has_recent(student: Student, ntype: str, today: date) -> bool:
    """判断今天是否已生成过同类型通知（去重）。"""
    return any(
        n.get("type") == ntype and n.get("created_at", "").startswith(today.isoformat())
        for n in student.parent_notifications
    )
