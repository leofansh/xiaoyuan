"""评估与激励：解析AI评估块 → 更新学生数据 → 触发徽章。"""

import logging

from backend.knowledge import syllabus
from backend.models.student import Badge, ErrorReview, Gap, Student

logger = logging.getLogger(__name__)

VALID_STATES = {
    "GREETING", "MOOD_CHECKIN", "MODE_SELECT", "PLAN",
    "BLIND_SPOT", "CORE_DERIVE", "EXAMPLE_CHECK", "ERROR_REVIEW",
    "OPTIONAL_VARIANT", "QUICK_REVIEW", "FIX_ONE_ERROR", "WEEKEND_CLEAR",
    "WRAP_UP", "DONE", "THINKING_TRAINING",
    # D1：动态化新增状态
    "ANALOGY_EXPLANATION", "VISUALIZATION", "ERROR_ROOT_CAUSE", "BREAK_SUGGESTION",
    # V3.0 模块 L：双向有效交流确认态（费曼复述 / 台阶诊断，结束后恢复原状态）
    "UNDERSTAND_CONFIRM",
}

# V3.0 模块 L：可进入 UNDERSTAND_CONFIRM 的教学节点（与 chat.TEACHING_STATES 对齐）
_UNDERSTAND_CONFIRM_ENTRY_STATES = {
    "CORE_DERIVE", "EXAMPLE_CHECK", "OPTIONAL_VARIANT", "QUICK_REVIEW",
    "FIX_ONE_ERROR", "WEEKEND_CLEAR", "ANALOGY_EXPLANATION", "VISUALIZATION",
    "ERROR_REVIEW", "ERROR_ROOT_CAUSE", "BREAK_SUGGESTION", "THINKING_TRAINING",
}

VALID_TRANSITIONS = {
    "GREETING": {"MOOD_CHECKIN", "MODE_SELECT"},
    "MOOD_CHECKIN": {"MODE_SELECT"},
    "MODE_SELECT": {"BLIND_SPOT", "PLAN", "QUICK_REVIEW", "WEEKEND_CLEAR"},
    "PLAN": {"CORE_DERIVE", "PLAN"},
    "BLIND_SPOT": {"PLAN", "CORE_DERIVE", "BLIND_SPOT"},
    "CORE_DERIVE": {"EXAMPLE_CHECK", "CORE_DERIVE", "WRAP_UP",
                    "ANALOGY_EXPLANATION", "VISUALIZATION", "BREAK_SUGGESTION"},
    "EXAMPLE_CHECK": {"ERROR_REVIEW", "OPTIONAL_VARIANT", "EXAMPLE_CHECK", "CORE_DERIVE",
                      "BREAK_SUGGESTION"},
    "ERROR_REVIEW": {"OPTIONAL_VARIANT", "FIX_ONE_ERROR", "WRAP_UP", "ERROR_ROOT_CAUSE", "BREAK_SUGGESTION"},
    "OPTIONAL_VARIANT": {"WRAP_UP", "OPTIONAL_VARIANT", "BREAK_SUGGESTION"},
    "QUICK_REVIEW": {"FIX_ONE_ERROR", "WRAP_UP", "BREAK_SUGGESTION"},
    "FIX_ONE_ERROR": {"WRAP_UP", "FIX_ONE_ERROR", "BREAK_SUGGESTION"},
    "WEEKEND_CLEAR": {"WRAP_UP", "WEEKEND_CLEAR", "BREAK_SUGGESTION"},
    "WRAP_UP": {"DONE"},
    "DONE": set(),
    "THINKING_TRAINING": {"WRAP_UP", "THINKING_TRAINING"},
    # D1 动态状态：完成特殊讲解后回到主流程
    "ANALOGY_EXPLANATION": {"CORE_DERIVE", "EXAMPLE_CHECK", "BREAK_SUGGESTION"},
    "VISUALIZATION": {"CORE_DERIVE", "EXAMPLE_CHECK", "BREAK_SUGGESTION"},
    "ERROR_ROOT_CAUSE": {"FIX_ONE_ERROR", "CORE_DERIVE", "WRAP_UP", "BREAK_SUGGESTION"},
    "BREAK_SUGGESTION": {"CORE_DERIVE", "EXAMPLE_CHECK", "WRAP_UP", "BREAK_SUGGESTION"},
    # V3.0 模块 L：确认态（费曼复述 / 台阶诊断）完成后恢复原教学状态
    "UNDERSTAND_CONFIRM": _UNDERSTAND_CONFIRM_ENTRY_STATES,
}
# V3.0 模块 L：教学节点可进入确认态（chat 层短路进入，不依赖 LLM 建议）
for _entry in _UNDERSTAND_CONFIRM_ENTRY_STATES:
    VALID_TRANSITIONS.setdefault(_entry, set()).add("UNDERSTAND_CONFIRM")


