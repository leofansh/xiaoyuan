"""V3.0 P2 模块D：闯关冒险地图服务（规格 6.3）。

负责冒险地图的懒初始化、关卡解锁判定、通关结算、星级评定与奖励发放。
业务逻辑集中在 service 层，main.py 端点只做加载 / 加锁 / 保存壳（不引入 SQL）。

通关后发放奖励：XP（喂给宠物）、卡片（加入 collected）、徽章（追加 badges），
并做解锁传播与大陆推进。掌握度（mastery）的递增由外部调用方保证，
本模块只读取、不修改 mastery。
"""

from __future__ import annotations

from datetime import datetime

from backend.knowledge.adventure_levels import (
    ADVENTURE_LEVELS,
    CONTINENT_ORDER,
    all_levels,
    get_level,
)
from backend.knowledge.cards import CARD_LIBRARY, drop_card, ensure_cards
from backend.models.student import Student
from backend.services.pet import add_xp, ensure_pet

# ---------------------------------------------------------------------------
# 冒险地图状态（规格 6.2）
# ---------------------------------------------------------------------------
DEFAULT_ADVENTURE = {
    "current_continent": "小学回顾",
    "unlocked_levels": [],
    "completed_levels": [],
    "stars": {},
    "total_stars": 0,
    "boss_cleared": [],
}


def default_adventure_map() -> dict:
    """获取一份全新的默认冒险地图状态（每次调用返回独立副本）。"""
    return dict(DEFAULT_ADVENTURE, unlocked_levels=[], completed_levels=[], stars={}, boss_cleared=[])


def _initial_unlocked_level_ids() -> list[str]:
    """初始解锁关卡：无前置依赖的 normal 关卡。"""
    return [
        lv["id"]
        for lv in all_levels()
        if lv["type"] == "normal" and not lv["unlock_condition"]["prerequisite_levels"]
    ]


def ensure_adventure(raw: dict | None) -> dict:
    """确保 adventure_map 结构完整（懒初始化，与 pet.ensure_pet 同风格）。

    空 / 非 dict 时返回全新默认地图（含初始解锁关卡）；
    否则原地补齐缺失字段并返回同一对象，保证内部修改同步到调用方引用。
    """
    if not isinstance(raw, dict) or not raw:
        adv = default_adventure_map()
        adv["unlocked_levels"] = _initial_unlocked_level_ids()
        return adv
    for k, v in DEFAULT_ADVENTURE.items():
        if raw.get(k) is None:
            raw[k] = [] if isinstance(v, list) else ({} if isinstance(v, dict) else v)
    if not raw.get("unlocked_levels") and not raw.get("completed_levels"):
        raw["unlocked_levels"] = _initial_unlocked_level_ids()
    return raw


# ---------------------------------------------------------------------------
# 星级与解锁判定
# ---------------------------------------------------------------------------
def _mastery_score(mastery) -> float:
    """从 MasteryRecord / dict / float 中提取掌握度分数。"""
    if mastery is None:
        return 0.0
    if isinstance(mastery, dict):
        return float(mastery.get("score", 0.0))
    if hasattr(mastery, "score"):
        return float(mastery.score)
    return float(mastery)


def compute_level_stars(level: dict, mastery, correct_answers: int, flawless: bool) -> int:
    """星级评定（规格 6.2）。

    1 星：掌握度 ≥ 0.7
    2 星：掌握度 ≥ 0.85 且答对 ≥ 2 题
    3 星：掌握度 ≥ 0.95 且一次通过（无答错）
    """
    score = _mastery_score(mastery)
    if score >= 0.95 and flawless:
        return 3
    if score >= 0.85 and correct_answers >= 2:
        return 2
    if score >= 0.7:
        return 1
    return 0


def is_level_unlocked(level: dict, adventure: dict) -> bool:
    """关卡是否已解锁：前置关卡全部 completed 且累计星星 ≥ prerequisite_stars。"""
    completed = set((adventure or {}).get("completed_levels", []))
    for pre in level["unlock_condition"].get("prerequisite_levels", []):
        if pre not in completed:
            return False
    total_stars = (adventure or {}).get("total_stars", 0)
    if total_stars < level["unlock_condition"].get("prerequisite_stars", 0):
        return False
    return True


# ---------------------------------------------------------------------------
# 通关结算
# ---------------------------------------------------------------------------
def _grant_rewards(student: Student, level: dict) -> dict:
    """发放奖励：XP（喂宠物）、卡片（入 collected）、徽章（追加 badges）。"""
    rw = level["rewards"]

    # XP → 宠物
    xp = int(rw.get("xp", 0))
    student.pet = ensure_pet(student.pet)
    add_xp(student.pet, xp, source="adventure")

    # 卡片（rewards.card 指定卡，若在卡片库中则放入 collected，标 is_new）
    card_dropped = None
    card_id = rw.get("card")
    if card_id and card_id in CARD_LIBRARY:
        student.cards = ensure_cards(student.cards)
        res = drop_card(student.cards, source="adventure", knowledge_node=level["knowledge_node"], guaranteed=True)
        if res.get("dropped") and res.get("card"):
            card_dropped = dict(res["card"])
            card_dropped["is_new"] = res.get("is_new", False)

    # 徽章
    badge_unlocked = None
    badge_id = rw.get("badge")
    if badge_id and badge_id not in student.badges:
        student.badges.append(badge_id)
        badge_unlocked = badge_id

    return {
        "xp": xp,
        "card_dropped": card_dropped,
        "badge_unlocked": badge_unlocked,
    }


