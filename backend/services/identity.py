"""V3.0 P1 模块：身份认同系统（规格 11.4）。

- 等级成长线：新手→学徒→熟练→大师→传奇
- 身份标签：神射手 / 建筑大师 / 建模侦探 / 出题大师 等
- 天赋归因话术（persona.py 注入用）

基于 student.mastery / combo / creations / cognitive_profile 计算。
"""

from __future__ import annotations

import random
from datetime import datetime

# ---------------------------------------------------------------------------
# 等级成长线（规格 11.4）
# ---------------------------------------------------------------------------
LEVEL_LADDER = [
    {"id": "newbie", "title": "新手", "min_nodes": 0, "min_sessions": 0},
    {"id": "apprentice", "title": "学徒", "min_nodes": 3, "min_sessions": 5},
    {"id": "skilled", "title": "熟练", "min_nodes": 12, "min_sessions": 15},
    {"id": "master", "title": "大师", "min_nodes": 28, "min_sessions": 35},
    {"id": "legend", "title": "传奇", "min_nodes": 50, "min_sessions": 60},
]


def _count_mastered_nodes(student) -> int:
    """掌握度 >= 0.7 的节点数。"""
    from backend.knowledge import syllabus
    count = 0
    for tid, rec in (student.mastery or {}).items():
        if hasattr(rec, "score") and rec.score >= 0.7:
            count += 1
        elif isinstance(rec, dict) and rec.get("score", 0) >= 0.7:
            count += 1
    return count


def compute_level(student) -> dict:
    """根据掌握节点数和会话数计算当前等级。返回完整 identity dict。"""
    identity = student.identity or {}
    nodes = _count_mastered_nodes(student)
    sessions = getattr(student, "total_sessions", 0) or 0

    # 找到满足条件的最高等级
    current = LEVEL_LADDER[0]
    for tier in LEVEL_LADDER:
        if nodes >= tier["min_nodes"] and sessions >= tier["min_sessions"]:
            current = tier

    # 更新 unlocked_titles
    unlocked = identity.get("unlocked_titles", [])
    for tier in LEVEL_LADDER:
        if nodes >= tier["min_nodes"] and sessions >= tier["min_sessions"]:
            if tier["title"] not in unlocked:
                unlocked.append(tier["title"])

    identity["level"] = current["id"]
    identity["title"] = current["title"]
    identity["unlocked_titles"] = unlocked
    identity["current_title"] = current["title"]
    return identity


# ---------------------------------------------------------------------------
# 身份标签触发规则（规格 11.4 / L1500）
# ---------------------------------------------------------------------------
def _pbl_projects(student) -> dict:
    """取 student.pbl_projects.projects，容错缺失。"""
    pbl = getattr(student, "pbl_projects", None)
    if isinstance(pbl, dict):
        return pbl.get("projects", {}) or {}
    return {}


def _pbl_project(student, project_id) -> dict | None:
    """取某个 PBL 项目进度记录，无则 None。"""
    record = _pbl_projects(student).get(project_id)
    return record if isinstance(record, dict) else None


def _project_completed(record: dict) -> bool:
    """PBL 项目是否通关：status=completed 或全部 level_states 完成。"""
    if record.get("status") == "completed":
        return True
    states = record.get("level_states", {}) or {}
    if states and isinstance(states, dict):
        return all(
            isinstance(v, dict) and v.get("completed") for v in states.values()
        )
    return False


def _pbl_completed_level_count(student) -> int:
    """PBL 各项目已完成关卡总数。"""
    total = 0
    for record in _pbl_projects(student).values():
        if isinstance(record, dict):
            total += len(record.get("completed_levels", []) or [])
    return total


def _adventure_boss_cleared(student) -> int:
    adv = getattr(student, "adventure_map", None)
    if isinstance(adv, dict):
        return len(adv.get("boss_cleared", []) or [])
    return 0


def _adventure_completed_levels(student) -> int:
    adv = getattr(student, "adventure_map", None)
    if isinstance(adv, dict):
        return len(adv.get("completed_levels", []) or [])
    return 0


def _missile_completed(student) -> bool:
    """神射手：导弹发射弧线项目通关（缺项目记录时退化为 Boss 关通关）。"""
    missile = _pbl_project(student, "missile_trajectory")
    if missile is not None:
        return _project_completed(missile)
    return _adventure_boss_cleared(student) >= 1


def _builder_completed(student) -> bool:
    """建筑大师：建筑项目通关（暂无建筑项目，等价 PBL 完成关卡>=6 或冒险>=6关）。"""
    return _pbl_completed_level_count(student) >= 6 or _adventure_completed_levels(student) >= 6


def _modeling_detective(student) -> bool:
    """建模侦探：用方程解决 3 个真实问题（缺字段退化为 PBL 完成关卡>=3）。"""
    interest = getattr(student, "interest_driven", None)
    if isinstance(interest, dict) and "real_world_problems_solved" in interest:
        return (interest.get("real_world_problems_solved") or 0) >= 3
    return _pbl_completed_level_count(student) >= 3