def apply_eval(student: Student, eval_data: dict, *, suppress_combo: bool = False) -> list[str]:
    """把AI评估块应用到学生档案，返回新触发的徽章列表。

    V3.0 P1：内部同时处理 combo / 宠物XP / 卡片掉落（P1 游戏化三件套）。
    奖励事件写入模块级 _P1_REWARDS，由 chat 层通过 pop_p1_rewards() 取出推送 SSE。

    suppress_combo：对话小确认（"对""嗯"等）时置 True，跳过 combo+1/归零，
    但仍处理 newly_mastered 掉落与宠物 XP（规格 5.3/5.8，避免刷分）。
    """
    new_badges: list[str] = []

    # 1. 掌握度更新（贝叶斯增量更新，B1）
    from backend.services.mastery_tracker import update_mastery

    mastery_updates = eval_data.get("mastery_updates") or {}
    independent_success = eval_data.get("independent_success") is True
    newly_mastered: list[str] = []  # 掌握度从 <0.7 跨越到 >=0.7 的知识点
    for topic_id, score in mastery_updates.items():
        if not syllabus.get_node(topic_id) or not isinstance(score, (int, float)):
            continue

        old_rec = student.mastery.get(topic_id)
        old_score = old_rec.score if old_rec else 0.0
        # K.2：被提示（hinted）作答时降权，避免「靠提示过关」被计入真实掌握度
        weight = 0.3 if eval_data.get("hinted") is True else 1.0
        new_rec = update_mastery(
            old_rec,
            observed_correct=independent_success,
            llm_score=float(score),
            weight=weight,
        )
        student.mastery[topic_id] = new_rec
        if old_score < 0.7 <= new_rec.score:
            newly_mastered.append(topic_id)

    # 2. 新漏洞
    # 2. 新漏洞（B2：精细分类 + 根因 + 修复策略 + 复发追踪）
    from backend.knowledge.error_patterns import category_name, classify_gap, repair_strategy_for

    for gap in eval_data.get("gaps_found") or []:
        topic_id = gap.get("topic_id", "")
        if not topic_id:
            continue
        node = syllabus.get_node(topic_id)
        evidence = str(gap.get("evidence", ""))[:200]
        gap_type = "concept" if gap.get("type") != "careless" else "careless"
        category = classify_gap(topic_id, gap_type, evidence, gap.get("error_pattern", ""))
        now = student.today_iso()

        # 已有 open 漏洞：同一知识点复发 → 计数+1，升级为 recurring
        existing_open = [g for g in student.gaps if g.topic_id == topic_id and g.status == "open"]
        if existing_open:
            g = existing_open[0]
            g.occurrence_count += 1
            g.last_occurred = now
            if g.occurrence_count >= 2:
                g.status = "recurring"
            if not g.root_cause and category != "unknown":
                g.category = category
                g.root_cause = f"再次出现，判定为{category_name(category)}"
                g.repair_strategy = repair_strategy_for(category, evidence)
            continue

        student.gaps.append(
            Gap(
                topic_id=topic_id,
                topic_name=gap.get("topic_name") or (node.name if node else topic_id),
                type=gap_type,
                category=category,
                root_cause=gap.get("root_cause") or (f"初步判定为{category_name(category)}" if category != "unknown" else ""),
                repair_strategy=repair_strategy_for(category, evidence),
                evidence=evidence,
                status="open",
                first_detected=now,
                last_occurred=now,
                occurrence_count=1,
                found_at=now,
            )
        )

    # 3. 漏洞清零（含 recurring 复发漏洞）
    for topic_id in eval_data.get("gaps_cleared") or []:
        for g in student.gaps:
            if g.topic_id == topic_id and g.status in ("open", "recurring"):
                g.status = "cleared"
                g.cleared_at = student.today_iso()
                rec = student.mastery.get(topic_id)
                if rec is None or rec.score < 0.7:
                    from backend.models.student import MasteryRecord
                    student.mastery[topic_id] = MasteryRecord(
                        score=0.7,
                        confidence=max(rec.confidence, 0.5) if rec else 0.5,
                        attempts_correct=rec.attempts_correct if rec else 1,
                        attempts_total=rec.attempts_total if rec else 1,
                        last_interaction=student.today_iso(),
                    )

    # 4. 错题两问记录（ERROR_REVIEW 状态下完成两问）
    if eval_data.get("state") == "DONE" and eval_data.get("error_type"):
        pass  # 两问内容由 chat 层显式提交

    # 5. 自我效能感四来源加权 → 信心曲线（EP-P1-2）
    emotion = eval_data.get("emotion")
    if emotion:
        # 来源1：成功体验（最强）——独立做对的增量
        independent_success = eval_data.get("independent_success", False)
        success_delta = 0.12 if independent_success else 0.0

        # 来源2：替代经验——"你上次XX也搞定了"
        vicarious_delta = 0.03 if eval_data.get("vicarious_experience_used") else 0.0

        # 来源3：言语说服——具体表扬（非泛泛夸奖）
        persuasion_delta = 0.02 if eval_data.get("specific_praise") else 0.0

        # 来源4：生理/情绪状态
        emotion_delta = {
            "confident": 0.05, "neutral": 0.0,
            "frustrated": -0.08, "tired": -0.03
        }.get(emotion, 0.0)

        current = student.confidence_trend[-1]["score"] if student.confidence_trend else 0.5
        new_confidence = max(0.0, min(1.0, current + success_delta + vicarious_delta + persuasion_delta + emotion_delta))
        student.confidence_trend.append({"date": student.today_iso(), "score": round(new_confidence, 2)})
        if len(student.confidence_trend) > 90:
            student.confidence_trend = student.confidence_trend[-90:]

    # 5b. 元认知追踪
    meta_observed = eval_data.get("metacognition_observed", "none")
    strategy = eval_data.get("strategy_suggested", "")
    if meta_observed in ("plan", "monitor", "evaluate"):
        student.student_profile.metacognition_level = min(
            1.0, student.student_profile.metacognition_level + 0.05
        )
    if strategy:
        uses = student.student_profile.strategy_use
        uses[strategy] = uses.get(strategy, 0) + 1

    # 5c. 独立成功率追踪
    if independent_success:
        rate = student.student_profile.independent_success_rate
        student.student_profile.independent_success_rate = round(min(1.0, rate * 0.9 + 0.1), 2)

    # 5d. 焦虑模式追踪
    anxiety = eval_data.get("anxiety_level", "low")
    if anxiety == "high" and not student.student_profile.anxiety_pattern:
        student.student_profile.anxiety_pattern = "待观察"

    # 5f. 思维模型掌握度更新（EP-P1-6）
    _update_thinking_model_mastery(student, eval_data)

    # 5e. 认知画像动态更新（EP-P1-5）
    features = extract_conversation_features(
        student.current_session.history[-1]["content"] if student.current_session.history else "",
        eval_data,
        student.current_session.history,
    )
    update_cognitive_profile(student, eval_data, features)

    # 5g. B3：日常交互持续更新认知画像（贝叶斯加权，新证据优先）
    from backend.agent.cognitive_assessment import update_cognitive_from_interaction

    _interaction_evidence: dict = {"source": "daily"}
    if features.get("asked_why"):
        _interaction_evidence["abstract_thinking_evidence"] = 0.65
        _interaction_evidence["metacognition_evidence"] = 0.6
    if features.get("self_corrected") or features.get("stated_blind_spot"):
        _interaction_evidence["metacognition_evidence"] = 0.55
    if features.get("tried_alternative_method"):
        _interaction_evidence["flexibility_evidence"] = 0.7
    if features.get("frequent_step_questions"):
        _interaction_evidence["working_memory_evidence"] = 0.2
    if features.get("careless_errors_frequent"):
        _interaction_evidence["working_memory_evidence"] = 0.3
    if features.get("avoidance_behavior"):
        _interaction_evidence["math_anxiety_evidence"] = 0.75
    if features.get("主动挑战难题"):
        _interaction_evidence["math_anxiety_evidence"] = 0.15
    if len(_interaction_evidence) > 1:  # 至少有证据可更新
        update_cognitive_from_interaction(student, _interaction_evidence)

    # 6. 状态机推进（确定性规则 + LLM 建议 + 合法性校验，架构优化 A1）
    from backend.agent.state_engine import decide_next_state, update_consecutive_counts

    current_state = student.current_session.state

    # 6a. 更新连续正确/错误计数（用旧状态判定，不触发状态转移）
    update_consecutive_counts(student, eval_data, current_state)
    sess_counts = student.current_session

    # 6b. 进入当前状态后累计停留轮数
    sess_counts.turns_in_current_state += 1

    # 6c. 确定性引擎决定下一状态（LLM 建议只是候选）
    llm_state = eval_data.get("state")
    if llm_state not in VALID_STATES:
        llm_state = None  # 非法/缺失的状态建议忽略
    mastery_values = [v for v in (eval_data.get("mastery_updates") or {}).values() if isinstance(v, (int, float))]
    mastery_avg = sum(mastery_values) / len(mastery_values) if mastery_values else None

    # D1：传入认知画像与题型信息驱动动态化
    _cp = student.cognitive_profile
    _problem_type = ""
    if student.current_session.topic_id:
        from backend.agent.strategy_engine import infer_problem_type
        _n = syllabus.get_node(student.current_session.topic_id)
        _problem_type = infer_problem_type(
            topic_name=_n.name if _n else "",
            user_message=student.current_session.history[-1]["content"] if student.current_session.history else "",
        )

    transition = decide_next_state(
        current=current_state,
        llm_suggested_state=llm_state,
        consecutive_correct=sess_counts.consecutive_correct,
        consecutive_wrong=sess_counts.consecutive_wrong,
        turns_in_current_state=sess_counts.turns_in_current_state,
        mastery_avg=mastery_avg,
        abstract_thinking=_cp.abstract_thinking,
        learning_preference=_cp.learning_preference,
        problem_type=_problem_type,
    )

    # 6d. 应用最终状态；若变化则重置停留轮数/连续计数，并记录进入时间
    if transition.new_state != current_state:
        from datetime import datetime as _dt
        student.current_session.state = transition.new_state
        student.current_session.turns_in_current_state = 0
        student.current_session.state_entry_time = _dt.now().isoformat(timespec="seconds")
        # 状态推进后重置连续计数，避免跨状态累积
        student.current_session.consecutive_correct = 0
        student.current_session.consecutive_wrong = 0
        if transition.source != "keep":
            logger.info("状态 %s → %s（%s）: %s", current_state, transition.new_state, transition.source, transition.reason)

    # ============ V3.0 P1：游戏化奖励（combo / 宠物XP / 卡片） ============
    is_answer_eval = bool(mastery_updates) or bool(eval_data.get("gaps_found")) or bool(eval_data.get("gaps_cleared"))
    _P1_REWARDS.update(
        _apply_p1_rewards(
            student,
            independent_success=independent_success,
            newly_mastered=newly_mastered,
            is_answer_eval=is_answer_eval,
            suppress_combo=suppress_combo,
        )
    )

    # ============ V3.0 P1：身份认同更新（规格 11.4） ============
    from backend.services.identity import update_identity, talent_attribution_silent
    update_identity(student)

    # ============ V3.0 P2 模块D：冒险自动通关（规格 6.3.3，掌握度达标自动判定） ============
    _auto_complete_adventure_levels(student, newly_mastered)

    return new_badges