def _propagate_unlocks(adventure: dict) -> list[str]:
    """通关后遍历全部关卡，把新解锁的关卡 id 加入 unlocked_levels，返回新增列表。"""
    completed = set(adventure.get("completed_levels", []))
    unlocked = set(adventure.get("unlocked_levels", []))
    newly: list[str] = []
    for lv in all_levels():
        if lv["id"] in completed:
            continue
        if is_level_unlocked(lv, adventure) and lv["id"] not in unlocked:
            unlocked.add(lv["id"])
            newly.append(lv["id"])
    adventure["unlocked_levels"] = list(unlocked)
    return newly


def _continent_bosses_cleared(adventure: dict, continent: str) -> bool:
    """某大陆的全部 boss 关是否已通关（boss_cleared 含全部该大陆 boss）。"""
    bosses = [l for l in ADVENTURE_LEVELS.values() if l["continent"] == continent and l["type"] == "boss"]
    if not bosses:
        return True
    cleared = set(adventure.get("boss_cleared", []))
    return all(b["id"] in cleared for b in bosses)


def _advance_continent(adventure: dict) -> None:
    """当前大陆 boss 全部通关时，推进 current_continent 到下一个大陆。"""
    current = adventure.get("current_continent", "小学回顾")
    idx = CONTINENT_ORDER.index(current) if current in CONTINENT_ORDER else 0
    while idx < len(CONTINENT_ORDER) - 1 and _continent_bosses_cleared(adventure, CONTINENT_ORDER[idx]):
        idx += 1
        adventure["current_continent"] = CONTINENT_ORDER[idx]


def try_complete_level(student: Student, level_id: str) -> dict:
    """尝试通关关卡（规格 6.3.3）。

    从 student.mastery 读取对应知识点掌握度判断是否达标，达标才通关；
    结算星级、发放奖励、传播解锁、推进大陆。不修改 mastery。

    返回结构：
      - 已通关（重复）: {"success": True, "completed": True, "rewards": None, ...}
      - 未达标:         {"success": False, "completed": False, "reason": "..."}
      - 通关成功:       {"success": True, "completed": True, "stars_earned",
                         "rewards": {"xp", "card_dropped", "badge_unlocked"},
                         "newly_unlocked": [...], "message": "..."}
    """
    level = get_level(level_id)
    if level is None:
        return {"success": False, "completed": False, "reason": f"关卡 {level_id} 不存在"}

    student.adventure_map = ensure_adventure(student.adventure_map)
    adventure = student.adventure_map

    # 已通关：不重复奖励
    if level_id in adventure.get("completed_levels", []):
        return {
            "success": True,
            "completed": True,
            "stars_earned": adventure.get("stars", {}).get(level_id, 0),
            "rewards": None,
            "newly_unlocked": [],
            "message": "已通关，不重复奖励",
        }

    # 掌握度达标判定
    node_id = level["knowledge_node"]
    rec = student.mastery.get(node_id)
    score = _mastery_score(rec)
    correct_answers = rec.attempts_correct if rec is not None else 0
    attempts_total = rec.attempts_total if rec is not None else 0

    threshold = level["completion_condition"]["mastery_threshold"]
    min_correct = level["completion_condition"]["min_correct_answers"]
    if score < threshold:
        return {
            "success": False,
            "completed": False,
            "reason": f"知识点掌握度 {score:.2f} 未达标（需 ≥ {threshold}）",
        }
    if correct_answers < min_correct:
        return {
            "success": False,
            "completed": False,
            "reason": f"答对 {correct_answers} 题未达标（需 ≥ {min_correct} 题）",
        }

    # 星级评定
    flawless = attempts_total > 0 and correct_answers == attempts_total
    stars = compute_level_stars(level, rec, correct_answers, flawless)

    # 记录通关
    if level_id not in adventure["completed_levels"]:
        adventure["completed_levels"].append(level_id)
    adventure["stars"][level_id] = max(adventure["stars"].get(level_id, 0), stars)
    adventure["total_stars"] = adventure.get("total_stars", 0) + stars
    if level["type"] == "boss" and level_id not in adventure["boss_cleared"]:
        adventure["boss_cleared"].append(level_id)

    # 发放奖励
    rewards = _grant_rewards(student, level)

    # 解锁传播 + 大陆推进
    newly_unlocked = _propagate_unlocks(adventure)
    _advance_continent(adventure)

    return {
        "success": True,
        "completed": True,
        "stars_earned": stars,
        "rewards": rewards,
        "newly_unlocked": newly_unlocked,
        "message": f"恭喜通关「{level['name']}」！获得 {stars} 颗星！",
    }
