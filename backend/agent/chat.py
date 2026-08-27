"""对话管理：会话生命周期 + 上下文组装 + 时间感知收尾。"""

import asyncio
from datetime import datetime
from typing import AsyncGenerator

from backend.agent import assessment, persona
from backend.agent.metacognition import detect_strategy, get_strategy_prompt
from backend.config import MAX_HISTORY_MESSAGES, SESSION_DEEP_MINUTES
from backend.models.student import Badge, SessionSummary, Student, StudentProfile
from backend.services import llm
from backend.services.content_filter import filter_llm_output
from backend.services.crisis import detect_crisis, crisis_intervention, record_crisis
from backend.services.repetition import schedule_review, get_due_reviews
from backend.services.teaching_journal import generate_insights, get_relevant_insights
from backend.services.wellbeing import check_time_limit
from backend.services.interest_extractor import extract_interests, personalized_opening
from backend.services.storage import StudentStorage, get_storage


def start_session(student: Student, mood: str) -> dict:
    """开始新会话：记录心情，生成开场白与模式建议。"""
    # 会话开始时先应用遗忘衰减
    assessment.apply_forgetting_decay(student)

    sess = student.current_session
    sess.state = "MODE_SELECT"
    sess.started_at = datetime.now().isoformat(timespec="seconds")
    sess.history = []
    sess.turn_count = 0
    sess.topic_id = ""
    sess.blind_spots_today = []
    sess.errors_reviewed = 0

    get_storage().add_mood(student, mood)

    suggestion = {"😊": "A", "😐": "A或B", "😣": "B"}.get(mood, "A")
    # V-P1-4：使用个性化开场白（引用学生兴趣）
    opening = personalized_opening(mood, student)
    if student.week_baseline_count >= 4:
        opening += "（悄悄说：这周我们都在充电呀，明天状态好的话来个小挑战？）"

    # 检查是否有待复习内容
    due_reviews = get_due_reviews(student)
    review_hint = ""
    if due_reviews:
        names = "、".join(rs.topic_name for rs in due_reviews[:3])
        review_hint = f"今天有{len(due_reviews)}个知识点该复习了：{names}～"

    return {
        "opening": opening,
        "mode_suggestion": suggestion,
        "streak": student.streak_chain,
        "due_reviews": [{"topic_id": rs.topic_id, "topic_name": rs.topic_name} for rs in due_reviews],
        "review_hint": review_hint,
    }


def select_mode(student: Student, mode: str) -> None:
    sess = student.current_session
    sess.mode = mode  # type: ignore[assignment]
    sess.state = "BLIND_SPOT" if mode == "A" else ("QUICK_REVIEW" if mode == "B" else "WEEKEND_CLEAR")
    get_storage().record_mode(student, mode)
    if mode == "B" and "💪 保底英雄" not in student.badges:
        student.badges.append("💪 保底英雄")


def _check_time_wrap(student: Student) -> bool:
    """深度模式超过时限→应主动收尾。"""
    sess = student.current_session
    if sess.mode != "A" or not sess.started_at:
        return False
    started = datetime.fromisoformat(sess.started_at)
    minutes = (datetime.now() - started).total_seconds() / 60
    return minutes >= SESSION_DEEP_MINUTES


MODE_INTENT_RULES = [
    (("A",), ["深入", "探索", "挑战", "学新", "深度", "a模式", "深度成长", "学点新", "攻坚"]),
    (("B",), ["快速", "过一遍", "保底", "简单", "轻松", "b模式", "快速过", "保底维稳", "不费力气", "过一下"]),
    (("weekend",), ["周末", "复习", "清零", "漏洞", "weekend", "补漏洞", "修复", "漏"]),
]


def _detect_mode_intent(message: str) -> str | None:
    """从学生回复中识别模式选择意图。"""
    if not message:
        return None
    msg = message.lower()
    for modes, keywords in MODE_INTENT_RULES:
        if any(kw in msg for kw in keywords):
            return modes[0]
    return None


