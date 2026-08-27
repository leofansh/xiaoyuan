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
) -> MasteryRecord:
    """用一次观测更新掌握度记录。返回（可能新建的）记录。

    - observed_correct: 学生是否答对（True/False）。None 表示无法判定（仅 LLM 评估）。
    - llm_score: LLM 粗估掌握度 0~1（无需独立作答信号时当作弱观测）。
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
            w = 0.4 * signal_strength
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