# 模块级：当前轮 P1 奖励快照（由 chat 层在每次 apply_eval 后 pop）
_P1_REWARDS: dict = {"combo": None, "card_drop": None, "xp_events": [], "pet": None}

_COMBO_MESSAGES = {
    "combo_3": "不错哦，继续保持！",
    "combo_5": "超棒！5连击了！",
    "combo_10": "哇！10连击！你是数学小天才！",
}

# 答错归零的温和鼓励话术（规格 5.3/5.8：答错不惩罚，只是归零并鼓励）
_COMBO_RESET_ENCOURAGEMENT: list[str] = [
    "没关系，连击断了，但勇气还在！",
    "答错是宝藏，我们把它变成经验值！",
    "别在意连击，重要的是我们弄懂了这题！",
    "连击清零啦，正好轻装上阵，下一题重新起飞！",
    "这次没连上没关系，你的努力我一直记着哦～",
    "错一次没什么大不了，敢尝试就已经很棒了！",
]


def pop_p1_rewards() -> dict:
    """取走上一轮 P1 奖励快照并清空（供 chat 层 SSE 推送）。"""
    global _P1_REWARDS
    rewards = _P1_REWARDS
    _P1_REWARDS = {"combo": None, "card_drop": None, "xp_events": [], "pet": None}
    return rewards


