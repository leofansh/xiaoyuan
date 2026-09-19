"""对话管理：会话生命周期 + 上下文组装 + 时间感知收尾。"""

import asyncio
import logging
import random
from datetime import datetime
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

from backend.agent import assessment, persona
from backend.agent.metacognition import detect_strategy, get_strategy_prompt
from backend.config import MAX_HISTORY_MESSAGES, SESSION_DEEP_MINUTES, get_pure_mode
from backend.models.student import Badge, SessionSummary, Student, StudentProfile
from backend.services import llm
from backend.services.content_filter import filter_llm_output
from backend.services.crisis import detect_crisis, crisis_intervention, record_crisis
from backend.services.repetition import schedule_review, get_due_reviews
from backend.services.teaching_journal import (
    generate_insights, get_relevant_insights, record_misunderstanding,
)
from backend.services.wellbeing import check_time_limit
from backend.services.interest_extractor import extract_interests, personalized_opening
from backend.services.storage import StudentStorage, get_storage
from backend.services.ab_testing import get_ab_test_group


# 规格 12.4.5#2：内在动机过渡机制话术（常量放 chat.py，不放 persona.py）
_INTRINSIC_STREAK_THRESHOLD = 14
_INTRINSIC_FEEDBACK_PROB = 0.30
_INTRINSIC_FIRST_NOTICE = "你好像已经不需要宠物提醒了呢，这全靠你自己想学呀"
_INTRINSIC_POSITIVE_FEEDBACK = [
    "你又主动来啦，真好",
    "不用催就自己来学，太棒了",
    "你越来越会安排自己的学习啦",
]

# 小圆动态表情：开场心情 → 头像表情映射（😊开心/😐平静/😣疲惫）
_MOOD_AVATAR = {"😊": "happy", "😐": "calm", "😣": "tired"}


def _delayed_check_settles(eval_data: dict | None, topic_id: str) -> bool:
    """延迟验证结算校验（H1）。

    仅当本轮 eval 的 mastery_updates 中包含验证题对应知识点（即学生本轮
    确实作答了该验证题）才允许结算，防止"下一轮任意作答误结算"。

    Args:
        eval_data: 本轮 LLM 评估块
        topic_id: 当前延迟验证的知识点

    Returns:
        是否应结算。
    """
    if not topic_id:
        return False
    updates = (eval_data or {}).get("mastery_updates") or {}
    return topic_id in updates


def _derive_avatar_emotion(eval_data: dict | None, new_badges: list | None = None) -> str:
    """从小圆（AI 助教）视角派生头像表情 avatar_emotion。

    依据"学生情绪 + 会话事件"按优先级从高到低派生：
    徽章 > 顿悟 > 高焦虑 > 学生情绪 > 默认平静。
    危机短路分支不经过此函数（在调用处单独处理）。
    """
    if new_badges:
        return "proud"
    data = eval_data or {}
    # 顿悟/理解通过信号（eval_data 无此字段则跳过）
    if data.get("insight_detected"):
        return "surprised"
    if data.get("anxiety_level") == "high":
        return "worried"
    emotion = data.get("emotion")
    if emotion == "confident":
        return "happy"
    if emotion == "frustrated":
        return "sad"
    if emotion == "tired":
        return "tired"
    return "calm"


def start_session(student: Student, mood: str, source: str = "主动打开") -> dict:
    """开始新会话：记录心情，生成开场白与模式建议。

    source：会话入口来源（"主动打开"/被动提醒等），用于 A/B 测试的主动打开率统计。
    """
    # 会话开始时先应用遗忘衰减 + 认知画像衰减（B3）
    assessment.apply_forgetting_decay(student)
    from backend.agent.cognitive_assessment import apply_cognitive_decay
    apply_cognitive_decay(student)

    # V3.0 模块 L.5：刷新学段语言层级（按年级 + 认知画像推导）
    student.ensure_language_level()

    sess = student.current_session
    sess.state = "MODE_SELECT"
    sess.started_at = datetime.now().isoformat(timespec="seconds")
    sess.history = []
    sess.turn_count = 0
    sess.topic_id = ""
    sess.blind_spots_today = []
    sess.errors_reviewed = 0
    # V3.0 P0/I-11.9#4：挑战状态随会话重置（规格 11.9.4——每次会话可重新触发）
    sess.challenge_state = ""
    sess.challenge_problem_id = ""
    sess.challenge_presented = False
    # V3.0 P2/I-11.5：奇怪现象计数随会话重置（同一会话最多插 2 次，规格 11.5）
    student.v3_meta["strange_inserted"] = 0

    get_storage().add_mood(student, mood)

    # V3.0 P0: 轻量首学模式标记（纯学习模式下关闭娱乐化功能）
    pure_mode = get_pure_mode()
    if not pure_mode and (not student.session_history or student.total_sessions == 0):
        sess.lightweight_mode = True

    # 设计方案 98：A/B 测试——确定性分组 + 记录会话入口来源/分组
    group = get_ab_test_group(student)
    sess.entry_source = source
    sess.ab_group = group

    suggestion = {"😊": "A", "😐": "A或B", "😣": "B"}.get(mood, "A")
    # 组 A=兴趣引入开场（现状默认），组 B=传统开场（仅基础问候）
    opening = _opening_for_group(mood, student, group, pure_mode)
    if student.week_baseline_count >= 4:
        opening += "（悄悄说：这周我们都在充电呀，明天状态好的话来个小挑战？）"

    # V3.0 P1：开场注入宠物心情话术（规格3.5·集成点：chat.py 开场时注入宠物心情话术）
    # 规格 12.4.5#2：内在动机阶段减少宠物主动打扰，改用纯正反馈（无催促）
    intrinsic_stage = not pure_mode and student.streak_chain >= _INTRINSIC_STREAK_THRESHOLD
    if not pure_mode and not intrinsic_stage:
        try:
            from backend.services.pet import compute_mood, ensure_pet, interact_message
            pet = ensure_pet(student.pet)
            compute_mood(pet)  # 实时心情
            pet_msg, _anim = interact_message(pet, scene="开场")
            if pet_msg:
                opening += f"\n\n🐾 {pet_msg}"
        except ImportError:
            pass

    # 规格 12.4.5#2：内在动机过渡机制（连续 14 天主动学习）
    if intrinsic_stage:
        vm = student.v3_meta
        if vm.get("motivational_stage") != "intrinsic":
            vm["motivational_stage"] = "intrinsic"
            vm["intrinsic_notified_at"] = datetime.now().isoformat(timespec="seconds")
            opening += f"\n\n🌸 {_INTRINSIC_FIRST_NOTICE}"
        elif random.random() < _INTRINSIC_FEEDBACK_PROB:
            opening += f"\n\n🌸 {random.choice(_INTRINSIC_POSITIVE_FEEDBACK)}"

    # 检查是否有待复习内容
    due_reviews = get_due_reviews(student)
    review_hint = ""
    if due_reviews:
        names = "、".join(rs.topic_name for rs in due_reviews[:3])
        review_hint = f"今天有{len(due_reviews)}个知识点该复习了：{names}～"

    # V3.0 P0/I-11.9#9：次日思考题询问（规格 11.9.5——第二天开场小圆主动问）
    if not pure_mode:
        _tp = student.insights.get("current_thinking_problem")
        if _tp and not _tp.get("solved"):
            try:
                given_day = datetime.fromisoformat(_tp["given_at"]).date()
                # 隔天（含更久）才问；当天留的题不当场追
                if given_day < datetime.now().date():
                    opening += (
                        f"\n\n💭 昨天那道思考题，你有没有突然想通？"
                        f"「{_tp['question']}」——不着急，好问题值得慢慢想。"
                    )
            except (ValueError, KeyError, TypeError):
                pass

    # V3.0 模块 L.4.1 + H1：延迟验证/掌握验证开场检查
    # get_due_verifications 是 get_due_delayed_checks 的增强（含 1 天延迟验证与
    # 7 天掌握验证两类，按到期日排序），此处统一消费，避免同一知识点重复出题。
    # 复用间隔复习调度器：验证题 = 复习题。有到期任务时优先呈现（先于复习提示）。
    try:
        from backend.services.mastery_tracker import get_due_verifications
        from backend.services.repetition import generate_retrieval_question
        _due_vf = get_due_verifications(student)
        # H1：残留字段清理——当前验证知识点若已无到期排期则清空（跨会话残留 bug）
        if sess.delayed_check_topic_id and not any(
            rs.topic_id == sess.delayed_check_topic_id for rs in _due_vf
        ):
            sess.delayed_check_topic_id = ""
        if not pure_mode:
            if _due_vf:
                _rc = _due_vf[0]
                _q = generate_retrieval_question(student, _rc.topic_id)
                if _q:
                    sess.delayed_check_topic_id = _rc.topic_id
                    opening += (
                        f"\n\n⏱️ 昨天你说「{_rc.topic_name}」你懂了，"
                        f"今天我们 30 秒热个身——{_q}\n"
                        "（不用有压力，试试就好～）"
                    )
    except ImportError:
        pass

    return {
        "opening": opening,
        "mode_suggestion": suggestion,
        "streak": student.streak_chain,
        "due_reviews": [{"topic_id": rs.topic_id, "topic_name": rs.topic_name} for rs in due_reviews],
        "review_hint": review_hint,
        # L.4.1：标记本次开场是否带延迟验证（前端可据此弱化复习提示）
        "delayed_check": bool(sess.delayed_check_topic_id),
        # 小圆动态表情：开场头像表情（按心情打卡派生）
        "avatar_emotion": _MOOD_AVATAR.get(mood, "calm"),
    }


