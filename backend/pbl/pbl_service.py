"""V3.0 P2 模块 E/F：PBL 进度 / 通关 / 奖励 / 知识回溯。

纯业务逻辑，不引入数据库、不读写磁盘。所有进度写入学生档案的
``student.pbl_projects`` 字段（规格 7.2.1），奖励写入 pet/cards，掌握度
通过 ``mastery_tracker.update_mastery`` 以"应用级掌握"弱观测更新（+0.1）。
"""

from __future__ import annotations

from datetime import datetime

from backend.knowledge.cards import CARD_LIBRARY, drop_card, ensure_cards
from backend.pbl.projects import PBL_PROJECTS, get_project, level_def
from backend.services.mastery_tracker import update_mastery
from backend.services.pet import add_xp, ensure_pet

# ---------------------------------------------------------------------------
# 档案字段初始化
# ---------------------------------------------------------------------------


def default_pbl_projects() -> dict:
    """PBL 档案初始结构（规格 7.2.1）。"""
    return {"active_project_id": None, "projects": {}}


def ensure_pbl(raw: dict | None) -> dict:
    """确保 pbl_projects 结构完整。原地补齐并返回同一对象。"""
    if not isinstance(raw, dict) or not raw:
        return default_pbl_projects()
    raw.setdefault("active_project_id", None)
    raw.setdefault("projects", {})
    return raw


def _new_project_record(project_id: str) -> dict:
    """新建一份项目进度记录。"""
    return {
        "project_id": project_id,
        "status": "available",
        "current_level": 1,
        "unlocked_levels": [1],
        "completed_levels": [],
        "level_states": {},
        "total_time_spent": 0,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "completed_at": None,
    }


def _completed_level_ids(record: dict, total: int) -> list[int]:
    """返回已完成关卡的 id 列表。"""
    states = record.get("level_states", {})
    return [i for i in range(1, total + 1) if states.get(str(i), {}).get("completed")]


def _project_status(record: dict | None, total: int) -> str:
    """项目状态：无记录→available；全完成→completed；否则→in_progress。"""
    if record is None:
        return "available"
    if len(_completed_level_ids(record, total)) >= total:
        return "completed"
    return "in_progress"


def _match_score(project: dict, interests: list[str]) -> int:
    """兴趣匹配度：项目 interests 与学生 interests 的交集大小。"""
    return len(set(project.get("interests", [])) & set(interests or []))


# ---------------------------------------------------------------------------
# 项目列表 / 详情
# ---------------------------------------------------------------------------


def list_projects(student) -> dict:
    """项目列表 + 兴趣推荐排序（规格 7.3.1）。"""
    pbl = ensure_pbl(getattr(student, "pbl_projects", None))
    student.pbl_projects = pbl
    records = pbl.get("projects", {})

    projects: list[dict] = []
    for project in PBL_PROJECTS.values():
        pid = project["id"]
        total = len(project.get("levels", []))
        record = records.get(pid)
        completed = _completed_level_ids(record, total) if record else []
        percent = round(len(completed) / total * 100, 1) if total else 0.0
        projects.append({
            "id": pid,
            "name": project.get("name"),
            "icon": project.get("icon"),
            "description": project.get("description"),
            "category": project.get("category"),
            "difficulty": project.get("difficulty"),
            "status": _project_status(record, total),
            "progress": {
                "completed_levels": len(completed),
                "total_levels": total,
                "percent": percent,
            },
        })

    interests = getattr(student, "interests", None) or []
    recommended = sorted(
        (p["id"] for p in projects),
        key=lambda pid: _match_score(get_project(pid), interests),
        reverse=True,
    )
    return {"projects": projects, "recommended": recommended}


def get_project_detail(student, project_id: str) -> dict:
    """项目详情：完整定义 + 学生进度（规格 7.3.2）。"""
    project = get_project(project_id)
    if project is None:
        return {}
    pbl = ensure_pbl(getattr(student, "pbl_projects", None))
    student.pbl_projects = pbl
    records = pbl.get("projects", {})
    record = records.get(project_id)

    total = len(project.get("levels", []))
    completed = _completed_level_ids(record, total) if record else []
    level_states = dict(record.get("level_states", {})) if record else {}

    detail = dict(project)
    detail["progress"] = {
        "completed_levels": len(completed),
        "total_levels": total,
        "percent": round(len(completed) / total * 100, 1) if total else 0.0,
        "level_states": level_states,
    }
    # 关卡标注：前端 renderLevelRow 依赖 status（locked/available/completed）+ best_score
    annotated = []
    for idx, lv in enumerate(project.get("levels", []), start=1):
        state = level_states.get(str(idx), {})
        out = dict(lv)
        if state.get("completed"):
            out["status"] = "completed"
        elif _is_level_unlocked(record, idx):
            out["status"] = "available"
        else:
            out["status"] = "locked"
        out["best_score"] = state.get("best_score")
        annotated.append(out)
    detail["levels"] = annotated
    return detail


