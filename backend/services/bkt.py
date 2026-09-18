"""BKT（贝叶斯知识追踪）学生级参数估计（进度表 135）。

在现有 EMA 掌握度（mastery_tracker.py）之外，引入标准 4 参数 BKT
（Corbett & Anderson 1995）作为逐次作答的预测与掌握度参考口径，双轨并存：

- 预测：P(correct) = P(L)(1-S) + (1-P(L))G
- 更新：贝叶斯后验（logit 形式，数值稳定）
- 转移：P(L') = P(L|obs) + (1-P(L|obs))·T
- 学生级学习速度偏移 s_u（Yudelson 2013 logit 组合，1-D 网格搜索估计）
- 遗忘阻尼：FSRS 可提取性 R(Δt,S) 阻尼（ReviewSchedule.stability 作 S）

纯标准库实现，无 numpy/torch/pyBKT 依赖。
"""

import math
from datetime import date

from backend.knowledge import syllabus
from backend.models.student import MasteryRecord, Student

# 概率数值稳定夹取下/上界（§1.1，避免除零与无穷 logit）
_EPS = 1e-9

# 遗忘阻尼参数（§1.3/§4）：R = (1 + FACTOR·Δt/S)^DECAY
DECAY = -0.1542
FACTOR = 0.9 ** (1.0 / DECAY) - 1.0

# 学生级 s_u 网格候选（logit 空间，7 档，§2.2）
_OFFSET_CANDIDATES: tuple[float, ...] = (-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5)

# 达标滞回阈值（§1.2，防抖）
_MASTERED_ENTER = 0.90
_MASTERED_EXIT = 0.80

# 知识点级先验（§2.1，按节点类型 3 档 + 未知默认档）
PRIORS_BY_TYPE: dict[str, dict[str, float]] = {
    "concept": {"L0": 0.15, "T": 0.12, "G": 0.08, "S": 0.12},
    "calculation": {"L0": 0.25, "T": 0.15, "G": 0.10, "S": 0.08},
    "application": {"L0": 0.20, "T": 0.12, "G": 0.15, "S": 0.10},
    "default": {"L0": 0.20, "T": 0.12, "G": 0.10, "S": 0.10},
}


def _clamp(p: float) -> float:
    """把概率夹在 (ε, 1-ε)，保证 logit/sigmoid 数值稳定。"""
    return max(_EPS, min(1.0 - _EPS, p))


def _sigmoid(x: float) -> float:
    """数值稳定的 sigmoid（σ）。"""
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _logit(p: float) -> float:
    """logit 变换（先夹取防除零/无穷）。"""
    p = _clamp(p)
    return math.log(p / (1.0 - p))


def _node_type(topic_id: str) -> str:
    """从 syllabus 知识点元数据推断节点类型；未知→默认档（§2.1）。"""
    node = syllabus.get_node(topic_id)
    if node is not None:
        t = getattr(node, "type", "")
        if t in PRIORS_BY_TYPE:
            return t
    return "default"


def _prior_for(node_type: str) -> dict[str, float]:
    """按节点类型取先验表，未知类型回退默认档。"""
    return PRIORS_BY_TYPE.get(node_type, PRIORS_BY_TYPE["default"])


def _find_schedule(student: Student, topic_id: str):
    """查找该知识点的复习计划（ReviewSchedule），无则返回 None。"""
    for rs in student.review_schedules:
        if rs.topic_id == topic_id:
            return rs
    return None


def p_known(student: Student, topic_id: str) -> float:
    """只读：当前 BKT 掌握概率 P(L)；尚无 BKT 状态时返回冷启动先验 P(L0)。"""
    rec = student.mastery.get(topic_id)
    if rec is not None and getattr(rec, "p_known", 0.0) > 0.0:
        return rec.p_known
    return _prior_for(_node_type(topic_id))["L0"]


def is_mastered(student: Student, topic_id: str) -> bool:
    """达标判定（§1.2，带滞回锁存防抖）。

    - P(L) ≥ 0.90 → 进入达标（锁存 True）
    - P(L) < 0.80 → 退出达标（锁存 False）
    - 0.80 ≤ P(L) < 0.90 → 保持当前锁存（滞回区间，不抖动）
    """
    rec = student.mastery.get(topic_id)
    if rec is None:
        return False
    pk = p_known(student, topic_id)
    if pk >= _MASTERED_ENTER:
        rec.bkt_mastered = True
    elif pk < _MASTERED_EXIT:
        rec.bkt_mastered = False
    return bool(rec.bkt_mastered)


def _apply_forgetting_damping(student: Student, topic_id: str, pl: float,
                              rec: MasteryRecord, today: str) -> float:
    """隔天遗忘阻尼（§1.3/§4）：FSRS 可提取性 R(Δt,S) 衰减。

    Δt = last_bkt_update 距今整天数；Δt ≥ 1 且 ReviewSchedule.stability > 0 才衰减；
    同日（Δt=0）不遗忘；无 ReviewSchedule 或 stability≤0 跳过。
    """
    last = getattr(rec, "last_bkt_update", "")
    if not last:
        return pl
    try:
        delta = (date.fromisoformat(today) - date.fromisoformat(last)).days
    except ValueError:
        return pl
    if delta < 1:
        return pl
    rs = _find_schedule(student, topic_id)
    if rs is None or getattr(rs, "stability", 0.0) <= 0.0:
        return pl
    s = float(rs.stability)
    r = (1.0 + FACTOR * delta / s) ** DECAY
    return _clamp(pl * r)