_MODE_CONFIRM = {
    "A": "好呀，那我们今天就深入探索一下～🌸",
    "B": "没问题，快速过一遍，守住底线就是胜利💪",
    "weekend": "好嘞，周末修复时间到🌟 我们把漏洞逐个拆掉！",
}


async def process_message(
    student: Student, user_message: str, *, external_extra: str = ""
) -> AsyncGenerator[dict, None]:
    """处理学生消息：组装上下文 → 流式LLM → 解析评估 → 落盘。

    产出事件:
      {"type": "text", ...}   可见正文增量
      {"type": "eval", ...}   评估结果（含徽章、总结等）
      {"type": "error", ...}
    """
    storage = get_storage()
    sess = student.current_session

    # 【最高优先级】心理危机检测（SAFE-P0-1 + V-P1-1 修复误判）
    # 计算连续消极轮次（用于中度词判断，避免"好累"等日常词误触发）
    recent_user = [m["content"] for m in sess.history[-6:] if m.get("role") == "user"]
    neg_words = ["好累", "好烦", "不想", "不会", "不懂", "难", "崩溃", "绝望", "撑不住"]
    consecutive_neg = 0
    for m in reversed(recent_user):
        if any(w in m for w in neg_words):
            consecutive_neg += 1
        else:
            break
    crisis_level = detect_crisis(
        user_message or "",
        {"consecutive_negative_turns": consecutive_neg},
    )
    if crisis_level:
        record_crisis(student, crisis_level, user_message or "")
        storage.save(student)
        yield {"type": "text", "content": crisis_intervention(crisis_level)}
        yield {
            "type": "eval",
            "state": student.current_session.state,
            "badges": [],
            "progress": None,
            "emotion": None,
            "metacognition": "none",
            "anxiety": "high",
            "crisis": True,
            "crisis_level": crisis_level,
        }
        return

    # 盲区自报识别（简单启发：在盲区定位阶段的所有发言都记录）
    if sess.state == "BLIND_SPOT" and user_message and "不知道" not in user_message[:6]:
        assessment.record_blind_spot(student, user_message)

    # V-P0-3：模式对话引导——在 MODE_SELECT 状态，从学生文字回复自动识别模式意图
    if sess.state == "MODE_SELECT" and user_message:
        detected_mode = _detect_mode_intent(user_message)
        if detected_mode:
            select_mode(student, detected_mode)
            storage.save(student)
            yield {"type": "text", "content": _MODE_CONFIRM[detected_mode]}
            yield {
                "type": "eval",
                "state": student.current_session.state,
                "badges": [],
                "progress": None,
                "emotion": None,
                "metacognition": "none",
                "anxiety": "low",
            }
            return

    system_prompt = persona.build_system_prompt(student)

    extras: list[str] = []
    if external_extra:
        extras.append(external_extra)

    # SAFE-P1-2：防沉迷时间提醒（温柔提示，不强制阻断）
    if user_message and sess.state not in ("MODE_SELECT", "BLIND_SPOT"):
        time_hint = check_time_limit(student)
        if time_hint:
            extras.append(
                f"[系统提示：{time_hint} 请用共情的语气温柔提醒学生，"
                "但不强行结束，尊重她的选择。如果她表示继续，就继续当前教学]"
            )

    if _check_time_wrap(student):
        extras.append("[系统提示：本次深度会话时间已到15分钟，请立即自然收尾总结，进入WRAP_UP]")
    if user_message and any(
        k in user_message for k in ["累", "烦", "不想学", "好难", "不学", "不想", "休息", "玩会", "玩一会"]
    ):
        extras.append(
            "[系统提示：学生表达了疲惫/烦躁/想放弃的情绪。请先完全共情接纳，"
            "然后建议切换轻松方式或直接温柔收尾，绝不加码新任务，绝不让TA有愧疚感]"
        )
    if sess.state == "MODE_SELECT":
        extras.append(
            "[系统提示：学生还没有选择学习模式。如果她问「能不能不学」或表达抗拒："
            "①先接纳（当然可以呀/今天不想学也完全没问题）；②给她台阶——"
            "可以说只聊5分钟保底、或者明天状态好了再来；③再轻轻提一句可以和她说"
            "「🛡保底」或「🌳深度」或「周末」来选择方式，不想选就聊天下也好。"
            "如果她表达想学，引导她说出想深入还是快速过一遍。绝不批评、绝不说教]"
        )
    if sess.state == "ERROR_REVIEW":
        extras.append(
            "[系统提示：当前处于错题溯源阶段。请严格执行两问协议："
            "①「你觉得自己卡在哪一步了？」——引导她定位具体步骤"
            "②「你觉得这里为什么会卡住？是概念模糊还是粗心了？」——帮她识别思维漏洞"
            "问完两问后，根据回答判断是概念漏洞（需要回去补基础）还是粗心（温和标记即可）]"
        )

    # EP-P0-1：认知负荷动态注入（高难度 + 低掌握度时限制信息量）
    if sess.topic_id:
        node = syllabus.get_node(sess.topic_id)
        if node and node.difficulty >= 4 and student.mastery_score(sess.topic_id) < 0.5:
            extras.append(
                "[系统提示：当前知识点难度较高且学生掌握度低，"
                "本轮只讲一个最基础的直觉，不要展开推导和例题，用生活化比喻锚定]"
            )

    # EP-P0-1：连续困惑自动降级（最近2条学生消息都含困惑词）
    confusion_words = ["不懂", "不会", "不明白", "听不懂", "看不懂", "还是不懂", "搞不清楚"]
    recent_user_msgs = [m["content"] for m in sess.history[-4:] if m.get("role") == "user"]
    recent_user_msgs.append(user_message)
    confusion_count = sum(1 for m in recent_user_msgs[-2:] if any(k in m for k in confusion_words))
    if confusion_count >= 2:
        extras.append(
            "[系统提示：学生连续2轮表示困惑，认知负荷已超载。请立即降级："
            "用更简单的比喻、更小的步骤、更多等待确认；如果当前在讲解推导，回到最基础的直觉]"
        )

    # EP-P1-3：高焦虑干预流程
    anxiety_high_words = ["好难", "烦死了", "我不行", "做不到", "太难了", "不想做了"]
    if user_message and any(k in user_message for k in anxiety_high_words):
        extras.append(
            "[系统提示：学生当前焦虑水平较高。请先做情绪调节再继续学习："
            "①共情接纳（'这题确实有点难，觉得难很正常'）；"
            "②教一个简单的焦虑管理技巧（如'我们先深呼吸三次'）；"
            "③把任务拆到最小步（'我们先只看题目在问什么，不急着做'）；"
            "④绝不加码、绝不说'这么简单都不会']"
        )

    # EP-P0-2：元认知策略检测（自动建议适合的策略）
    strategy_key = detect_strategy(user_message) if user_message else None
    if strategy_key:
        strategy_prompt = get_strategy_prompt(strategy_key)
        extras.append(
            f"[系统提示：学生遇到卡点，建议引导她使用元认知策略。"
            f"先共情，然后温柔建议：'{strategy_prompt}'，"
            f"让她主动尝试，而不是直接告诉她怎么做]"
        )

    extra_instruction = "\n".join(extras)
    if extra_instruction:
        system_prompt += f"\n\n## 本轮特殊指令{extra_instruction}"

    # 认知发展适配（动态教学策略，EP-P0-3）
    cognitive_rules = persona._cognitive_adaptation(student.cognitive_profile)
    if cognitive_rules:
        system_prompt += "\n\n" + cognitive_rules

    # V-P0-2：计算验证器（LLM 算错自动修正，Function Calling 兜底）
    from backend.services.calc_verifier import verify_and_fix

    history = sess.history[-MAX_HISTORY_MESSAGES:]

    # V-P0-1：改用"缓冲 → 过滤/验证 → 模拟流式"模式，保证不适合内容不暴露
    full_reply = ""
    eval_data: dict | None = None
    try:
        async for event in llm.stream_chat(system_prompt, history, user_message):
            if event["type"] == "text":
                full_reply += event["content"]  # 只缓冲，不输出
            elif event["type"] == "eval":
                eval_data = event["data"]
    except Exception as e:  # noqa: BLE001
        await asyncio.to_thread(storage.save, student)
        yield {"type": "error", "message": f"小圆走神了一下（{type(e).__name__}），再试一次好吗？"}
        return

    # 内容过滤（V-P0-1：在输出前执行，保证安全）
    if full_reply:
        reply_text, _triggered = filter_llm_output(full_reply, {"student": student})
    else:
        reply_text = full_reply

    # 计算验证（V-P0-2：LLM 未调用工具时的心算出错兜底）
    if reply_text:
        reply_text, calc_fixes = verify_and_fix(reply_text)
        if calc_fixes:
            # 有修正时，在回复末尾补充一句提示（可选，避免打断主体）
            pass

    # 模拟逐字输出（打字机效果）
    for i in range(0, len(reply_text), 3):
        yield {"type": "text", "content": reply_text[i : i + 3]}
        await asyncio.sleep(0.01)

    new_badges: list[str] = []
    if eval_data:
        new_badges.extend(assessment.apply_eval(student, eval_data))
        state_now = student.current_session.state

        # 从 eval 自动识别当前主题（优先 mastery_updates，其次 gaps_found/gaps_cleared）
        if not sess.topic_id:
            candidates = (
                list((eval_data.get("mastery_updates") or {}).keys())
                + [g.get("topic_id", "") for g in (eval_data.get("gaps_found") or []) if g.get("topic_id")]
                + list(eval_data.get("gaps_cleared") or [])
            )
            # 过滤掉空串和 syllabus 里不存在的 id
            from backend.knowledge import syllabus as _syl
            for c in candidates:
                if c and _syl.get_node(c):
                    sess.topic_id = c
                    break

        # 推导徽章
        mastery_updates = eval_data.get("mastery_updates") or {}
        topic_score = mastery_updates.get(sess.topic_id) if sess.topic_id else None
        if assessment.check_derive_badge(student, state_now, topic_score):
            new_badges.append(Badge.DERIVE_BRAVE)

        # 变式徽章
        if assessment.check_transfer_badge(student, state_now):
            new_badges.append(Badge.TRANSFER)

    # 更新历史
    sess.history.append({"role": "user", "content": user_message})
    sess.history.append({"role": "assistant", "content": reply_text})
    if len(sess.history) > MAX_HISTORY_MESSAGES * 2:
        sess.history = sess.history[-MAX_HISTORY_MESSAGES * 2 :]
    sess.turn_count += 1

    # V-P1-4：从学生消息中提取新兴趣并保存
    new_interests = extract_interests(user_message, student.interests)
    if new_interests:
        student.interests.extend(new_interests)
        logger.info("提取到新兴趣: %s", new_interests)

    storage.save(student)

    yield {
        "type": "eval",
        "state": student.current_session.state,
        "badges": new_badges,
        "progress": (eval_data or {}).get("session_progress"),
        "emotion": (eval_data or {}).get("emotion"),
        "metacognition": (eval_data or {}).get("metacognition_observed", "none"),
        "anxiety": (eval_data or {}).get("anxiety_level", "low"),
        "used_thinking_model": (eval_data or {}).get("used_thinking_model"),
        "student_initiated_model": (eval_data or {}).get("student_initiated_model"),
    }