# ---------------------------------------------------------------------------
# 进入关卡
# ---------------------------------------------------------------------------


def _intro_for_level(level: dict) -> str:
    """关卡开场白：优先用定义里的 intro_message，否则按模板生成。"""
    if level.get("intro_message"):
        return level["intro_message"]
    return f"Lv.{level.get('id')} {level.get('name')}：{level.get('description')}"


def _is_level_unlocked(record: dict | None, level_id: int) -> bool:
    """Lv.1 总是可进入；其余关卡需前一关 completed。"""
    if level_id <= 1:
        return True
    if record is None:
        return False
    states = record.get("level_states", {})
    return bool(states.get(str(level_id - 1), {}).get("completed"))


def enter_level(student, project_id: str, level_id: int) -> dict:
    """进入关卡（规格 7.3.3）。"""
    project = get_project(project_id)
    if project is None:
        return {"success": False, "can_enter": False, "reason": "项目不存在"}
    level = level_def(project_id, level_id)
    if level is None:
        return {"success": False, "can_enter": False, "reason": "关卡不存在"}

    pbl = ensure_pbl(getattr(student, "pbl_projects", None))
    student.pbl_projects = pbl
    record = pbl.get("projects", {}).get(project_id)

    if not _is_level_unlocked(record, level_id):
        return {
            "success": False,
            "can_enter": False,
            "reason": f"需先通关 Lv.{level_id - 1} 才能进入本关",
        }

    pbl["active_project_id"] = project_id
    return {
        "success": True,
        "can_enter": True,
        "level": level,
        "simulator_config": level.get("simulator_config", {}),
        "intro_message": _intro_for_level(level),
    }


# ---------------------------------------------------------------------------
# 通关奖励 / 知识回溯
# ---------------------------------------------------------------------------


def _stars(hit: bool, attempts: int) -> int:
    """星级规则（规格 8.4 简化）：1 次命中→3星；≤3 次→2星；其余命中→1星。"""
    if not hit:
        return 0
    if attempts <= 1:
        return 3
    if attempts <= 3:
        return 2
    return 1


def _grant_card(cards: dict, card_id: str) -> dict | None:
    """直接发放指定卡片到 collected，返回 {card, is_new}。"""
    if not card_id or card_id not in CARD_LIBRARY:
        return None
    cards = ensure_cards(cards)
    card = CARD_LIBRARY[card_id]
    collected = cards["collected"]
    is_new = card_id not in collected
    if is_new:
        collected[card_id] = {
            "count": 1,
            "first_obtained": datetime.now().isoformat(timespec="seconds"),
            "obtained_from": "pbl",
        }
        cards["unique_cards"] += 1
    else:
        collected[card_id]["count"] += 1
    cards["total_cards"] += 1
    return {"card": card, "is_new": is_new}


def _apply_knowledge(student, level: dict) -> None:
    """知识回溯：PBL 成功操作视为"应用级掌握"，llm_score 观测 +0.1。"""
    for kp in level.get("level_knowledge", []):
        kid = kp.get("id")
        if not kid:
            continue
        record = student.mastery.get(kid)
        current = record.score if record else 0.0
        llm_score = min(1.0, current + 0.1)
        student.mastery[kid] = update_mastery(record, None, llm_score)


def _knowledge_summary(level: dict) -> str:
    """生成知识回溯摘要。"""
    names = [kp.get("name", kp.get("id")) for kp in level.get("level_knowledge", [])]
    if not names:
        return "你刚才通过自己的操作完成了挑战！"
    return "你刚才用到了：" + "、".join(names)