# 模块级：当前轮冒险自动通关事件（chat 层在每次 apply_eval 后 pop 推 SSE level_complete）
_ADVENTURE_COMPLETIONS: list[dict] = []


def pop_adventure_completions() -> list[dict]:
    """取走上一轮冒险自动通关事件并清空（供 chat 层 SSE 推送，规格 6.3.3）。"""
    global _ADVENTURE_COMPLETIONS
    events = _ADVENTURE_COMPLETIONS
    _ADVENTURE_COMPLETIONS = []
    return events


def _auto_complete_adventure_levels(student: Student, newly_mastered: list[str]) -> None:
    """掌握度达标 → 自动通关冒险关卡（规格 6.3.3："学习后由后端自动判断"）。

    对本次掌握度跨越 ≥0.7 的知识点，检查其对应冒险关卡；
    已解锁且尚未通关的关卡调用 try_complete_level 结算（发放奖励/传播解锁）。
    通关事件写入模块级 _ADVENTURE_COMPLETIONS，由 chat 层 pop 推送 SSE。
    """
    global _ADVENTURE_COMPLETIONS
    from backend.config import get_pure_mode
    if get_pure_mode() or not newly_mastered:
        return
    try:
        from backend.knowledge.adventure_levels import all_levels
        from backend.services.adventure_service import (
            ensure_adventure,
            is_level_unlocked,
            try_complete_level,
        )
    except ImportError:
        return

    adventure = ensure_adventure(student.adventure_map)
    student.adventure_map = adventure
    completed_set = set(adventure.get("completed_levels", []) or [])
    mastered_set = set(newly_mastered)

    for level in all_levels():
        if level.get("knowledge_node") not in mastered_set:
            continue
        if level["id"] in completed_set:
            continue
        if not is_level_unlocked(level, adventure):
            continue
        try:
            result = try_complete_level(student, level["id"])
        except Exception as e:  # noqa: BLE001
            logger.warning("冒险自动通关 %s 失败: %s", level["id"], e)
            continue
        if result.get("completed") and result.get("rewards") is not None:
            _ADVENTURE_COMPLETIONS.append({
                "level_id": level["id"],
                "level_name": level.get("name", level["id"]),
                "stars_earned": result.get("stars_earned", 0),
                "rewards": result.get("rewards"),
                "newly_unlocked": result.get("newly_unlocked", []),
                "message": result.get("message", ""),
            })