def end_session(student: Student) -> dict:
    """结束会话：学习链更新、周末清零检查、摘要落盘归档。"""
    storage = get_storage()
    streak_badge = storage.touch_streak(student)
    weekend_clear = False
    if student.current_session.mode == "weekend":
        weekend_clear = assessment.weekend_clear_check(student)

    new_badges: list[str] = []
    if streak_badge:
        new_badges.append("🔗 不断链7天")
    if weekend_clear:
        new_badges.append("🌟 清零大师")

    # 计算本次时长
    duration = 0
    if student.current_session.started_at:
        try:
            started = datetime.fromisoformat(student.current_session.started_at)
            duration = int((datetime.now() - started).total_seconds() / 60)
        except ValueError:
            pass

    # 解析 topic_name（优先 session.topic_id，否则从对话文本匹配知识点）
    topic_id = student.current_session.topic_id
    topic_name = ""
    if topic_id:
        from backend.knowledge import syllabus
        node = syllabus.get_node(topic_id)
        if node:
            topic_name = node.name
    if not topic_name:
        topic_name = _infer_topic_from_history(student.current_session.history)

    # 取开场心情
    mood = ""
    if student.mood_checkins:
        mood = student.mood_checkins[-1].get("mood", "")

    # 落盘摘要（含完整对话）
    summary_record = SessionSummary(
        date=datetime.now().strftime("%Y-%m-%d"),
        mode=student.current_session.mode or "",
        mood=mood,
        topic_id=topic_id,
        topic_name=topic_name,
        turns=student.current_session.turn_count,
        blind_spots=list(student.current_session.blind_spots_today),
        new_badges=list(new_badges),
        duration_minutes=duration,
        messages=list(student.current_session.history),
    )
    student.session_history.append(summary_record)

    summary = {
        "topic": student.current_session.topic_id,
        "turns": student.current_session.turn_count,
        "blind_spots": student.current_session.blind_spots_today,
        "open_gaps_left": len(student.concept_gaps_open()),
        "streak": student.streak_chain,
        "new_badges": new_badges,
    }

    student.total_sessions += 1
    student.current_session = type(student.current_session)()  # 重置为空会话
    update_student_profile(student)

    # 间隔复习：为本次学习的知识点安排复习
    # 如果 topic_id 为空，从 topic_name 反查
    from backend.knowledge import syllabus as _syl
    review_topic_id = topic_id
    if not review_topic_id and topic_name:
        for n in _syl.all_nodes():
            if n.name == topic_name:
                review_topic_id = n.id
                break
    # 只要学了新话题就安排复习（mastery 为 0 时默认用 0.4）
    if review_topic_id:
        mastery_val = student.mastery_score(review_topic_id, 0.4)
        schedule_review(student, review_topic_id, mastery_val)

    # 教学日志：从对话中提取教学洞察
    new_insights = generate_insights(student, summary_record)
    student.teaching_journal.extend(new_insights)
    # 保持日志不超过50条
    if len(student.teaching_journal) > 50:
        student.teaching_journal = student.teaching_journal[-50:]

    storage.save(student)
    return summary