def _problem_master(student) -> bool:
    """出题大师：出过 10 道题（creations 中 type=="problem" 数量>=10）。"""
    creations = getattr(student, "creations", None) or []
    count = 0
    for c in creations:
        if isinstance(c, dict) and c.get("type") == "problem":
            count += 1
    return count >= 10


BADGE_DEFINITIONS = {
    "神射手": {
        "description": "导弹发射弧线项目通关",
        "trigger": _missile_completed,
    },
    "建筑大师": {
        "description": "建筑项目通关（PBL完成关卡>=6 或冒险地图完成>=6关）",
        "trigger": _builder_completed,
    },
    "建模侦探": {
        "description": "用方程解决3个真实问题（或PBL完成关卡>=3）",
        "trigger": _modeling_detective,
    },
    "出题大师": {
        "description": "出过10道题",
        "trigger": _problem_master,
    },
    "思维达人": {
        "description": "有3个思维模型掌握度 >= 0.7",
        "trigger": lambda s: sum(
            1 for v in (s.thinking_model_mastery or {}).values()
            if isinstance(v, (int, float)) and v >= 0.7
        ) >= 3,
    },
}


def check_badges(student) -> list[str]:
    """检查所有标签触发条件，返回新触发的标签列表。"""
    identity = student.identity or {}
    existing = identity.get("badges", [])
    new_badges: list[str] = []

    for badge_name, rule in BADGE_DEFINITIONS.items():
        if badge_name not in existing:
            try:
                if rule["trigger"](student):
                    new_badges.append(badge_name)
            except Exception:
                pass

    if new_badges:
        identity["badges"] = existing + new_badges
        student.identity = identity
    return new_badges


# ---------------------------------------------------------------------------
# 天赋归因话术（规格 11.4：persona.py 注入用）
# ---------------------------------------------------------------------------
_TALENT_SPEECH_BY_FIELD = {
    "number_theory": [
        "你对数字特别敏感，有数学家的直觉",
        "你有数论天赋，数字在你手里像积木",
        "你是数字型选手，对数的理解力很强",
    ],
    "algebra": [
        "你有很强的代数思维，逻辑链条拉得很稳",
        "你像个小侦探，从变量里找线索",
        "你是建模型选手，擅长用符号解决问题",
    ],
    "geometry": [
        "你有空间想象力，形状在你脑子里是活的",
        "你的几何直觉很棒，图感一流",
        "你是图形型选手，看图就能抓到关键",
    ],
    "function": [
        "你对变化规律特别敏感，函数感很强",
        "你有变化思维的天赋，变量之间的关系一目了然",
        "你是函数型选手，擅长从变化中找规律",
    ],
}


def talent_attribution(student) -> str:
    """根据掌握最强的领域，返回一段天赋归因话术。无数据时返回空串。"""
    mastery = student.mastery or {}
    if not mastery:
        return ""

    from backend.knowledge import syllabus
    # 统计各领域掌握度加权和
    field_scores: dict[str, float] = {}
    for tid, rec in mastery.items():
        score = getattr(rec, "score", 0) if hasattr(rec, "score") else (rec.get("score", 0) if isinstance(rec, dict) else 0)
        if score <= 0:
            continue
        node = syllabus.get_node(tid)
        if not node:
            continue
        domain = getattr(node, "domain", "general") or "general"
        field_scores[domain] = field_scores.get(domain, 0) + score

    if not field_scores:
        return ""

    best_domain = max(field_scores, key=field_scores.get)
    # general 是默认，如果没有其它领域专长就返回空
    if best_domain == "general" and len(field_scores) > 1:
        # 找非 general 的最高分
        non_general = {k: v for k, v in field_scores.items() if k != "general"}
        if non_general:
            best_domain = max(non_general, key=non_general.get)

    if best_domain == "general":
        return ""

    options = _TALENT_SPEECH_BY_FIELD.get(best_domain, [])
    if not options:
        return ""
    return random.choice(options)


def talent_attribution_silent(student) -> dict:
    """返回结构化的天赋归因信息（供 persona prompt 注入）。"""
    text = talent_attribution(student)
    if not text:
        return {"has_talent": False, "speech": ""}
    return {"has_talent": True, "speech": text}


# ---------------------------------------------------------------------------
# identity 确保初始化
# ---------------------------------------------------------------------------
def ensure_identity(raw: dict | None) -> dict:
    """确保 identity 结构完整。"""
    if not isinstance(raw, dict) or not raw:
        return {
            "level": "newbie",
            "title": "新手",
            "badges": [],
            "unlocked_titles": ["新手"],
            "current_title": "新手",
        }
    return raw


def update_identity(student) -> dict:
    """一次调用完成：等级计算 + 标签检查 + 返回完整 identity。"""
    identity = ensure_identity(student.identity)
    student.identity = identity  # 先写回完整结构，后续计算在完整结构上展开
    identity = compute_level(student)
    check_badges(student)
    student.identity = identity
    return identity
