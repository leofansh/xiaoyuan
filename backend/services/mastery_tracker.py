"""贝叶斯掌握度追踪器（架构优化 B1）。

把"单一掌握度分数"升级为"观测样本 + 贝叶斯后验"：
- 每次答对/答错或 LLM 评估都是一个观测，累积到 attempts
- 后验掌握度 = 正确率 与 先验 的加权融合（比例收缩）
- 置信度反映数据充分性：观测越多置信度越高，能区分"真懂"与"刚蒙对"
- 遗忘衰减只作用于无新观测且置信度较高的知识点，置信度低的（数据少）不急于衰减
"""

from datetime import date

from backend.models.student import MasteryRecord


def _beta_factor(total: int) -> float:
    """比例收缩因子：随观测数收敛到 1（观测越多越信任实测正确率）。"""
    # 无观测时置信 0；约 10 次观测后收敛到 ~0.9
    return 1.0 - 1.0 / (total + 1.0)


def update_mastery(
    record: MasteryRecord | None,
    observed_correct: bool | None,
    llm_score: float | None,
    today: str | None = None,
    weight: float = 1.0,
) -> MasteryRecord:
    """用一次观测更新掌握度记录。返回（可能新建的）记录。

    - observed_correct: 学生是否答对（True/False）。None 表示无法判定（仅 LLM 评估）。
    - llm_score: LLM 粗估掌握度 0~1（无需独立作答信号时当作弱观测）。
    - weight: 观测权重系数（默认 1.0；被提示/卸载场景降权，如 0.3），向后兼容。
    """
    if record is None:
        record = MasteryRecord()
    today = today or date.today().isoformat()

    # 累积观测样本
    if observed_correct is True:
        record.attempts_total += 1
        record.attempts_correct += 1
    elif observed_correct is False:
        record.attempts_total += 1

    # 实测正确率（有样本时）
    if record.attempts_total > 0:
        empirical = record.attempts_correct / record.attempts_total
    else:
        empirical = None

    # 观测强度：独立作答信号权重 1.0，纯 LLM 评估弱观测权重 0.5
    signal_strength = 1.0 if observed_correct is not None else (0.5 if llm_score is not None else 0.0)

    if signal_strength > 0:
        # 贝叶斯融合：后验 = 先验*(1-w) + 观测*w
        prior = record.score
        observed_est = empirical if empirical is not None else llm_score
        if observed_est is not None:
            w = 0.4 * signal_strength * weight
            record.score = max(0.0, min(1.0, prior * (1 - w) + observed_est * w))

    # 置信度：随观测数增长，且独立作答样本权重更高
    if record.attempts_total > 0:
        record.confidence = min(1.0, _beta_factor(record.attempts_total))

    record.last_interaction = today
    return record


def apply_forgetting(
    record: MasteryRecord,
    days_since: int,
    memory_strength: float,
) -> MasteryRecord:
    """置信度感知的遗忘衰减（B1）。

    规则：
    - 低置信度（数据不足、可能本来就没学会）不衰减，保留待更多观测
    - 置信度足够时，按艾宾浩斯曲线 R = e^(-days_since / S) 衰减
    - 衰减后置信度同步降低（长期未复习说明记忆未巩固）
    """
    if record.confidence < 0.5 or days_since <= 1:
        return record
    import math
    retention = math.exp(-days_since / memory_strength)
    new_score = max(0.0, record.score * retention)
    new_conf = max(0.0, record.confidence * (0.9 ** days_since))
    record.score = round(new_score, 2)
    record.confidence = round(new_conf, 2)
    return record


# ============ V3.0 模块 L.4.1：延迟验证（Delayed Testing） ============
# 理论依据：即时自测会高估掌握（工作记忆仍"热着"），24~48 小时后再测才反映真实掌握度。
# 实现：验证题 = 复习题，复用间隔复习调度器（review_schedules），仅打 delayed_check 标记。


