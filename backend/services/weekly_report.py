"""周学习报告生成器（V-P2-1 + 架构优化 G1 洞察/建议）。

统计本周学习数据，对比上周，生成可视化报告。
本周定义：周一到周日（自然周）。
"""

from datetime import datetime, timedelta, date

from backend.models.student import Student


def generate_weekly_report(student: Student) -> dict:
    """生成本周学习报告（含洞察和建议 G1）。"""
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

    # G1：洞察分析
    insights = _generate_insights(student, this_week, last_week)
    # G1：下周建议
    suggestions = _generate_suggestions(student)

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
        },
        "insights": insights,
        "suggestions": suggestions,
    }


def _generate_insights(student: Student, this_week: list, last_week: list) -> list[dict]:
    """生成学习洞察（G1）。"""
    insights: list[dict] = []

    # 洞察1：进步最大的知识点
    mastery_scores = [(k, rec.score) for k, rec in student.mastery.items() if rec.confidence >= 0.4]
    if mastery_scores:
        top = max(mastery_scores, key=lambda x: x[1])
        if top[1] >= 0.6:
            from backend.knowledge.syllabus import get_node
            node = get_node(top[0])
            insights.append({
                "type": "progress",
                "title": f"在「{node.name if node else top[0]}」上掌握得不错",
                "detail": f"掌握度达到 {top[1]:.0%}，数据充分（置信度 {student.mastery[top[0]].confidence:.0%}）。继续保持！",
            })

    # 洞察2：需要关注的漏洞
    open_gaps = student.open_gaps()
    if open_gaps:
        gap_names = [g.topic_name or g.topic_id for g in open_gaps[:3]]
        insights.append({
            "type": "gap",
            "title": f"有 {len(open_gaps)} 个知识漏洞需要修复",
            "detail": f"主要在：{'、'.join(gap_names)}。建议下周优先修复这些漏洞。",
        })

    # 洞察3：反复出错的模式（基于 recurring 漏洞或 open gaps 的 category）
    error_counts: dict[str, int] = {}
    for g in student.gaps:
        if g.status in ("open", "recurring") and g.category and g.category != "unknown":
            error_counts[g.category] = error_counts.get(g.category, 0) + g.occurrence_count
    if error_counts:
        top_err = max(error_counts, key=error_counts.get)
        if error_counts[top_err] >= 2:
            from backend.knowledge.error_patterns import category_name, repair_strategy_for
            insights.append({
                "type": "error_pattern",
                "title": f"反复出现「{category_name(top_err)}」",
                "detail": f"出现 {error_counts[top_err]} 次。{repair_strategy_for(top_err)[:60]}",
            })

    # 洞察4：学习时长对比
    if last_minutes := sum(s.duration_minutes for s in last_week):
        this_m = sum(s.duration_minutes for s in this_week)
        change = (this_m - last_minutes) / last_minutes * 100
        if abs(change) > 20:
            insights.append({
                "type": "time_change",
                "title": f"学习时长{'增加' if change > 0 else '减少'}了 {abs(change):.0f}%",
                "detail": f"上周 {last_minutes} 分钟，本周 {this_m} 分钟。{'坚持得很好！' if change > 0 else '可以适当增加一点学习时间。'}",
            })

    # 洞察5：连续学习链
    if student.streak_chain >= 7:
        insights.append({
            "type": "streak",
            "title": f"已连续学习 {student.streak_chain} 天",
            "detail": "习惯是最好的老师，这个连续学习的节奏非常棒！",
        })

    return insights


def _generate_suggestions(student: Student) -> list[str]:
    """生成下周学习建议（G1）。"""
    suggestions: list[str] = []

    # 建议1：优先修复漏洞
    open_gaps = student.concept_gaps_open()
    if open_gaps:
        suggestions.append(f"下周优先修复 {len(open_gaps)} 个知识漏洞，特别是「{open_gaps[0].topic_name or open_gaps[0].topic_id}」。")

    # 建议2：ZPD 内的知识点
    try:
        from backend.services.learning_path import generate_weekly_plan
        plan = generate_weekly_plan(student)
        if plan.items:
            nxt = plan.items[0]
            suggestions.append(f"下周可以学习「{nxt.topic_name}」（{nxt.reason}）。")
    except Exception:  # noqa: BLE001
        pass

    # 建议3：思维模型
    if student.cognitive_profile.abstract_thinking < 0.4:
        suggestions.append("可以多使用「图形化思维」和「类比思维」来理解抽象概念，画图帮助理解。")

    # 建议4：学习习惯
    if student.streak_chain < 3:
        suggestions.append("尝试每天固定时间学习15分钟，连续学习会获得「不断链」徽章哦。")

    return suggestions[:3]