def _infer_topic_from_history(history: list[dict[str, str]]) -> str:
    """从对话历史文本中匹配知识点名称作为 fallback（支持部分匹配）。"""
    from backend.knowledge import syllabus

    text = " ".join(m["content"] for m in history if m.get("role") == "user")
    if not text:
        return ""

    nodes = sorted(syllabus.all_nodes(), key=lambda n: len(n.name), reverse=True)

    # 精确包含匹配（优先）
    for node in nodes:
        if node.name in text:
            return node.name

    # 部分匹配：topic name 的任意 2+ 字子串出现在用户文本中
    for node in nodes:
        name = node.name
        for length in range(len(name), 1, -1):
            for start in range(len(name) - length + 1):
                substr = name[start:start + length]
                if substr in ("的", "了", "与", "及其", "用"):
                    continue
                if substr in text:
                    return node.name

    # 兜底：取第一条用户消息的前15字作为话题名
    user_msgs = [m["content"] for m in history if m.get("role") == "user"]
    if user_msgs:
        return user_msgs[0][:15]
    return ""


def submit_error_review(student: Student, q1: str, q2: str, error_type: str, topic_id: str = "") -> dict:
    """显式提交错题两问结果。"""
    new_badge = assessment.check_error_detective(student, q1, q2, error_type, topic_id)
    student.current_session.errors_reviewed += 1
    get_storage().save(student)
    return {"saved": True, "new_badges": ["🕵️ 错题侦探"] if new_badge else []}