def schedule_delayed_check(
    student,
    topic_id: str,
    topic_name: str = "",
    claimed_at: str | None = None,
    days: int = 1,
) -> bool:
    """登记延迟验证任务（L.4.1 次日验证 / H1 掌握度 7 天验证，共用同一排期逻辑）。

    在 student.review_schedules 中创建/更新一条延迟验证计划：
    - next_review = today + timedelta(days=days)（缺省为次日开场 30 秒验证）
    - interval_days = days
    - delayed_check = True（标识验证题 = 复习题）

    Args:
        student: 学生档案
        topic_id: 通过费曼检查（或掌握达标）的知识点
        topic_name: 知识点名称（回退到 syllabus）
        claimed_at: 首次声称掌握时间（ISO；缺省为当前时间）
        days: 验证间隔天数（缺省 1，即次日延迟验证；H1 掌握验证用 7）

    Returns:
        是否成功登记。
    """
    from datetime import datetime, timedelta

    from backend.knowledge import syllabus

    node = syllabus.get_node(topic_id)
    if not node:
        return False
    name = topic_name or node.name
    claimed = claimed_at or datetime.now().isoformat(timespec="seconds")
    review_date = (datetime.now().date() + timedelta(days=days)).isoformat()

    existing = next(
        (rs for rs in student.review_schedules if rs.topic_id == topic_id),
        None,
    )
    if existing:
        # 已有计划：升级为延迟验证，覆盖为 days 天后的验证日（防重，不新建排期）
        existing.delayed_check = True
        existing.claimed_at = claimed
        existing.next_review = review_date
        existing.interval_days = days
        return True

    from backend.models.student import ReviewSchedule

    student.review_schedules.append(
        ReviewSchedule(
            topic_id=topic_id,
            topic_name=name,
            next_review=review_date,
            interval_days=days,
            review_count=0,
            last_reviewed="",
            mastery_at_schedule=student.mastery_score(topic_id, 0.0),
            delayed_check=True,
            claimed_at=claimed,
        )
    )
    return True


def schedule_verification(student, topic_id: str, topic_name: str = "") -> bool:
    """掌握达标登记 7 天验证（H1）。

    知识点掌握度从 <0.7 跨越到 >=0.7 时调用，复用 schedule_delayed_check 的排期
    与防重逻辑（days=7）：7 天后开场出一道检索练习题验证"真掌握"。
    已存在未结算的排期时由 schedule_delayed_check 内部防重（升级而非新建）。

    Args:
        student: 学生档案
        topic_id: 掌握达标的知识点
        topic_name: 知识点名称（回退到 syllabus）

    Returns:
        是否成功登记。
    """
    return schedule_delayed_check(student, topic_id, topic_name, days=7)


def get_due_delayed_checks(student):
    """取今天到期的延迟验证任务（L.4.1，会话开场调用）。

    延迟验证 = 标记了 delayed_check 且 next_review 到期的复习计划。
    完成后标记转为普通复习（record_delayed_check_result 内处理）。

    Returns:
        到期延迟验证任务列表（ReviewSchedule）。
    """
    from datetime import datetime

    today = datetime.now().date().isoformat()
    return [
        rs for rs in student.review_schedules
        if rs.delayed_check and rs.next_review and rs.next_review <= today
    ]


def get_due_verifications(student) -> list:
    """取今天到期的掌握验证任务（H1）。

    get_due_delayed_checks 的增强：同取全部 delayed_check 且到期的排期，
    覆盖 1 天延迟验证与 7 天掌握验证两类，并按 next_review 升序排序
    （同一天内先到期的优先出题）。

    Returns:
        到期验证任务列表（ReviewSchedule，按 next_review 排序）。
    """
    due = get_due_delayed_checks(student)
    return sorted(due, key=lambda rs: rs.next_review)