def _apply_p1_rewards(student: Student, *, independent_success: bool,
                      newly_mastered: list[str], is_answer_eval: bool,
                      suppress_combo: bool = False) -> dict:
    """组合 模块C(combo) + 模块A(宠物XP) + 模块B(卡片) 的奖励逻辑。

    触发条件（规格 5.3）：仅"主动答题并被评估"计 combo；
    对话小确认（"对""嗯"）不计数，避免刷分。
    """
    import random as _random

    from backend.config import get_pure_mode, get_variable_rewards
    from backend.knowledge.cards import drop_card, ensure_cards
    from backend.services.pet import add_xp, ensure_pet

    vr = get_variable_rewards()

    if get_pure_mode():
        return {"combo": None, "card_drop": None, "xp_events": [], "pet": None}

    rewards: dict = {"combo": None, "card_drop": None, "xp_events": [], "pet": None}

    pet = student.pet or {}
    pet = ensure_pet(pet)
    combo = student.combo or {}

    # 本周最佳：ISO 周键跨周重置
    from datetime import datetime
    iso_year, iso_week_n, _ = datetime.now().isocalendar()
    week_key = f"{iso_year}-W{iso_week_n:02d}"
    if combo.get("week_key") != week_key:
        combo["best_this_week"] = 0
        combo["week_key"] = week_key
    combo.setdefault("current", 0)
    combo.setdefault("best_all_time", 0)
    combo.setdefault("total_combos_5", 0)
    combo.setdefault("total_combos_10", 0)

    # ---------- 答对（评估块确认）：combo+1 + XP + 概率掉卡 ----------
    # suppress_combo（小确认"对/嗯"）时跳过 combo+1/归零，但仍处理掌握度掉落与宠物 XP
    if not suppress_combo and independent_success:
        prev = combo["current"]
        combo["current"] = prev + 1
        current = combo["current"]
        combo["best_all_time"] = max(combo["best_all_time"], current)
        combo["best_this_week"] = max(combo["best_this_week"], current)

        milestone = None
        xp_bonus = 0
        if current == 3:
            milestone = "combo_3"
        elif current == 5:
            milestone = "combo_5"
            xp_bonus = 10
            combo["total_combos_5"] += 1
        elif current == 10:
            milestone = "combo_10"
            xp_bonus = 20
            combo["total_combos_10"] += 1

        rewards["combo"] = {
            "current": current,
            "previous": prev,
            "milestone": milestone,
            "xp_bonus": xp_bonus,
            "message": _COMBO_MESSAGES.get(milestone or "", ""),
        }

        # 答对 +5 XP + 里程碑加成
        rewards["xp_events"].append({"source": "correct_answer", "amount": 5, "message": ""})
        if milestone and xp_bonus:
            rewards["xp_events"].append({"source": f"combo_{current}", "amount": xp_bonus,
                                         "message": rewards["combo"]["message"]})

        # 规格 13.9.4：连击暴击（达到阈值且概率触发）
        crit = False
        crit_effect = None
        if current >= vr["combo_crit_threshold"] and _random.random() < vr["combo_crit_prob"]:
            crit = True
            if _random.random() < 0.5:
                # A) 本答 XP 按 combo_crit_xp_multiplier 放大（追加被加倍的部分）
                crit_effect = "xp"
                base_xp = 5 + xp_bonus
                crit_extra = int(round(base_xp * (vr["combo_crit_xp_multiplier"] - 1)))
                rewards["xp_events"].append({"source": "combo_crit", "amount": crit_extra, "message": "暴击！"})
            else:
                # B) 必掉稀有卡（保底稀有度由配置指定）
                crit_effect = "card"
                cards = ensure_cards(student.cards)
                dc = drop_card(cards, source="combo_crit", force_rarity=vr["combo_crit_guarantee_rarity"])
                student.cards = cards
                if dc["dropped"] and rewards["card_drop"] is None:
                    rewards["card_drop"] = dc
        rewards["combo"]["crit"] = crit
        rewards["combo"]["crit_effect"] = crit_effect

        # 规格 13.9.4：宠物随机事件（真实学习成功后概率触发，每日上限）
        _today = datetime.now().date().isoformat()
        if student.v3_meta.get("pet_event_date") != _today:
            student.v3_meta["pet_event_date"] = _today
            student.v3_meta["pet_event_count"] = 0
        if (_random.random() < vr["pet_event_prob"]
                and student.v3_meta.get("pet_event_count", 0) < vr["pet_event_daily_max"]):
            student.v3_meta["pet_event_count"] = student.v3_meta.get("pet_event_count", 0) + 1
            if _random.random() < 0.5:
                xp = _random.randint(vr["pet_event_xp_range"][0], vr["pet_event_xp_range"][1])
                rewards["xp_events"].append({"source": "pet_random", "amount": xp, "message": "宠物送你一个礼物！"})
            else:
                cards = ensure_cards(student.cards)
                dc = drop_card(cards, source="pet_random")
                student.cards = cards
                if dc["dropped"] and rewards["card_drop"] is None:
                    rewards["card_drop"] = dc

        # 答对 10% 随机掉卡（规格 4.3.3）
        if _random.random() < 0.10:
            cards = ensure_cards(student.cards)
            dc = drop_card(cards, source="correct_answer")
            student.cards = cards
            if dc["dropped"] and rewards["card_drop"] is None:
                rewards["card_drop"] = dc

        # combo_10 额外 50% 掉卡（规格 5.3）
        if milestone == "combo_10" and _random.random() < 0.50:
            cards = ensure_cards(student.cards)
            dc = drop_card(cards, source="combo_10")
            student.cards = cards
            if dc["dropped"] and rewards["card_drop"] is None:
                rewards["card_drop"] = dc

    elif not suppress_combo and is_answer_eval:
        # ---------- 答错（明确答题被评估）：combo 归零，不惩罚 ----------
        if combo["current"] > 0:
            combo["current"] = 0
            rewards["combo"] = {
                "current": 0,
                "previous": combo["current"],
                "milestone": None,
                "xp_bonus": 0,
                "message": _random.choice(_COMBO_RESET_ENCOURAGEMENT),
            }

    # ---------- 新掌握知识点（≥0.7）：必掉卡 + 宠物+30XP（规格3.2/4.2） ----------
    if newly_mastered:
        cards = ensure_cards(student.cards)
        for tid in newly_mastered:
            dc = drop_card(cards, source="mastery", knowledge_node=tid, guaranteed=True)
            if dc["dropped"] and rewards["card_drop"] is None:
                rewards["card_drop"] = dc
            rewards["xp_events"].append({"source": "mastery_new", "amount": 30, "message": ""})
        student.cards = cards

    # ---------- 宠物 XP 统一入账（每次 add_xp 返回升级信息并入事件） ----------
    for ev in rewards["xp_events"]:
        res = add_xp(pet, ev["amount"], source=ev["source"])
        ev.update({k: res[k] for k in ("leveled_up", "new_level", "unlocked_skin", "new_exp")})
    student.pet = pet
    student.combo = combo
    rewards["pet"] = pet
    return rewards