def set_topic(student: Student, topic_id: str) -> bool:
    from backend.knowledge import syllabus

    node = syllabus.get_node(topic_id)
    if not node:
        return False
    student.current_session.topic_id = topic_id
    get_storage().save(student)
    return True


def check_cognitive_threshold(student: Student, topic_id: str) -> str | None:
    """检查学生认知阶段是否适合学习该知识点，返回提醒文本或 None（EP-P0-3）。"""
    from backend.knowledge import syllabus
    node = syllabus.get_node(topic_id)
    if not node:
        return None
    profile = student.cognitive_profile
    if syllabus.can_learn_topic(profile.cognitive_stage, node):
        return None
    stage_names = {"concrete": "具体运算", "transitional": "过渡期", "formal": "形式运算"}
    required = stage_names.get(node.required_cognitive_stage, node.required_cognitive_stage)
    current = stage_names.get(profile.cognitive_stage, profile.cognitive_stage)
    return (
        f"[系统提示：学生当前认知阶段({current})尚未达到学习'{node.name}'的建议阶段({required})。"
        f"请用更具体的方式讲解，多画图多举例，如果学生明显跟不上，"
        f"建议先回到前置知识点。不要直接说'你还没到学这个的水平'。]"
    )


def storage_instance() -> StudentStorage:
    return get_storage()