def record_delayed_check_result(student, topic_id: str, success: bool) -> dict:
    """延迟验证结果结算（L.4.1）。

    - 通过：掌握度确认更新（作为一次成功观测），转普通复习节奏（间隔翻倍）
    - 失败：掌握度回退 + 记录 false_mastery 事件 + 换讲法重新讲解

    Returns:
        结果描述 dict：{success, rolled_back, prev_score, new_score, false_mastery_event}
    """
    from datetime import datetime

    from backend.models.student import TeachingInsight

    rs = next(
        (r for r in student.review_schedules if r.topic_id == topic_id),
        None,
    )
    claimed_at = rs.claimed_at if rs else ""
    prev_score = student.mastery_score(topic_id, 0.0)
    today = datetime.now().isoformat(timespec="seconds")

    result: dict = {
        "success": success,
        "rolled_back": False,
        "prev_score": prev_score,
        "new_score": prev_score,
        "false_mastery_event": None,
    }

    if success:
        # 通过：作为一次独立成功观测更新掌握度（确认"真掌握"）
        rec = student.mastery.get(topic_id)
        from backend.models.student import MasteryRecord

        rec = update_mastery(
            rec or MasteryRecord(),
            observed_correct=True,
            llm_score=None,
            today=today[:10],
        )
        student.mastery[topic_id] = rec
        if rs:
            # 转普通复习：清标记 + 按复习成功推进（间隔翻倍）
            rs.delayed_check = False
            rs.claimed_at = ""
            from backend.services.repetition import record_review

            record_review(student, topic_id, True)
        result["new_score"] = rec.score
    else:
        # 失败：掌握度回退 + false_mastery 事件 + 换讲法引导
        rec = student.mastery.get(topic_id)
        if rec:
            rec.score = round(max(0.0, prev_score * 0.6), 2)
            rec.confidence = round(max(0.0, (rec.confidence or 0.0) * 0.7), 2)
            rec.attempts_total += 1
            rec.last_interaction = today[:10]
            result["rolled_back"] = True
            result["new_score"] = rec.score
        # BKT 延迟验证失败观测（进度表 135，§5/§4）：correct=False + 显式遗忘回退 logit −1.5
        from backend.services.bkt import _forget_logit, update_bkt

        update_bkt(student, topic_id, False)
        _forget_logit(student, topic_id)
        if rs:
            rs.delayed_check = False
            rs.claimed_at = ""

        event = {
            "date": today[:10],
            "topic_id": topic_id,
            "topic_name": rs.topic_name if rs else topic_id,
            "claimed_at": claimed_at,
            "verified_at": today,
            "result": "failed",
            "prev_score": prev_score,
            "new_score": result["new_score"],
            "action": "rollback + 换一种讲法重新讲解",
        }
        student.false_mastery_events.append(event)
        # 保持日志 ≤50 条
        if len(student.false_mastery_events) > 50:
            student.false_mastery_events = student.false_mastery_events[-50:]
        result["false_mastery_event"] = event

        # 教学日志特别记录（规格 L.9：false_mastery 事件类型）
        student.teaching_journal.append(TeachingInsight(
            date=today[:10],
            category="false_mastery",
            insight=(
                f"假性掌握：昨天声称掌握「{rs.topic_name if rs else topic_id}」，"
                f"次日延迟验证未通过，掌握度已回退（{prev_score:.2f}→{result['new_score']:.2f}）"
            ),
            what_worked="",
            what_failed="口头确认即更新掌握度，未经延迟验证校准",
            student_style="即时自测会高估掌握，需要间隔验证",
        ))
        if len(student.teaching_journal) > 50:
            student.teaching_journal = student.teaching_journal[-50:]

        # H1：验证失败补概念性遗忘 Gap（同知识点已有 open gap 则跳过，避免重复叠加）
        from backend.models.student import Gap

        _has_open_gap = any(
            g.topic_id == topic_id and g.status in ("open", "recurring")
            for g in student.gaps
        )
        if not _has_open_gap:
            student.gaps.append(Gap(
                topic_id=topic_id,
                topic_name=rs.topic_name if rs else topic_id,
                type="concept",
                category="concept_forgetting",
                root_cause="7天掌握验证失败：间隔后无法稳定提取，判定为概念性遗忘",
                repair_strategy="重讲概念要点 + 变式题复测，重置记忆表征",
                status="open",
                evidence="delayed_check_result=false",
                last_occurred=today[:10],
                occurrence_count=1,
            ))

    return result