def _opening_for_group(mood: str, student: Student, group: str, pure_mode: bool) -> str:
    """按 A/B 测试组生成开场白（设计方案 98）。

    组 A（含 ab_test 未启用时 group=""，保持现状）：兴趣引入开场
    （个性化开场白 + 兴趣题 + 剧情铺垫 + 好奇心钩子）。
    组 B：传统开场，仅 OPENING_BY_MOOD 基础问候，不注入兴趣题/兴趣开场白/额外钩子。
    """
    from backend.agent.persona import OPENING_BY_MOOD
    if group == "B":
        return OPENING_BY_MOOD.get(mood, OPENING_BY_MOOD["😐"])

    # 组 A / 现状：个性化开场白（引用学生兴趣）
    opening = personalized_opening(mood, student)
    if not pure_mode:
        # 从兴趣引出第一个数学问题
        if student.interests:
            try:
                from backend.services.interest_extractor import get_opening_problem
                opening_problem = get_opening_problem(student.interests[0])
                if opening_problem:
                    opening += f"\n\n对了，我有个有趣的问题想请教你：{opening_problem}"
            except ImportError:
                pass
        # 连续剧情铺垫（昨天学会的技巧今天派上用场，规格 11.7）
        _prelude = _yesterday_prelude(student)
        if _prelude:
            opening = f"{_prelude}\n\n{opening}"
        # 开场好奇心钩子（悬念化开局，铺垫当天主题）
        try:
            from backend.agent.persona import pick_opening_hook
            hook = pick_opening_hook()
            if hook:
                opening = f"✨ {hook}\n\n{opening}"
        except ImportError:
            pass
    return opening


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


_MINOR_CONFIRM_WORDS = {
    "对", "嗯", "好", "是", "对呀", "对对", "嗯嗯", "好的", "是的",
    "ok", "OK", "对啊", "对!",
}


def _is_minor_confirmation(msg: str) -> bool:
    """对话小确认（"对""嗯"等）判定：确定性过滤，避免刷分（规格 5.3/5.8）。"""
    if not msg:
        return False
    stripped = msg.strip()
    if len(stripped) > 4:
        return False
    return stripped in _MINOR_CONFIRM_WORDS


def _yesterday_prelude(student: Student) -> str:
    """连续剧情铺垫（I-11.7）：昨天/近日学会的技巧，今天开场提一句。

    取 session_history 最后一条，若日期在 1~3 天前且含话题名，返回铺垫话术。
    """
    if not student.session_history:
        return ""
    last = student.session_history[-1]
    topic_name = (last.topic_name or "").strip()
    if not topic_name or not last.date:
        return ""
    try:
        last_day = datetime.strptime(last.date, "%Y-%m-%d").date()
    except ValueError:
        return ""
    days_since = (datetime.now().date() - last_day).days
    if not 1 <= days_since <= 3:
        return ""
    return (
        f"🌸 昨天我们搞定了「{topic_name}」，今天可能会用到哦——"
        "你昨天学会的技巧，今天要派上大用场啦！"
    )


# ============ V3.0 P0/I-11.9#4：主动挑战状态机（规格 11.9.4） ============
_CHALLENGE_DECLINE_WORDS = ("不想", "不敢", "算了", "不要", "不挑战", "先不", "不了", "怕", "不试", "没兴趣", "下次", "太难了")
_CHALLENGE_ACCEPT_WORDS = ("挑战", "试试", "来呀", "好啊", "好呀", "可以", "敢", "来吧", "想试", "要试")
_CHALLENGE_GIVEUP_WORDS = ("不想做", "放弃", "不挑战了", "做不出来", "不做了", "太难了")