def update_bkt(student: Student, topic_id: str, correct: bool, node_type: str = "") -> None:
    """用一次真实作答观测更新 BKT 状态（先取/初始化 → 遗忘阻尼 → 预测/更新/转移）。

    Args:
        student: 学生档案
        topic_id: 知识点 ID
        correct: 本次作答是否答对
        node_type: 知识点类型（concept/calculation/application）；空串时自动从 syllabus 查，
            查不到用默认先验档。
    """
    node_type = node_type or _node_type(topic_id)
    prior = _prior_for(node_type)

    rec = student.mastery.get(topic_id)
    if rec is None:
        rec = MasteryRecord()
        student.mastery[topic_id] = rec

    today = date.today().isoformat()

    # 1. 取 / 初始化 P(L0)（首次作答用先验冷启动；p_known=0 表示"尚无 BKT 状态"）
    if getattr(rec, "p_known", 0.0) > 0.0:
        pl = rec.p_known
        # 2. 遗忘阻尼 R(Δt,S)（隔天且稳定性>0 才衰减）
        pl = _apply_forgetting_damping(student, topic_id, pl, rec, today)
    else:
        pl = prior["L0"]

    # 3. 学生级 s_u 偏移合成 P(T)（§1.3：P(T) = σ(logit(T^k) + logit(s_u))）
    s_u = getattr(student, "bkt_learn_offset", 0.5)
    t_eff = _sigmoid(_logit(prior["T"]) + _logit(s_u))

    # 4. 预测 → 贝叶斯更新 → 转移（logit 等价形式，数值稳定）
    l = _logit(pl)
    if correct:
        l += math.log((1.0 - prior["S"]) / prior["G"])
    else:
        l += math.log(prior["S"] / (1.0 - prior["G"]))
    pl = _sigmoid(l)
    pl = _clamp(pl + (1.0 - pl) * t_eff)

    # 5. 落 MasteryRecord（BKT 状态 + 已消费作答数 + 更新时间）
    rec.p_known = pl
    rec.bkt_n = getattr(rec, "bkt_n", 0) + 1
    rec.last_bkt_update = today

    # 6. 学生级聚合计数（s_u 重估时机判断与对账用）
    student.bkt_obs_total += 1
    if correct:
        student.bkt_obs_correct += 1


def _forget_logit(student: Student, topic_id: str) -> None:
    """显式遗忘回退：P(L) ← σ(logit(P(L)) − 1.5)（延迟验证失败路径，§4）。"""
    rec = student.mastery.get(topic_id)
    if rec is None or getattr(rec, "p_known", 0.0) <= 0.0:
        return
    rec.p_known = _clamp(_sigmoid(_logit(rec.p_known) - 1.5))


def _sequence_brier(prior: dict[str, float], seq: list[bool], logit_offset: float) -> float:
    """对单条知识点作答序列做 BKT 前向递推，累计 Brier 损失。

    Args:
        prior: 知识点先验 {L0, T, G, S}
        seq: 该知识点按时间序的作答结果（True=答对）
        logit_offset: 学生级学习速度偏移（logit 空间）
    """
    t_eff = _sigmoid(_logit(prior["T"]) + logit_offset)
    pl = prior["L0"]
    loss = 0.0
    for correct in seq:
        pred = pl * (1.0 - prior["S"]) + (1.0 - pl) * prior["G"]
        actual = 1.0 if correct else 0.0
        loss += (pred - actual) ** 2
        if correct:
            l = _logit(pl) + math.log((1.0 - prior["S"]) / prior["G"])
        else:
            l = _logit(pl) + math.log(prior["S"] / (1.0 - prior["G"]))
        pl = _sigmoid(l)
        pl = _clamp(pl + (1.0 - pl) * t_eff)
    return loss


def _collect_observations(
    student: Student, topic_id: str | None
) -> list[tuple[dict[str, float], list[bool]]]:
    """池化学生全部可观测知识点作答序列（取自 review_logs，按时间排序）。

    rating ≥ 3（Good/Easy）视为答对；rating < 3（Again/Hard）视为答错。
    """
    groups: dict[str, list[tuple[str, bool]]] = {}
    for log in student.review_logs:
        if topic_id is not None and log.topic_id != topic_id:
            continue
        correct = log.rating >= 3
        groups.setdefault(log.topic_id, []).append((log.review_datetime, correct))

    observations: list[tuple[dict[str, float], list[bool]]] = []
    for tid, items in groups.items():
        items.sort(key=lambda item: item[0])
        observations.append((_prior_for(_node_type(tid)), [c for _, c in items]))
    return observations


def estimate_learn_offset(student: Student, topic_id: str | None = None) -> float:
    """1-D 网格搜索学生级学习速度偏移 s_u（§2.2，Yudelson 2013）。

    候选 logit 偏移 7 档；池化该生全部可观测知识点作答序列，最小化 Brier 损失
    Σ(P(correct_t) − 实际)^2。纯函数（只读 student），无观测时返回默认 0.5。

    Returns:
        s_u ∈ (0,1)（0.5 = 标准 BKT，冷启动零风险）。
    """
    observations = _collect_observations(student, topic_id)
    if not observations:
        return 0.5

    best_logit = 0.0
    best_loss = float("inf")
    for logit_offset in _OFFSET_CANDIDATES:
        loss = sum(_sequence_brier(prior, seq, logit_offset) for prior, seq in observations)
        if loss < best_loss:
            best_loss = loss
            best_logit = logit_offset
    return _sigmoid(best_logit)