def update_student_profile(student: Student) -> None:
    """会话结束后从历史数据提取学生画像，更新跨会话记忆。"""
    from collections import Counter
    from backend.knowledge import syllabus

    profile = StudentProfile()
    node_names = {n.id: n.name for n in syllabus.all_nodes()}
    mode_labels = {"A": "深度成长", "B": "保底维稳", "weekend": "周末修复"}

    # 1) 历史盲区（从 session_history 归档的 blind_spots 提取，去重保序）
    seen_blind = set()
    for rec in student.session_history:
        for bs in rec.blind_spots:
            if bs not in seen_blind:
                profile.historical_blind_spots.append(bs)
                seen_blind.add(bs)

    # 2) 已掌握知识点（mastery >= 0.7）
    profile.mastered_topics = [
        node_names.get(k, k) for k, rec in student.mastery.items() if rec.score >= 0.7
    ]

    # 3) 待修复盲区（gaps 中 status=open 且 type=concept）
    profile.pending_blind_spots = [
        f"{g.topic_name or node_names.get(g.topic_id, g.topic_id)}: {g.evidence}"
        for g in student.concept_gaps_open()
    ]

    # 4) 情绪模式
    mood_counter = Counter(
        c.get("mood", "") for c in student.mood_checkins if c.get("mood")
    )
    if mood_counter:
        top_moods = mood_counter.most_common(2)
        parts = []
        for mood, cnt in top_moods:
            total = len(student.mood_checkins)
            pct = cnt / total
            if pct >= 0.6:
                parts.append(f"多数时候{mood}")
            elif pct >= 0.3:
                parts.append(f"偶尔{mood}")
        profile.mood_pattern = "，".join(parts) if parts else ""

    # 5) 常用模式
    mode_counter = Counter(
        m.get("mode", "") for m in student.mode_history if m.get("mode")
    )
    if mode_counter:
        top_mode = mode_counter.most_common(1)[0]
        label = mode_labels.get(top_mode[0], top_mode[0])
        profile.preferred_mode = f"常用{label}"

    # 6) 上次会话信息
    if student.session_history:
        last = student.session_history[-1]
        profile.last_session_topic = last.topic_name or ""
        profile.last_session_date = last.date or ""

    # 7) 元认知能力追踪
    if student.student_profile.metacognition_level > 0:
        profile.metacognition_level = student.student_profile.metacognition_level
    if student.student_profile.strategy_use:
        profile.strategy_use = dict(student.student_profile.strategy_use)
    profile.independent_success_rate = student.student_profile.independent_success_rate
    if student.student_profile.anxiety_pattern:
        profile.anxiety_pattern = student.student_profile.anxiety_pattern

    from datetime import datetime
    profile.updated_at = datetime.now().isoformat(timespec="seconds")

    student.student_profile = profile
