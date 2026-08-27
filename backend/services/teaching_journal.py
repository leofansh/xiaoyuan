"""教学日志：从对话中提取教学洞察，支持自进化。"""

from datetime import datetime

from backend.models.student import Student, TeachingInsight, SessionSummary


def generate_insights(student: Student, summary: SessionSummary) -> list[TeachingInsight]:
    """从会话摘要中提取教学洞察。规则式提取，不依赖LLM。"""
    insights: list[TeachingInsight] = []
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. 信任建立洞察
    trust_insight = _analyze_trust(student, summary)
    if trust_insight:
        insights.append(trust_insight)

    # 2. 教学策略洞察
    strategy_insight = _analyze_strategy(student, summary)
    if strategy_insight:
        insights.append(strategy_insight)

    # 3. 情绪模式洞察
    emotion_insight = _analyze_emotion(student, summary)
    if emotion_insight:
        insights.append(emotion_insight)

    # 4. 学生风格洞察
    style_insight = _analyze_style(student, summary)
    if style_insight:
        insights.append(style_insight)

    return insights


def _analyze_trust(student: Student, summary: SessionSummary) -> TeachingInsight | None:
    """分析信任建立情况。需要多个信号才触发，降低误判。"""
    messages = summary.messages
    if len(messages) < 4:
        return None

    # 检测负面信号（需要至少2条含负面词的消息才触发）
    negative_signals = ["不信", "骗人", "讨厌", "烦死了", "没意思"]
    negate_words = ("不是", "没有", "才不", "别", "不要")

    user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
    negative_count = 0
    for msg in user_msgs:
        for signal in negative_signals:
            if signal in msg:
                # 检查是否被否定词包裹（"不是不信"不算不信）
                before = msg[:msg.index(signal)]
                if any(neg in before[-4:] for neg in negate_words if len(before) >= 4):
                    continue
                negative_count += 1
                break

    if negative_count >= 2:
        return TeachingInsight(
            date=summary.date,
            category="trust",
            insight="学生多次表达不信任，需要先建立关系再教学",
            what_worked="",
            what_failed="直接讲道理，没有先回应情绪",
            student_style="重视权威性和实用性，质疑时需要被认真对待",
        )
    return None


def _analyze_strategy(student: Student, summary: SessionSummary) -> TeachingInsight | None:
    """分析教学策略有效性。需要3次以上重复才判定无效。"""
    messages = summary.messages
    if len(messages) < 6:
        return None

    # 检测是否有多次重复解释（策略无效）
    user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
    repeat_count = sum(1 for msg in user_msgs if any(
        keyword in msg for keyword in ["还是不懂", "但是", "不对", "不是这样"]
    ))

    if repeat_count >= 3:
        return TeachingInsight(
            date=summary.date,
            category="strategy",
            insight="学生多次表示不理解，当前策略需要调整",
            what_worked="",
            what_failed="重复解释同一观点，没有换角度或降级",
            student_style="有主见，会坚持自己的观点",
        )
    return None


def _analyze_emotion(student: Student, summary: SessionSummary) -> TeachingInsight | None:
    """分析情绪变化。"""
    messages = summary.messages
    if len(messages) < 4:
        return None

    # 检测情绪恶化
    negative_words = ["累", "烦", "不想", "好难", "算了", "没意思"]
    first_half = messages[:len(messages)//2]
    second_half = messages[len(messages)//2:]

    first_negative = sum(1 for m in first_half if m.get("role") == "user"
                        and any(w in m["content"] for w in negative_words))
    second_negative = sum(1 for m in second_half if m.get("role") == "user"
                         and any(w in m["content"] for w in negative_words))

    if second_negative > first_negative:
        return TeachingInsight(
            date=summary.date,
            category="emotion",
            insight="对话过程中情绪恶化",
            what_worked="",
            what_failed="没有及时察觉情绪变化并调整",
            student_style="情绪变化快，需要更敏感地察觉",
        )
    return None


def _analyze_style(student: Student, summary: SessionSummary) -> TeachingInsight | None:
    """分析学生学习风格。"""
    messages = summary.messages
    user_msgs = [m["content"] for m in messages if m.get("role") == "user"]

    if not user_msgs:
        return None

    # 分析提问模式
    question_count = sum(1 for msg in user_msgs if "?" in msg or "？" in msg or "吗" in msg)
    short_answers = sum(1 for msg in user_msgs if len(msg) < 10)

    style_obs = []
    if question_count > len(user_msgs) * 0.3:
        style_obs.append("喜欢提问")
    if short_answers > len(user_msgs) * 0.5:
        style_obs.append("回答简短")

    if style_obs:
        return TeachingInsight(
            date=summary.date,
            category="style",
            insight=f"学习风格观察：{', '.join(style_obs)}",
            what_worked="",
            what_failed="",
            student_style="、".join(style_obs),
        )
    return None


def get_relevant_insights(student: Student, limit: int = 5) -> list[TeachingInsight]:
    """获取最近的相关教学洞察，用于注入system prompt。"""
    journal = student.teaching_journal
    if not journal:
        return []

    # 优先返回信任和策略类洞察（对教学影响最大）
    priority_order = {"trust": 0, "strategy": 1, "emotion": 2, "style": 3}
    sorted_journal = sorted(
        journal,
        key=lambda x: (priority_order.get(x.category, 99), x.date),
        reverse=False
    )

    # 去重：同类洞察只保留最新的
    seen_categories = set()
    result = []
    for insight in sorted_journal:
        key = insight.category
        if key not in seen_categories:
            seen_categories.add(key)
            result.append(insight)
            if len(result) >= limit:
                break

    return result


def format_insights_for_prompt(insights: list[TeachingInsight]) -> str:
    """将洞察格式化为system prompt片段。"""
    if not insights:
        return ""

    lines = ["## 教学经验（从历史对话中总结）"]
    for ins in insights:
        if ins.insight:
            lines.append(f"- {ins.insight}")
        if ins.what_failed:
            lines.append(f"  ⚠️ 避免：{ins.what_failed}")
        if ins.student_style:
            lines.append(f"  👤 学生风格：{ins.student_style}")

    return "\n".join(lines)