def check_error_detective(student: Student, q1: str, q2: str, error_type: str, topic_id: str = "") -> bool:
    """完成两问协议→错题侦探徽章。返回是否新获得。"""
    student.error_reviews.append(
        ErrorReview(date=student.today_iso(), q1_answer=q1[:200], q2_answer=q2[:200],
                    error_type=error_type, topic_id=topic_id)
    )
    if Badge.ERROR_DETECTIVE not in student.badges and q1 and q2:
        student.badges.append(Badge.ERROR_DETECTIVE)
        return True
    return False


def check_derive_badge(student: Student, state: str, mastery_score: float | None) -> bool:
    """完成核心推导→推导小勇士徽章。"""
    if state == "CORE_DERIVE" and mastery_score is not None and mastery_score >= 0.6:
        if Badge.DERIVE_BRAVE not in student.badges:
            student.badges.append(Badge.DERIVE_BRAVE)
            return True
    return False


def check_transfer_badge(student: Student, state: str) -> bool:
    """独立解出变式题→举一反三徽章。"""
    if state in ("OPTIONAL_VARIANT",):
        last_mastery_gain = [
            rec.score for rec in student.mastery.values()
        ]
        if last_mastery_gain and Badge.TRANSFER not in student.badges:
            # 变式环节完成且掌握度整体不低时授予
            if max(last_mastery_gain) >= 0.7:
                student.badges.append(Badge.TRANSFER)
                return True
    return False


