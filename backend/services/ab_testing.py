"""A/B 测试框架（设计方案 98）。

对比「兴趣引入开场（组 A）vs 传统开场（组 B）」在三个指标上的差异：
学习时长、完成率、主动打开率。

分组规则：基于 student_id 的稳定哈希取模 100 与配置比例比较，确定性分组，
同一学生在档案落地后固定分组，不随每次会话重新哈希（非随机游走）。
"""

import hashlib
import math

from pydantic import BaseModel

from backend.config import get_ab_test_config
from backend.models.student import SessionSummary, Student


class ABTest(BaseModel):
    """通用化 A/B 实验定义：描述一个实验的两组配置与评估指标（文档 H2）。"""

    id: str                 # 实验唯一标识
    name: str               # 实验名称
    description: str        # 实验说明
    variant_a: dict         # A 组配置
    variant_b: dict         # B 组配置
    metrics: list[str]      # 评估指标列表
    start_date: str         # 开始日期（ISO）
    end_date: str = ""      # 结束日期（ISO，空串表示进行中）
    active: bool = True     # 是否启用


def _stable_bucket(student_id: str) -> int:
    """把 student_id 稳定散列到 [0, 99] 区间（md5 取模，跨进程/跨重启不变）。"""
    digest = hashlib.md5(student_id.encode("utf-8")).hexdigest()
    return int(digest, 16) % 100


def get_variant(student_id: str, test_id: str) -> str:
    """通用化确定性分组：同一学生同一实验始终落入同一组（"A"/"B"）。

    以 f"{student_id}_{test_id}" 为稳定哈希键，复用 _stable_bucket 的 md5 取模
    落桶到 [0, 99]，50/50 等分边界（< 50 → A，否则 → B）。无状态、无副作用。
    """
    key = f"{student_id}_{test_id}"
    return "A" if _stable_bucket(key) < 50 else "B"


def get_ab_test_group(student: Student) -> str:
    """返回学生所属实验组："A" / "B" / ""（未启用）。

    - ab_test 未启用 → 返回 ""，且不改动学生档案（行为与现状零变化）。
    - 已启用且学生已落定分组 → 直接返回，绝不重新哈希（分组固定）。
    - 已启用但学生尚未分组 → 惰性分配并写入 student.ab_test_group。
    """
    cfg = get_ab_test_config()
    if not cfg["enabled"]:
        return ""
    if student.ab_test_group in ("A", "B"):
        return student.ab_test_group
    threshold = int(cfg["variant_a_ratio"] * 100)
    group = "A" if _stable_bucket(student.id) < threshold else "B"
    student.ab_test_group = group
    return group


def _median(values: list[float]) -> float:
    """有序数值列表的中位数（列表为空返回 0.0）。"""
    n = len(values)
    if n == 0:
        return 0.0
    if n % 2 == 1:
        return values[n // 2]
    return (values[n // 2 - 1] + values[n // 2]) / 2


def _group_report(sessions: list[SessionSummary], sample_count: int) -> dict:
    """聚合单个实验组的三指标报告，全程无除零（空数据回退 0）。"""
    total = len(sessions)
    # 学习时长：只统计 duration_minutes > 0 的会话，避免被大量 0 分钟（放弃的会话）拉平
    durations = sorted(s.duration_minutes for s in sessions if s.duration_minutes > 0)
    # 完成率（代理定义）：turns >= 3 视为「完整完成一次学习」（少于 3 轮视为中途离开）
    completed = sum(1 for s in sessions if s.turns >= 3)
    # 主动打开率：entry_source == "主动打开" 的会话占比
    active_open = sum(1 for s in sessions if s.entry_source == "主动打开")
    return {
        "sample_count": sample_count,
        "total_sessions": total,
        "avg_duration_minutes": round(sum(durations) / len(durations), 2) if durations else 0.0,
        "median_duration_minutes": round(_median(durations), 2) if durations else 0.0,
        "completion_rate": round(completed / total, 4) if total else 0.0,
        "active_open_rate": round(active_open / total, 4) if total else 0.0,
    }


def compute_ab_report(students: list[Student]) -> dict:
    """全量学生聚合两组三指标报告。

    只统计 ab_test_group 非空（已落入 A/B 组）的学生，其余学生忽略。
    不暴露任何学生身份与记录明细，仅输出聚合统计量。
    附加完成率 A/B 比例差的双侧正态近似 z 检验 p 值（样本不足时为 null）。
    """
    cfg = get_ab_test_config()
    groups: dict[str, dict] = {}
    sessions_by_group: dict[str, list[SessionSummary]] = {}
    for group in ("A", "B"):
        members = [s for s in students if s.ab_test_group == group]
        sessions: list[SessionSummary] = []
        for s in members:
            sessions.extend(s.session_history)
        sessions_by_group[group] = sessions
        groups[group] = _group_report(sessions, len(members))
    return {
        "groups": groups,
        "enabled": cfg["enabled"],
        "variant_a_ratio": cfg["variant_a_ratio"],
        "completion_rate_p_value": _completion_rate_p_value(
            sessions_by_group["A"], sessions_by_group["B"]
        ),
    }


def _normal_cdf(x: float) -> float:
    """标准正态分布累计函数（基于 math.erf，纯 stdlib）。"""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _proportion_z_test(x1: int, n1: int, x2: int, n2: int) -> float | None:
    """两组比例差的正态近似 z 检验，返回双侧 p 值。

    任一组样本为 0、合并比例落到 0/1 边界（无方差）或标准误为 0 时返回 None。
    """
    if n1 <= 0 or n2 <= 0:
        return None
    p_pool = (x1 + x2) / (n1 + n2)
    if p_pool <= 0.0 or p_pool >= 1.0:
        return None
    se = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / n1 + 1.0 / n2))
    if se == 0.0:
        return None
    z = (x1 / n1 - x2 / n2) / se
    return 2.0 * (1.0 - _normal_cdf(abs(z)))


def _completion_rate_p_value(a_sessions: list[SessionSummary], b_sessions: list[SessionSummary]) -> float | None:
    """完成率（turns >= 3 视作完整完成）A/B 比例差的双侧 z 检验 p 值。"""
    ca = sum(1 for s in a_sessions if s.turns >= 3)
    na = len(a_sessions)
    cb = sum(1 for s in b_sessions if s.turns >= 3)
    nb = len(b_sessions)
    p_value = _proportion_z_test(ca, na, cb, nb)
    return round(p_value, 6) if p_value is not None else None