def _maybe_open_challenge(student: Student) -> None:
    """挑战机会窗口：掌握度达标或连续答对后，从题库选定一道挑战题（规格 11.9.4）。

    仅在本次会话尚未邀请过、非纯学习模式、且处于教学环节时触发。
    """
    sess = student.current_session
    if sess.challenge_state:
        return
    if get_pure_mode() or not sess.topic_id:
        return
    if sess.state in ("GREETING", "MODE_SELECT", "BLIND_SPOT") or sess.turn_count < 5:
        return
    mastery = student.mastery_score(sess.topic_id)
    if mastery < 0.6 and sess.consecutive_correct < 2:
        return
    from backend.knowledge.challenge_problems import get_challenge_by_topic, get_random_challenge
    prob = get_challenge_by_topic(sess.topic_id) or get_random_challenge(max_difficulty=4)
    if not prob:
        return
    sess.challenge_state = "invited"
    sess.challenge_problem_id = prob.id
    sess.challenge_presented = False


def _challenge_state_machine(student: Student, user_message: str) -> None:
    """挑战状态机推进（规格 11.9.4）：

    - invited → 孩子表态：接受 → active；拒绝 → declined
      （不依赖 presented——即使 LLM 尚未复制完整题面，接受也立即推进，
      persona active 分支会自然注入题目+提示）
    - active 且孩子明确放弃 → declined（不算失败，绝不勉强）
    """
    sess = student.current_session
    msg = user_message or ""
    if sess.challenge_state == "invited":
        if any(w in msg for w in _CHALLENGE_DECLINE_WORDS):
            sess.challenge_state = "declined"
        elif any(w in msg for w in _CHALLENGE_ACCEPT_WORDS):
            sess.challenge_state = "active"
    elif sess.challenge_state == "active" and any(w in msg for w in _CHALLENGE_GIVEUP_WORDS):
        sess.challenge_state = "declined"


def _challenge_present_confirm(student: Student, reply_text: str) -> None:
    """确认小圆已真正发出挑战（含题目原文或任一邀请话术 → 标记 presented）。

    presented 用于 persona 避免重复邀请文案；接受/拒绝判定由状态机独立完成。
    """
    sess = student.current_session
    if sess.challenge_state != "invited" or sess.challenge_presented:
        return
    from backend.knowledge.challenge_problems import CHALLENGE_BANK
    prob = next((p for p in CHALLENGE_BANK if p.id == sess.challenge_problem_id), None)
    if prob and (prob.question[:12] in reply_text or prob.title in reply_text):
        sess.challenge_presented = True
        return
    from backend.agent.persona import CHALLENGE_INVITE_PHRASES as _INVITES
    if any(ph[:8] in reply_text for ph in _INVITES):
        sess.challenge_presented = True


def _settle_challenge_success(student: Student, *, independent_success: bool) -> list[dict]:
    """挑战成功结算（规格 11.9.4：3-5倍XP + 必掉稀有以上卡 + 徽章 + 教学日志特别记录）。

    仅当挑战处于 active 且本轮为独立答对时结算。
    返回 challenge_success SSE 载荷（含掉落卡与徽章），空列表表示本轮无结算。
    """
    import random as _random

    sess = student.current_session
    # 挑战已真正呈现（presented 或进入 active）且本轮独立答对才结算——
    # 放宽到 invited：孩子可能不明确说"好呀"就自顾自开始解题
    if (not independent_success
            or not sess.challenge_presented
            or sess.challenge_state not in ("invited", "active")):
        return []

    from backend.knowledge.cards import drop_card, ensure_cards
    from backend.services.pet import add_xp, ensure_pet

    student.insights["challenge_completed"] = int(student.insights.get("challenge_completed", 0)) + 1

    # 3-5 倍普通答题 XP（普通答对 +5）
    xp = 5 * _random.randint(3, 5)
    student.pet = ensure_pet(student.pet)
    add_xp(student.pet, xp, source="challenge")

    # 必掉稀有以上卡片（rare/epic/legendary）
    force_rarity = _random.choice(["rare", "epic", "legendary"])
    student.cards = ensure_cards(student.cards)
    card_drop = drop_card(
        student.cards, source="challenge",
        knowledge_node=sess.topic_id, force_rarity=force_rarity,
    )

    # 挑战徽章（挑战者/难题杀手，规格 11.9.6）
    challenge_badges = assessment.check_insight_badges(student, "")

    # 教学日志特别记录（规格 11.9.4）
    from backend.models.student import TeachingInsight
    from backend.knowledge.challenge_problems import CHALLENGE_BANK
    prob = next((p for p in CHALLENGE_BANK if p.id == sess.challenge_problem_id), None)
    student.teaching_journal.append(TeachingInsight(
        date=datetime.now().strftime("%Y-%m-%d"),
        category="challenge",
        insight=f"挑战成功：孩子独立完成了《{prob.title if prob else '挑战题'}》，获得 {xp} XP",
        what_worked="主动挑战机制：掌握度达标后邀请挑战，大额奖励强化成就感",
    ))

    sess.challenge_state = "solved"
    sess.challenge_problem_id = ""

    badge_payload = None
    if challenge_badges:
        _b = challenge_badges[0]
        badge_payload = {
            "name": _b,
            "icon": (Badge.ALL.get(_b) or {}).get("icon", "🏅"),
            "desc": (Badge.ALL.get(_b) or {}).get("desc", ""),
        }
    return [{
        "type": "challenge_success",
        "title": prob.title if prob else "",
        "xp_reward": xp,
        "card_dropped": _drop_payload(card_drop) if card_drop.get("success") else None,
        "badge_unlocked": badge_payload,
    }]


# ============ V3.0 模块 L：双向有效交流（规格 L.2/L.3/L.4/L.7） ============
# 可触发费曼检查 / 台阶诊断的"教学节点"集合（规格 L.4/L.3）
TEACHING_STATES = frozenset({
    "CORE_DERIVE", "EXAMPLE_CHECK", "OPTIONAL_VARIANT", "QUICK_REVIEW",
    "FIX_ONE_ERROR", "WEEKEND_CLEAR", "ANALOGY_EXPLANATION", "VISUALIZATION",
    "ERROR_REVIEW", "ERROR_ROOT_CAUSE", "BREAK_SUGGESTION", "THINKING_TRAINING",
})


def _record_misunderstanding(
    student: Student, *, signal: str, detail: str, quote: str,
    resolution: str, resolved: bool, topic_id: str = "",
) -> None:
    """记录假性理解 / 理解纠偏事件（规格 L.4，上限 50 条）。

    同步记入教学日志（TeachingInsight，规格 L.9 新增 misunderstanding 事件类型），
    与 misunderstanding_events 详表双写。
    """
    event = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "signal": signal,
        "detail": detail,
        "quote": quote[:100],
        "resolution": resolution,
        "resolved": resolved,
        "topic_id": topic_id,
    }
    student.misunderstanding_events.append(event)
    if len(student.misunderstanding_events) > 50:
        student.misunderstanding_events = student.misunderstanding_events[-50:]
    record_misunderstanding(student, event)