def check_insight_badges(student: Student, insight_type: str = "") -> list[str]:
    """顿悟徽章判定（规格 11.9.6，8 种）。

    输入：本次顿悟类型（insight_type，如 "delayed" 触发延迟顿悟徽章）。
    返回本次新获得的徽章列表（供 SSE badge_unlocked 展示）。
    """
    new_badges: list[str] = []
    ins = student.insights or {}
    total = int(ins.get("total_count", 0))

    # 累计次数里程碑（初次顿悟 1 / 思考者 10 / 顿悟达人 50 / 思想者 100）
    milestones = [
        (1, Badge.INSIGHT_FIRST),
        (10, Badge.INSIGHT_THINKER),
        (50, Badge.INSIGHT_MASTER),
        (100, Badge.INSIGHT_SAGE),
    ]
    for threshold, badge in milestones:
        if total >= threshold and badge not in student.badges:
            student.badges.append(badge)
            new_badges.append(badge)

    # 延迟顿悟：非学习时间主动说出"昨天那道题我想通了"
    if insight_type == "delayed" and Badge.INSIGHT_DELAYED not in student.badges:
        student.badges.append(Badge.INSIGHT_DELAYED)
        new_badges.append(Badge.INSIGHT_DELAYED)

    # 挑战题：完成第 1 道 / 第 10 道
    challenges = int(ins.get("challenge_completed", 0))
    if challenges >= 1 and Badge.INSIGHT_CHALLENGER not in student.badges:
        student.badges.append(Badge.INSIGHT_CHALLENGER)
        new_badges.append(Badge.INSIGHT_CHALLENGER)
    if challenges >= 10 and Badge.INSIGHT_GIANT_KILLER not in student.badges:
        student.badges.append(Badge.INSIGHT_GIANT_KILLER)
        new_badges.append(Badge.INSIGHT_GIANT_KILLER)

    # 每日思考题：想通 5 道
    solved = int(ins.get("thinking_problems_solved", 0))
    if solved >= 5 and Badge.INSIGHT_PROBLEM_MASTER not in student.badges:
        student.badges.append(Badge.INSIGHT_PROBLEM_MASTER)
        new_badges.append(Badge.INSIGHT_PROBLEM_MASTER)

    return new_badges


def record_blind_spot(student: Student, text: str) -> None:
    """记录学生自报盲区；首次自报→盲区猎手。只记录描述问题的消息。"""
    text = text.strip()[:100]
    if not text or text in student.current_session.blind_spots_today:
        return
    # 过滤掉明显不是盲区描述的消息（正向反馈、简单确认等）
    positive_patterns = ("懂了", "知道了", "明白了", "会了", "原来是这样", "好的", "嗯", "对的")
    clean = text.lstrip("我")  # 去掉开头的"我"
    if any(clean.startswith(s) for s in positive_patterns):
        return
    student.current_session.blind_spots_today.append(text)
    if Badge.BLIND_HUNTER not in student.badges:
        student.badges.append(Badge.BLIND_HUNTER)


def weekend_clear_check(student: Student) -> bool:
    """周末修复后无概念漏洞→清零大师。"""
    if student.current_session.mode != "weekend":
        return False
    if student.concept_gaps_open():
        return False
    if Badge.WEEKEND_CLEAR not in student.badges:
        student.badges.append(Badge.WEEKEND_CLEAR)
        return True
    return False


def apply_forgetting_decay(student: Student) -> None:
    """基于距离上次学习的时间，对掌握度进行置信度感知的艾宾浩斯衰减（B1）。"""
    from datetime import date

    from backend.services.mastery_tracker import apply_forgetting

    today = date.today()
    for topic_id, record in list(student.mastery.items()):
        if record.score <= 0.0:
            continue
        # 查找该知识点最后学习时间（从 session_history 中匹配）
        last_studied = _find_last_study_date(student, topic_id)
        if not last_studied:
            continue
        days_since = (today - last_studied).days
        if days_since <= 1:
            continue
        # 艾宾浩斯遗忘曲线：R = e^(-t/S)，S 为记忆强度
        memory_strength = record.score * 10 + 1
        student.mastery[topic_id] = apply_forgetting(record, days_since, memory_strength)


def _find_last_study_date(student: Student, topic_id: str) -> "date | None":
    """从会话历史中找到该知识点最后学习日期。"""
    from datetime import date as _date

    for rec in reversed(student.session_history):
        if rec.topic_id == topic_id:
            try:
                return _date.fromisoformat(rec.date)
            except (ValueError, TypeError):
                continue
    return None


def extract_conversation_features(
    user_message: str, eval_data: dict, history: list[dict]
) -> dict:
    """从对话中提取行为指标，用于更新认知画像（EP-P1-5）。"""
    features: dict = {}
    msg = user_message or ""

    # 学生是否要求画图
    features["requested_diagram"] = any(
        k in msg for k in ["画个图", "画图", "画一下", "图呢", "能不能画"]
    )
    # 学生是否问"为什么"
    features["asked_why"] = any(
        k in msg for k in ["为什么", "为啥", "怎么会", "凭什么"]
    )
    # 学生是否频繁问步骤（最近消息中）
    recent_user = [m["content"] for m in history[-6:] if m.get("role") == "user"]
    features["frequent_step_questions"] = sum(
        1 for m in recent_user
        if any(k in m for k in ["这一步", "怎么来的", "然后呢", "这步怎么"])
    ) >= 2
    # 粗心错误频繁
    features["careless_errors_frequent"] = (eval_data.get("error_type") == "careless")
    # 尝试换方法
    features["tried_alternative_method"] = any(
        k in msg for k in ["换一种", "另一种方法", "有没有别的", "其他办法"]
    )
    # 回避行为（不想做/跳过）
    features["avoidance_behavior"] = any(
        k in msg for k in ["不想做", "跳过", "换一道", "太难了不想"]
    )
    # 主动挑战
    features["主动挑战难题"] = any(
        k in msg for k in ["再来一道", "挑战", "难一点", "试试难的"]
    )
    # 自我纠正
    features["self_corrected"] = any(
        k in msg for k in ["不对，应该是", "我改一下", "等等，我重新想"]
    )
    # 主动说出卡点
    features["stated_blind_spot"] = eval_data.get("metacognition_observed") in ("monitor", "evaluate")

    return features


