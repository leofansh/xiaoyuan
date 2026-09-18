"""A/B 测试框架（设计方案 98）。

对比「兴趣引入开场（组 A）vs 传统开场（组 B）」在三个指标上的差异：
学习时长、完成率、主动打开率。

分组规则：基于 student_id 的稳定哈希取模 100 与配置比例比较，确定性分组，
同一学生在档案落地后固定分组，不随每次会话重新哈希（非随机游走）。
"""

import hashlib

from backend.config import get_ab_test_config
from backend.models.student import SessionSummary, Student


def _stable_bucket(student_id: str) -> int:
    """把 student_id 稳定散列到 [0, 99] 区间（md5 取模，跨进程/跨重启不变）。"""
    digest = hashlib.md5(student_id.encode("utf-8")).hexdigest()
    return int(digest, 16) % 100


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
    """
    cfg = get_ab_test_config()
    groups: dict[str, dict] = {}
    for group in ("A", "B"):
        members = [s for s in students if s.ab_test_group == group]
        sessions: list[SessionSummary] = []
        for s in members:
            sessions.extend(s.session_history)
        groups[group] = _group_report(sessions, len(members))
    return {
        "groups": groups,
        "enabled": cfg["enabled"],
        "variant_a_ratio": cfg["variant_a_ratio"],
    }