async def _llm_classify_fallback(student: Student, user_message: str):
    """L.2 LLM 兜底通道：规则未命中时用 LLM 判断孩子表达是否属 8 类信号之一（规格 L.2 双通道）。

    触发条件：非纯学习模式 + 教学节点 + 消息长度适中 + 配置了 API Key。
    失败/超时/无 Key → 静默返回 None（由 persona 自然应对，绝不阻塞主流程）。

    Returns:
        UnderstandingSignal | None
    """
    from backend.config import get_api_key
    from backend.services.understand_detector import (
        LLM_CLASSIFY_PROMPT, parse_llm_classify,
    )

    msg = (user_message or "").strip()
    # 消息过长/过短都不值得 LLM 兜底（过短多为语气词，过长是正常提问）
    if not (2 <= len(msg) <= 60):
        return None
    if not get_api_key():
        return None
    sess = student.current_session
    topic = sess.topic_id or ""
    context = f"当前知识点：{topic or '（非特定知识点）'}"
    try:
        raw = await asyncio.wait_for(
            llm.simple_chat(LLM_CLASSIFY_PROMPT, f"{context}\n孩子说的话：{msg}"),
            timeout=6,
        )
    except Exception:
        logger.info("L.2 LLM 兜底分类失败，静默降级（persona 自然应对）")
        return None
    return parse_llm_classify(raw)


def _build_understand_short_reply(student: Student, sig) -> str:
    """根据理解信号构建短路回复（不进入 LLM）。

    Returns:
        非空字符串 → 直接输出并 return；空串 → 信号由 LLM 对症指令处理（extras 注入）。
    """
    import random as _rnd

    from backend.knowledge import syllabus as _syl
    from backend.services.understand_detector import (
        FEYNMAN_OPENERS, build_step_diagnostic, pick_confirm_phrase,
    )

    sess = student.current_session
    s = sig.signal

    # 假性理解 "知道了/嗯/哦" → 费曼检查（仅教学节点 + 有知识点 + 上条助手消息够长）
    if s == "fake_understand":
        if sess.topic_id and sess.state in TEACHING_STATES:
            _last = next(
                (m["content"] for m in reversed(sess.history) if m.get("role") == "assistant"),
                "",
            ) or ""
            if len(_last) >= 12:
                _node = _syl.get_node(sess.topic_id)
                sess.understand_confirm_from = sess.state
                sess.feynman_topic_id = sess.topic_id
                sess.feynman_topic_name = _node.name if _node else sess.topic_id
                sess.state = "UNDERSTAND_CONFIRM"
                return _rnd.choice(FEYNMAN_OPENERS)
        return ""  # 不在教学节点/无知识点 → LLM 自然应对

    # 元认知不足 "我就是不会" → 台阶式诊断（需节点配置 diagnostic_steps）
    if s == "metacognition_gap":
        _node = _syl.get_node(sess.topic_id) if sess.topic_id else None
        _steps = _syl.get_diagnostic_steps(_node) if _node else []
        if _steps:
            sess.understand_confirm_from = sess.state
            sess.diagnostic_topic_id = sess.topic_id
            sess.state = "UNDERSTAND_CONFIRM"
            return build_step_diagnostic(_node.name, _steps)
        return ""

    # "我不会" / "看不懂" → 确认提问（直接短路，不改状态，规格 L.2）
    if s in ("cant_do", "text_confusion"):
        return pick_confirm_phrase(s)

    # claimed_understand / method_conflict / emotional_fatigue / calc_wrong → 不走短路
    return ""