def update_cognitive_profile(student: Student, eval_data: dict, features: dict) -> None:
    """根据对话行为指标动态更新认知画像（EP-P1-5）。"""
    profile = student.cognitive_profile

    # 1. 抽象思维推断
    if features.get("requested_diagram"):
        profile.abstract_thinking = max(0.1, profile.abstract_thinking - 0.03)
        profile.learning_preference = "visual"
    if features.get("asked_why"):
        profile.abstract_thinking = min(1.0, profile.abstract_thinking + 0.02)
        profile.metacognition_level = min(1.0, profile.metacognition_level + 0.02)

    # 2. 工作记忆推断
    if features.get("frequent_step_questions"):
        if profile.working_memory_capacity != "low":
            profile.working_memory_capacity = "low"

    # 3. 执行功能推断
    ef = profile.executive_function
    if features.get("careless_errors_frequent"):
        ef["inhibition"] = max(0.1, ef["inhibition"] - 0.03)
    if features.get("tried_alternative_method"):
        ef["flexibility"] = min(1.0, ef["flexibility"] + 0.03)

    # 4. 数学焦虑推断
    if features.get("avoidance_behavior"):
        profile.math_anxiety = min(1.0, profile.math_anxiety + 0.04)
    if features.get("主动挑战难题"):
        profile.math_anxiety = max(0.0, profile.math_anxiety - 0.02)

    # 5. 元认知推断
    if features.get("self_corrected"):
        profile.metacognition_level = min(1.0, profile.metacognition_level + 0.03)
    if features.get("stated_blind_spot"):
        profile.metacognition_level = min(1.0, profile.metacognition_level + 0.02)

    # 6. 认知阶段推断（基于综合指标）
    avg = (profile.abstract_thinking + profile.metacognition_level) / 2
    if avg >= 0.7 and profile.cognitive_stage != "formal":
        profile.cognitive_stage = "formal"
    elif avg >= 0.45 and profile.cognitive_stage == "concrete":
        profile.cognitive_stage = "transitional"

    # 7. 分领域认知水平更新
    topic_id = student.current_session.topic_id
    if topic_id:
        node = syllabus.get_node(topic_id)
        if node:
            domain = node.domain
            old_domain = profile.domain_levels.get(domain, 0.5)
            verified = eval_data.get("independent_success", False)
            delta = 0.05 if verified else 0.02
            profile.domain_levels[domain] = round(min(1.0, old_domain + delta), 2)

    # 8. 置信度提升
    profile.assessment_confidence = min(1.0, profile.assessment_confidence + 0.02)
    from datetime import datetime
    profile.last_updated = datetime.now().isoformat(timespec="seconds")


def _update_thinking_model_mastery(student: Student, eval_data: dict) -> None:
    """更新思维模型掌握度（EP-P1-6）。"""
    mastery = student.thinking_model_mastery

    # 学生主动使用
    if eval_data.get("student_initiated_model"):
        mid = eval_data["student_initiated_model"]
        mastery[mid] = min(1.0, mastery.get(mid, 0.0) + 0.05)

    # 需要提示才使用
    if eval_data.get("prompted_model"):
        mid = eval_data["prompted_model"]
        mastery[mid] = min(1.0, mastery.get(mid, 0.0) + 0.02)

    # 错过了应该使用的模型
    if eval_data.get("missed_model"):
        mid = eval_data["missed_model"]
        mastery[mid] = max(0.0, mastery.get(mid, 0.0) - 0.03)

    # 本轮使用了某模型（无论成功失败，尝试即+0.01）
    if eval_data.get("used_thinking_model") and not eval_data.get("student_initiated_model") and not eval_data.get("prompted_model"):
        mid = eval_data["used_thinking_model"]
        mastery[mid] = min(1.0, mastery.get(mid, 0.0) + 0.01)

    # 思维模型徽章检查（掌握度达0.7触发）
    from backend.models.student import Badge
    _badge_map = {
        "reverse": Badge.THINKING_REVERSE,
        "visualization": Badge.THINKING_VISUAL,
        "decomposition": Badge.THINKING_DECOMPOSE,
        "analogy": Badge.THINKING_ANALOGY,
        "transformation": Badge.THINKING_TRANSFORM,
        "case_analysis": Badge.THINKING_CASE,
        "extreme": Badge.THINKING_EXTREME,
        "holistic": Badge.THINKING_HOLISTIC,
        "modeling": Badge.THINKING_MODELING,
        "verification": Badge.THINKING_VERIFY,
    }
    for mid, badge in _badge_map.items():
        if mastery.get(mid, 0.0) >= 0.7 and badge not in student.badges:
            student.badges.append(badge)