def complete_level(student, project_id: str, level_id: int,
                   score: float, hit: bool, attempts: int) -> dict:
    """完成关卡：判定命中、更新进度、结算奖励、知识回溯（规格 7.3.4）。"""
    project = get_project(project_id)
    if project is None:
        return {"success": False, "completed": False, "message": "项目不存在"}
    level = level_def(project_id, level_id)
    if level is None:
        return {"success": False, "completed": False, "message": "关卡不存在"}

    pbl = ensure_pbl(getattr(student, "pbl_projects", None))
    student.pbl_projects = pbl
    projects = pbl.setdefault("projects", {})
    record = projects.setdefault(project_id, _new_project_record(project_id))
    level_states = record.setdefault("level_states", {})
    key = str(level_id)
    existing = level_states.get(key)
    already_completed = bool(existing and existing.get("completed"))

    total = len(project.get("levels", []))
    base = {
        "success": True,
        "completed": True,
        "next_level_unlocked": False,
        "project_completed": False,
    }

    if not hit:
        return {
            "success": True,
            "completed": False,
            "stars_earned": 0,
            "rewards": None,
            "message": "差一点！再试试调整力度和角度，导弹离靶子就差一点点啦！",
        }

    stars = _stars(True, attempts)

    # 已通关：不重复奖励，仅可能提升 best_score，保持原星级
    if already_completed:
        if score > existing.get("best_score", 0):
            existing["best_score"] = score
        completed = _completed_level_ids(record, total)
        next_unlocked = level_id < total
        project_completed = len(completed) >= total
        return {
            **base,
            "stars_earned": existing.get("stars", stars),
            "rewards": None,
            "next_level_unlocked": next_unlocked,
            "project_completed": project_completed,
            "knowledge_summary": _knowledge_summary(level),
            "message": f"恭喜通过 Lv.{level_id}！",
        }

    # 首次通关：写入进度
    level_states[key] = {
        "completed": True,
        "stars": stars,
        "best_score": score,
        "attempts": attempts,
    }
    completed = _completed_level_ids(record, total)
    record["completed_levels"] = completed
    record["status"] = "completed" if len(completed) >= total else "in_progress"
    record["current_level"] = min(total, max(completed) + 1) if completed else level_id
    record["unlocked_levels"] = [i for i in range(1, min(total, max(completed) + 2) + 1)] if completed else [1]
    if len(completed) >= total:
        record["completed_at"] = datetime.now().isoformat(timespec="seconds")

    next_unlocked = level_id < total
    project_completed = len(completed) >= total

    # 奖励：宠物 XP
    rewards_xp = level.get("rewards", {}).get("xp", 0)
    xp_result = add_xp(ensure_pet(getattr(student, "pet", None)), rewards_xp, source="pbl_level")
    student.pet = xp_result["pet"]

    # 奖励：卡片（库中直接发放，否则随机掉落一张）
    student.cards = ensure_cards(getattr(student, "cards", None))
    card_id = level.get("rewards", {}).get("card")
    card_dropped = _grant_card(student.cards, card_id)
    if card_dropped is None:
        drop_result = drop_card(student.cards, source="pbl")
        if drop_result.get("dropped"):
            card_dropped = {"card": drop_result["card"], "is_new": drop_result["is_new"]}

    # 知识回溯：更新掌握度
    _apply_knowledge(student, level)

    return {
        **base,
        "stars_earned": stars,
        "rewards": {"xp": rewards_xp, "card_dropped": card_dropped},
        "next_level_unlocked": next_unlocked,
        "project_completed": project_completed,
        "knowledge_summary": _knowledge_summary(level),
        "message": f"恭喜通过 Lv.{level_id}！",
    }


def project_knowledge(student, project_id: str, level_id: int) -> dict:
    """知识回溯接口（规格 8.6）：返回知识点列表 + 掌握度前后对比。"""
    level = level_def(project_id, level_id)
    if level is None:
        return {"level_id": level_id, "knowledge_points": [], "summary": ""}

    points: list[dict] = []
    for kp in level.get("level_knowledge", []):
        kid = kp.get("id")
        record = student.mastery.get(kid)
        current = record.score if record else 0.0
        after = min(1.0, current + 0.1)
        points.append({
            "id": kid,
            "name": kp.get("name", kid),
            "explanation": kp.get("explanation", ""),
            "mastery_current": round(current, 2),
            "mastery_after": round(after, 2),
        })

    names = [p["name"] for p in points]
    summary = "你刚才通过调整角度和力度打中了靶子，用到了：" + "、".join(names) + "。" if names else ""
    return {"level_id": level_id, "knowledge_points": points, "summary": summary}