def _handle_understand_confirm_answer(student: Student, user_message: str) -> str | None:
    """处理孩子在 UNDERSTAND_CONFIRM 状态下的回答（费曼复述 / 台阶选择）。

    Returns:
        非空字符串 → 本轮直接输出该话术（费曼通过/失败、重示台阶）
        None → 已恢复原教学状态并设置 understand_pending_instruction，继续走 LLM 流程
    """
    import random as _rnd
    import re as _re

    from backend.knowledge import syllabus as _syl
    from backend.services.mastery_tracker import schedule_delayed_check
    from backend.services.understand_detector import (
        FEYNMAN_FAIL_GUIDE, FEYNMAN_PASS_PRAISE, build_step_diagnostic,
    )

    sess = student.current_session
    msg = (user_message or "").strip()

    # —— 费曼复述 ——
    if sess.feynman_topic_id:
        topic_id = sess.feynman_topic_id
        topic_name = sess.feynman_topic_name or topic_id
        restored = sess.understand_confirm_from or "CORE_DERIVE"
        # 视为通过：实质复述（>=4 字且不含失败词）
        fail_words = ("忘了", "不知道", "不会说", "记不清", "说不出来", "不记得")
        passed = len(msg) >= 4 and not any(w in msg for w in fail_words)
        # 复位费曼检查临时字段
        sess.feynman_topic_id = ""
        sess.feynman_topic_name = ""
        sess.understand_confirm_from = ""
        sess.state = restored
        if passed:
            # L.4：费曼通过 → 表扬 + 登记次日延迟验证 + 记录事件（已消解）
            schedule_delayed_check(student, topic_id, topic_name)
            _record_misunderstanding(
                student, signal="fake_understand", detail="费曼复述通过",
                quote=msg, resolution="feynman_pass", resolved=True, topic_id=topic_id,
            )
            return _rnd.choice(FEYNMAN_PASS_PRAISE)
        # L.4：费曼失败 → 鼓励 + 记录未消解事件 + 设换讲法指令（下轮 LLM 执行）
        _record_misunderstanding(
            student, signal="fake_understand", detail="费曼复述失败",
            quote=msg, resolution="feynman_fail", resolved=False, topic_id=topic_id,
        )
        sess.understand_pending_instruction = (
            f"[系统提示：孩子刚在费曼检查中复述失败（假性理解）。"
            f"请换一种与刚才完全不同的讲法/比喻重新讲解「{topic_name}」，"
            f"讲完再请她用一句话复述]"
        )
        return _rnd.choice(FEYNMAN_FAIL_GUIDE)

    # —— 台阶式诊断（选第 N 步 / 觉得都会 / 其他） ——
    if sess.diagnostic_topic_id:
        topic_id = sess.diagnostic_topic_id
        node = _syl.get_node(topic_id)
        steps = _syl.get_diagnostic_steps(node) if node else []
        topic_name = node.name if node else topic_id
        restored = sess.understand_confirm_from or "CORE_DERIVE"
        m = _re.search(r"(\d+)", msg)
        step_no = int(m.group(1)) if m else 0
        sess.diagnostic_topic_id = ""
        sess.understand_confirm_from = ""
        sess.state = restored
        if 1 <= step_no <= len(steps):
            # 选定了卡壳台阶 → 设指令让 LLM 只讲这一层 → 走 LLM 流程
            step = steps[step_no - 1]
            sess.understand_pending_instruction = (
                f"[系统提示：孩子自报卡在「{topic_name}」的台阶{step['step']}「{step['name']}」。"
                f"本轮请只用最基础直觉讲解这一步（拆到最小可理解单位），"
                f"确认她懂了再继续下一层。{step.get('check_question', '')}]"
            )
            return None
        if any(w in msg for w in ("都会", "都行", "都懂", "都可以", "差不多")):
            sess.understand_pending_instruction = (
                f"[系统提示：孩子觉得「{topic_name}」都会但实际掌握度未达标。"
                f"请从台阶1开始快速逐层过一遍，每层用一道小练习确认，找出真正薄弱处]"
            )
            return None
        # 无法解析 → 重新展示台阶（保持 UNDERSTAND_CONFIRM）
        sess.diagnostic_topic_id = topic_id
        sess.understand_confirm_from = sess.state
        sess.state = "UNDERSTAND_CONFIRM"
        return build_step_diagnostic(topic_name, steps)

    return None


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

    # V3.0 P0: 顿悟时刻检测（纯学习模式下关闭）
    insight = None
    insight_card_drop = None
    insight_badges: list[str] = []
    pure_mode = get_pure_mode()
    if not pure_mode:
        try:
            from backend.services.insight_detector import detect_insight, is_delayed_insight
            # 延迟顿悟优先：存在未解决思考题时，"昨天那道题想通了"类信号优先于通用感叹词
            insight = None
            _tp = student.insights.get("current_thinking_problem")
            if _tp and not _tp.get("solved"):
                insight = is_delayed_insight(user_message)
            if not insight:
                insight = detect_insight(user_message, sess.history)
            if insight and insight.confidence >= 0.7:
                sess.insight_today = getattr(sess, 'insight_today', 0) + 1
                student.insights["total_count"] += 1
                # 延迟顿悟：标记思考题已解决 + 计数（须在徽章判定前，供"想通5道"徽章读取）
                if insight.insight_type == "delayed":
                    _tp = student.insights.get("current_thinking_problem")
                    if _tp and not _tp.get("solved"):
                        _tp["solved"] = True
                        student.insights["thinking_problems_solved"] = int(
                            student.insights.get("thinking_problems_solved", 0)
                        ) + 1
                student.insights["history"].append({
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "type": insight.insight_type,
                    "quote": insight.student_quote[:100],
                    "knowledge_node": sess.topic_id,
                    "xp_reward": 100,
                })
                # V3.0 P0/验收11.9#5：大额奖励结算 —— 宠物 +100 XP + 概率史诗/传说卡
                import random as _random
                from backend.knowledge.cards import drop_card, ensure_cards
                from backend.services.pet import add_xp, ensure_pet
                student.pet = ensure_pet(student.pet)
                add_xp(student.pet, 100, source="insight")
                student.cards = ensure_cards(student.cards)
                force_rarity = "epic" if _random.random() < 0.7 else "legendary"
                insight_card_drop = drop_card(
                    student.cards, source="insight",
                    knowledge_node=sess.topic_id, force_rarity=force_rarity,
                )
                # V3.0 P0/验收11.9#11：顿悟徽章判定（初次/思考者/达人/思想者/延迟顿悟）
                insight_badges = assessment.check_insight_badges(student, insight.insight_type)
        except ImportError:
            pass

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
    # D1：持久化连续负面情绪轮数
    sess.consecutive_negative_turns = consecutive_neg
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
            # 小圆动态表情：危机时小圆担忧/难过（severe→sad，其余→worried）
            "avatar_emotion": "sad" if crisis_level == "severe" else "worried",
        }
        return

    # V3.0 模块 L：UNDERSTAND_CONFIRM 状态——费曼复述 / 台阶选择答语处理（纯规则短路）
    _uc_resumed_llm = False  # 本回答已由确认流程消费（如"选第N步"），本轮不再做信号检测
    if not pure_mode and sess.state == "UNDERSTAND_CONFIRM":
        _uc_reply = _handle_understand_confirm_answer(student, user_message)
        if _uc_reply:
            sess.history.append({"role": "user", "content": user_message})
            sess.history.append({"role": "assistant", "content": _uc_reply})
            if len(sess.history) > MAX_HISTORY_MESSAGES * 2:
                sess.history = sess.history[-MAX_HISTORY_MESSAGES * 2 :]
            sess.turn_count += 1
            storage.save(student)
            yield {"type": "text", "content": _uc_reply}
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
        # _uc_reply 为 None：台阶选择已解析为 understand_pending_instruction，
        # 原始教学状态已恢复，继续走 LLM 流程（指令在 extras 注入）
        _uc_resumed_llm = True

    # 盲区自报识别（简单启发：在盲区定位阶段的所有发言都记录）
    if sess.state == "BLIND_SPOT" and user_message and "不知道" not in user_message[:6]:
        assessment.record_blind_spot(student, user_message)

    # V3.0 K.2：认知卸载检测（纯规则，纯学习模式下关闭，规格 K.2）
    offload_signals: list = []
    if not pure_mode:
        try:
            from backend.services.offload_detector import detect_offload_signals
            _recent_user = [m["content"] for m in sess.history[-4:] if m.get("role") == "user"]
            _recent_user.append(user_message or "")
            offload_signals = detect_offload_signals(student, user_message, _recent_user)
            for _sig in offload_signals:
                student.offload_events.append({
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "signal": _sig.signal,
                    "confidence": _sig.confidence,
                    "detail": _sig.detail,
                    "student_quote": _sig.student_quote[:100],
                    "resolved": False,
                })
        except ImportError:
            pass

    # V3.0 P3 模块G：共创模式——已进入共创流程时走解释性状态机（不进 LLM 教学循环）
    from backend.pbl.co_creation import advance_co_creation, is_co_creation_state, step_from_state
    if is_co_creation_state(sess.state):
        result = advance_co_creation(step_from_state(sess.state), user_message or "")
        sess.state = result["state"]
        sess.history.append({"role": "user", "content": user_message})
        sess.history.append({"role": "assistant", "content": result["reply"]})
        storage.save(student)
        yield {"type": "text", "content": result["reply"]}
        yield {
            "type": "eval",
            "state": sess.state,
            "badges": [],
            "progress": None,
            "emotion": None,
            "metacognition": "none",
            "anxiety": "low",
            "co_creation": True,
        }
        return

    # V-P0-3：模式对话引导——在 MODE_SELECT 状态，从学生文字回复自动识别模式意图
    if sess.state == "MODE_SELECT" and user_message:
        # V3.0 P3 模块G：共创意图识别（优先于模式选择）——把对话引向共创
        from backend.pbl.co_creation import detect_co_creation_intent, start_co_creation
        if detect_co_creation_intent(user_message):
            flow = start_co_creation(user_message)
            sess.state = flow["state"]
            sess.history.append({"role": "user", "content": user_message})
            sess.history.append({"role": "assistant", "content": flow["reply"]})
            storage.save(student)
            yield {"type": "text", "content": flow["reply"]}
            yield {
                "type": "eval",
                "state": sess.state,
                "badges": [],
                "progress": None,
                "emotion": None,
                "metacognition": "none",
                "anxiety": "low",
                "co_creation": True,
            }
            return
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
        # V3.0 P0：孩子表达学习意图（但未明确模式）→ 提示前端展示模式快捷栏
        # 轻量首学模式期间不弹出（前10分钟自然聊天，10.3.4）
        if not getattr(getattr(student, 'current_session', None), 'lightweight_mode', False) and any(
            k in user_message for k in ["学", "做", "开始", "来一道", "题", "试试", "练", "讲"]
        ):
            yield {"type": "mode_hint", "content": "show"}

    # V3.0 P0/I-11.9#4：挑战状态机推进 + 机会窗口（规格 11.9.4，须在 prompt 组装前触发）
    if not pure_mode:
        _challenge_state_machine(student, user_message)
        _maybe_open_challenge(student)

    # ---- V3.0 模块 L：双向有效交流——理解信号检测与处理（纯规则，纯学习模式关闭）----
    # 孩子在教学节点表达模糊（"我不会""知道了""看不懂"等），先按信号短路确认，
    # 不进 LLM（规格 L.2/L.3/L.4）。UNDERSTAND_CONFIRM 状态在函数头部已消费，这里不会重复。
    understand_extra = ""
    if not pure_mode and not _uc_resumed_llm and sess.state not in ("MODE_SELECT", "GREETING", "BLIND_SPOT", "UNDERSTAND_CONFIRM"):
        try:
            from backend.services.understand_detector import classify_utterance
            _sig = classify_utterance(user_message or "")
        except ImportError:
            _sig = None
        # L.2 LLM 兜底通道（规格：关键词规则优先 + LLM 判断兜底，命中任一即触发确认流程）
        if _sig is None:
            _sig = await _llm_classify_fallback(student, user_message or "")
        if _sig is not None:
            sess.current_understand_signal = _sig.signal
            # 防死循环：同一信号 2 轮内重复命中 → 不再短路，仅注入得体指令自然应对
            _repeated = (
                sess.last_understand_signal == _sig.signal
                and sess.understand_signal_count - sess.last_understand_turn <= 2
            )
            sess.last_understand_signal = _sig.signal
            sess.last_understand_turn = sess.understand_signal_count
            sess.understand_signal_count += 1
            understand_reply = ""
            if not _repeated:
                understand_reply = _build_understand_short_reply(student, _sig)
            if understand_reply:
                # 短路输出：确认流程话术（不发 LLM、不做评估，规格 L.2）
                sess.history.append({"role": "user", "content": user_message})
                sess.history.append({"role": "assistant", "content": understand_reply})
                if len(sess.history) > MAX_HISTORY_MESSAGES * 2:
                    sess.history = sess.history[-MAX_HISTORY_MESSAGES * 2 :]
                sess.turn_count += 1
                storage.save(student)
                yield {"type": "text", "content": understand_reply}
                yield {
                    "type": "eval",
                    "state": student.current_session.state,
                    "badges": [],
                    "progress": None,
                    "emotion": None,
                    "metacognition": "none",
                    "anxiety": "low",
                    "understand_signal": _sig.signal,
                }
                return
            # 非短路信号（声称已懂 / 方法冲突 / 重复表达）→ 注入 LLM 对症指令
            if _sig.signal == "claimed_understand":
                understand_extra = (
                    "[系统提示：孩子声称已懂。口头确认不算掌握（L.4）：不要直接接受，"
                    "请出一道同类型变式题验证，她独立做对才算真掌握]"
                )
            elif _sig.signal == "method_conflict":
                understand_extra = (
                    "[系统提示：孩子提到的方法与当前讲解不同（方法冲突）。"
                    "请先接住并肯定她的方法，再引导对比两种方法的异同与等价性，"
                    "把新方法连回已有知识，绝不否定她的方法]"
                )
            elif _repeated and _sig.signal in ("cant_do", "text_confusion", "fake_understand", "metacognition_gap"):
                understand_extra = (
                    f"[系统提示：孩子反复表达「{_sig.detail}」。已确认过，本轮请收起程式化确认话术，"
                    "直接对症推进：把难点拆成更小的步子、换一种具体讲法，或给出一个她一定能做的小练习]"
                )

    system_prompt = persona.build_system_prompt(student)

    extras: list[str] = []
    # V3.0 K.2：认知卸载干预话术注入（恢复独立思考，绝不直接给答案）
    if offload_signals:
        from backend.services.offload_detector import INTERVENTION_PHRASES
        for _sig in offload_signals:
            _phrases = INTERVENTION_PHRASES.get(_sig.signal, [])
            _picked = _phrases[0] if _phrases else ""
            extras.append(
                f"[系统提示：检测到认知卸载信号（{_sig.signal}）。请立即用以下方式干预，恢复孩子的独立思考，绝不直接给答案：\n{_picked}]"
            )
    if external_extra:
        extras.append(external_extra)
    # V3.0 模块 L：理解信号对症指令（非短路路径：变式验证/方法冲突/重复表达）
    if understand_extra:
        extras.append(understand_extra)
    # V3.0 模块 L：UNDERSTAND_CONFIRM 确认流程遗留的待执行指令（如"换讲法""只讲第N步"）
    if sess.understand_pending_instruction:
        extras.append(sess.understand_pending_instruction)
        sess.understand_pending_instruction = ""
    # V3.0 模块 L.7：上一轮认知负荷高 → 本轮降低讲解粒度
    if not pure_mode and sess.last_cognitive_load == "high":
        from backend.agent.strategy_engine import reduce_pace_instruction

        extras.append(reduce_pace_instruction())

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
    # V3.0 P0: 轻量首学模式 → 正常模式
    if getattr(sess, 'lightweight_mode', False):
        if sess.turn_count >= 15:
            sess.lightweight_mode = False
            extras.append("[系统提示：轻量首学模式已满15轮，自然过渡到正常学习模式]")
        elif sess.started_at:
            started = datetime.fromisoformat(sess.started_at)
            elapsed = (datetime.now() - started).total_seconds() / 60
            if elapsed >= 10:
                sess.lightweight_mode = False
                extras.append("[系统提示：轻量首学模式已满10分钟，自然过渡到正常学习模式]")
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
        from backend.knowledge import syllabus as _syl_load
        node = _syl_load.get_node(sess.topic_id)
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

    # C1：教学策略引擎（确定性选择，LLM 按步骤执行）
    from backend.agent.strategy_engine import infer_problem_type, select_strategy, strategy_instruction
    from backend.knowledge import syllabus as _syl_strategy

    _topic_node = _syl_strategy.get_node(sess.topic_id) if sess.topic_id else None
    _ptype = infer_problem_type(
        topic_name=_topic_node.name if _topic_node else "",
        user_message=user_message or "",
    )
    _self_doubt = bool(user_message and any(
        k in user_message for k in ["我太笨", "我学不会", "我不行", "我笨", "好难我不会"]
    ))
    _strategy = select_strategy(
        student,
        problem_type=_ptype,
        context={
            "consecutive_wrong": sess.consecutive_wrong,
            "consecutive_correct": sess.consecutive_correct,
            "mastery": student.mastery_score(sess.topic_id) if sess.topic_id else 0.5,
            "step_count": 4 if _ptype in ("word_problem", "multi_step") else 1,
            "self_doubt_expression": _self_doubt,
        },
    )
    if _strategy:
        extras.append(f"[教学策略指令]\n{strategy_instruction(_strategy)}")

    # K.4 时间信任承诺：新知识点首次教学注入价值说明
    if (
        not pure_mode
        and sess.topic_id
        and sess.state not in ("MODE_SELECT", "BLIND_SPOT")
        and student.mastery.get(sess.topic_id) is None
    ):
        from backend.agent.persona import value_statement_for

        extras.append(
            "[系统提示：本知识点首次教学，请先输出价值说明：\n"
            + value_statement_for(sess.topic_id)
            + "\n然后自然开始教学（若孩子表示不感兴趣，提供换方式或跳过选项）]"
        )

    # K.4 时间信任承诺：价值质疑 / 跳过追踪
    if not pure_mode and sess.topic_id and user_message:
        if any(k in user_message for k in ["为什么要学", "为啥要学", "为什么学这个"]):
            extras.append(
                "[系统提示：孩子询问本知识点价值。请先用一句话说明为什么值得学（从孩子关心的角度），若仍不接受，提供「换个方式」或「先跳过」选项，绝不强迫]"
            )
        elif any(
            k in user_message
            for k in ["跳过", "不想学这个", "换一个吧", "没意思", "不感兴趣", "学这个干嘛", "学这个有啥用", "有啥用"]
        ):
            skip_map = getattr(student, "skipped_topics", None) or {}
            student.skipped_topics = skip_map
            skip_map[sess.topic_id] = int(skip_map.get(sess.topic_id, 0)) + 1
            extras.append(
                "[系统提示：孩子想跳过本知识点。请：①若价值说明还没输出，先简短补一句；②仍不接受时，温柔提供「换个方式学」或「先跳过」，绝不强迫、不让她有愧疚感；③她选择跳过就自然接受，下次可换项目方式引入]"
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

    # V3.0 P0/I-11.9#4：挑战题面确认（规格 11.9.4——小圆真正发出题目后才接受表态）
    if not pure_mode:
        _challenge_present_confirm(student, reply_text)

    # 模拟逐字输出（打字机效果）
    for i in range(0, len(reply_text), 3):
        yield {"type": "text", "content": reply_text[i : i + 3]}
        await asyncio.sleep(0.01)

    # V3.0 P2/I-11.5：奇怪现象（学习中低概率插入数学小悬念，规格 11.5）
    if (
        not pure_mode
        and sess.state not in ("MODE_SELECT", "GREETING")
        and sess.turn_count >= 3
    ):
        _strange_count = int(student.v3_meta.get("strange_inserted", 0))
        if _strange_count < 2:
            import random as _random_sp
            if _random_sp.random() < 0.08:
                try:
                    from backend.agent.persona import pick_strange_phenomenon
                    _phenomenon = pick_strange_phenomenon()
                    if _phenomenon:
                        student.v3_meta["strange_inserted"] = _strange_count + 1
                        yield {"type": "text", "content": f"\n\n🧐 {_phenomenon}"}
                except ImportError:
                    pass

    # V3.0 P0/I-11.9#5: 顿悟时刻庆祝 SSE（纯学习模式下关闭，规格 11.9.2）
    if not pure_mode and insight and insight.confidence >= 0.7:
        card_payload = _drop_payload(insight_card_drop) if (
            insight_card_drop and insight_card_drop.get("success")
        ) else None
        badge_payload = None
        if insight_badges:
            _b = insight_badges[0]
            badge_payload = {
                "name": _b,
                "icon": (Badge.ALL.get(_b) or {}).get("icon", "🏅"),
                "desc": (Badge.ALL.get(_b) or {}).get("desc", ""),
            }
        yield {
            "type": "insight_event",
            "insight_type": insight.insight_type,
            "student_quote": insight.student_quote[:100],
            "xp_reward": 100,
            "card_dropped": card_payload,
            "badge_unlocked": badge_payload,
            "effect": "golden_burst",
        }

    new_badges: list[str] = []
    if eval_data:
        new_badges.extend(assessment.apply_eval(
            student,
            eval_data,
            suppress_combo=_is_minor_confirmation(user_message),
        ))
        state_now = student.current_session.state

        # V3.0 P1：推送游戏化奖励 SSE（combo_update / card_drop / pet_feed）
        p1 = assessment.pop_p1_rewards()
        if p1.get("combo"):
            yield {"type": "combo_update", "data": p1["combo"]}
        if p1.get("card_drop"):
            yield {
                "type": "card_drop",
                "data": {
                    **_drop_payload(p1["card_drop"]),
                    "combo": (p1.get("combo") or {}).get("current", 0),
                },
            }
        if p1.get("xp_events"):
            yield {
                "type": "pet_feed",
                "data": {
                    "events": p1["xp_events"],
                    "pet": _pet_payload(p1.get("pet")),
                },
            }

        # V3.0 P2 模块D：冒险自动通关 SSE（规格 6.3.3，掌握度达标自动判定）
        for adv in assessment.pop_adventure_completions():
            yield {"type": "level_complete", "data": adv}

        # V3.0 P0/I-11.9#4：挑战成功结算（规格 11.9.4——独立答对即大额奖励，
        # 3-5倍XP + 必掉稀有以上卡 + 挑战徽章 + 教学日志特别记录）
        _challenge_events = (
            _settle_challenge_success(
                student,
                independent_success=eval_data.get("independent_success") is True,
            )
            if not pure_mode else []
        )
        for ev in _challenge_events:
            yield ev

        # V3.0 模块 L.4.1：延迟验证结算（开场 30 秒热身作答后）
        # 孩子作答完毕、eval 给出独立成功判定 → 结算昨日声称掌握的验证任务。
        # H1 校验：仅当本轮 mastery_updates 含该知识点才结算（防止任意作答误结算）。
        if not pure_mode and sess.delayed_check_topic_id:
            _dc_topic = sess.delayed_check_topic_id
            _dc_ind = eval_data.get("independent_success")
            if _delayed_check_settles(eval_data, _dc_topic) and isinstance(_dc_ind, bool):
                from backend.services.mastery_tracker import record_delayed_check_result

                sess.delayed_check_topic_id = ""
                res = record_delayed_check_result(student, _dc_topic, success=_dc_ind)
                if not _dc_ind:
                    # 假性掌握：掌握度已回退，下轮换讲法重新讲解（L.4.1）
                    sess.understand_pending_instruction = (
                        f"[系统提示：昨日声称掌握的「{_dc_topic}」延迟验证未通过"
                        f"（掌握度已回退，假性掌握）。本轮请用与上次完全不同的讲法/比喻"
                        f"重新讲解，先肯定她尝试的勇气]"
                    )
                yield {
                    "type": "delayed_check_result",
                    "data": {
                        "topic_id": _dc_topic,
                        "success": bool(_dc_ind),
                        "prev_score": res.get("prev_score"),
                        "new_score": res.get("new_score"),
                        "rolled_back": res.get("rolled_back", False),
                    },
                }

        # V3.0 模块 L.7：记录本轮认知负荷（供下一轮讲解粒度控制）
        _cl = eval_data.get("cognitive_load")
        if isinstance(_cl, str) and _cl in ("low", "medium", "high"):
            sess.last_cognitive_load = _cl

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
        # 小圆动态表情：由学生情绪 + 会话事件派生（文本流之后到达）
        "avatar_emotion": _derive_avatar_emotion(eval_data, new_badges),
    }


def _drop_payload(dc: dict) -> dict:
    """卡片掉落事件 → SSE 载荷（剔除内部字段）。"""
    card = dict(dc.get("card") or {})
    return {
        "card": card,
        "is_new": dc.get("is_new", False),
        "duplicate_count": dc.get("duplicate_count", 0),
        "starlight_gained": dc.get("starlight_gained", 0),
        "starlight_total": dc.get("starlight_total", 0),
        "source": dc.get("source", ""),
    }


def _pet_payload(pet: dict | None) -> dict:
    """宠物对象 → SSE 载荷（实时计算心情）。"""
    if not pet:
        return {}
    from backend.services.pet import compute_mood
    mood, _ = compute_mood(pet)
    return {
        "species": pet.get("species", "egg"),
        "name": pet.get("name", "小蛋蛋"),
        "level": pet.get("level", 1),
        "exp": pet.get("exp", 0),
        "exp_to_next": pet.get("exp_to_next", 100),
        "mood": mood,
        "current_skin": pet.get("current_skin", "default"),
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
        entry_source=student.current_session.entry_source,
        ab_group=student.current_session.ab_group,
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

    # V3.0 P1：会话结束喂宠物（规格3.2：≥3轮 +20 XP）+ combo 归零保留最佳（规格5.3）
    turns = student.current_session.turn_count
    pet_feed_result = None
    from backend.services.pet import add_xp, ensure_pet
    if not get_pure_mode() and turns >= 3:
        student.pet = ensure_pet(student.pet)
        pet_feed_result = add_xp(student.pet, 20, source="session_complete")
        # 累计学习分钟数（粗估）
        student.pet["total_study_minutes"] = student.pet.get("total_study_minutes", 0) + (
            1 if turns < 5 else min(turns // 2, 30)
        )
    if student.combo:
        student.combo["current"] = 0  # 会话结束归零，历史最佳保留
        from datetime import datetime as _dt2
        iso_year, iso_week_n, _ = _dt2.now().isocalendar()
        student.combo["week_key"] = f"{iso_year}-W{iso_week_n:02d}"
    summary["pet_feed"] = {
        k: pet_feed_result[k] for k in ("xp_gained", "new_exp", "leveled_up", "new_level", "unlocked_skin")
    } if pet_feed_result else None
    summary["combo"] = {
        "current": student.combo.get("current", 0) if student.combo else 0,
        "best_all_time": student.combo.get("best_all_time", 0) if student.combo else 0,
        "best_this_week": student.combo.get("best_this_week", 0) if student.combo else 0,
    }

    # V3.0 P0: 每日思考题（会话结束时留一道，纯学习模式下关闭）
    if not get_pure_mode() and not student.insights.get("current_thinking_problem"):
        try:
            from backend.knowledge.challenge_problems import get_random_challenge
            tp = get_random_challenge(max_difficulty=2)
            if tp:
                student.insights["current_thinking_problem"] = {
                    "id": tp.id,
                    "question": tp.question,
                    "given_at": datetime.now().isoformat(timespec="seconds"),
                    "solved": False,
                }
                # 展示给前端：告别弹窗亮出今日思考题（验收 11.9#9）
                summary["thinking_problem"] = {
                    "id": tp.id,
                    "question": tp.question,
                }
        except ImportError:
            pass
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

    # V3.0 P2/I-11.5+I-11.7：结尾悬念 + 数学趣闻可变奖励 + 小圆故事线推进（纯学习模式关闭）
    if not get_pure_mode():
        try:
            from backend.agent.persona import fun_fact_unlock, pick_closing_hook, story_reveal
            closing_hook = pick_closing_hook()
            if closing_hook:
                summary["closing_hook"] = closing_hook
            fact = fun_fact_unlock(student)
            if fact:
                summary["fun_fact"] = fact
            story = story_reveal(student)
            if story:
                summary["story_reveal"] = story
        except ImportError:
            pass

    # BKT 学生级学习速度偏移 s_u 重估（进度表 135，§2.2）：会话结束自然挂点，
    # 仅当累计干净观测 ≥10 才重估写回，否则保持默认 0.5（冷启动零风险）。
    if getattr(student, "bkt_obs_total", 0) >= 10:
        from backend.services import bkt

        student.bkt_learn_offset = bkt.estimate_learn_offset(student)

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
