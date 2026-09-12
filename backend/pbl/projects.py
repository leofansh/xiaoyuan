"""V3.0 P2 模块 E/F：PBL 项目与关卡定义。

PBL_PROJECTS 存放每个"学习世界"的静态定义（项目元信息 + 关卡列表）。
旗舰项目「导弹发射弧线」按规格 7.2.2 + 8.2 定义 6 个关卡，从六年级平抛
逐步进阶到初三的移动靶预判；每关带 level_knowledge 用于通关后的知识回溯。
"""

from __future__ import annotations

from backend.knowledge.cards import CARD_LIBRARY

# 卡片校验兜底：不在库中时替换为一定存在的建模思维卡
_FALLBACK_CARD = "card_thinking_modeling"

PBL_PROJECTS: dict[str, dict] = {
    "missile_trajectory": {
        "id": "missile_trajectory",
        "name": "导弹发射弧线",
        "icon": "🚀",
        "description": "你是一名导弹工程师，需要调整发射角度和力度，打中远处的靶子。",
        "category": "物理/军事",
        "interests": ["游戏", "军事", "科学"],
        "difficulty": "beginner",
        "estimated_time": "2-4小时",
        "knowledge_coverage": ["函数", "三角函数", "向量", "物理运动"],
        "grade_range": "六年级~初三",
        "levels": [
            {
                "id": 1,
                "name": "平抛入门",
                "description": "水平扔石头，多久落地？落多远？",
                "math_knowledge": ["距离=速度×时间", "一次函数"],
                "simulator_type": "missile_level1",
                "simulator_config": {
                    "angle_range": [0, 0],
                    "power_range": [0, 100],
                    "target_distance": 100,
                    "wind": False,
                    "target_moving": False,
                },
                "completion_criteria": {"hit_target": True, "min_correct": 1},
                "rewards": {"xp": 30, "card": "card_elem_fangcheng"},
                "intro_message": (
                    "欢迎来到导弹基地！我是你的助手小圆。Lv.1 平抛入门：调整力度，"
                    "把导弹扔到对面的靶子上！试试拖一下力度滑块，然后点发射！"
                ),
                "level_knowledge": [
                    {
                        "id": "elem_fangcheng",
                        "name": "简易方程",
                        "explanation": (
                            "导弹飞行的距离 = 速度 × 时间，写成 d = v·t 就是一个最简单的方程："
                            "已知其中两个量，就能解出第三个。"
                        ),
                    },
                ],
            },
            {
                "id": 2,
                "name": "斜抛初探",
                "description": "45度角发射，飞多远？多高？",
                "math_knowledge": ["三角函数(sin/cos)", "抛物线方程"],
                "simulator_type": "missile_level2",
                "simulator_config": {
                    "angle_range": [0, 90],
                    "power_range": [0, 100],
                    "wind": False,
                    "target_moving": False,
                    "show_trajectory": True,
                },
                "completion_criteria": {"hit_target": True},
                "rewards": {"xp": 40, "card": "card_thinking_visual"},
                "level_knowledge": [
                    {
                        "id": "trig_basic",
                        "name": "三角函数基础",
                        "explanation": (
                            "初速度可以分解成水平(vx=v0·cosθ)和竖直(vy=v0·sinθ)两个方向，"
                            "sin 和 cos 就是把'斜着的速度'拆成'横竖两条腿'的工具。"
                        ),
                    },
                ],
            },
            {
                "id": 3,
                "name": "精准瞄准",
                "description": "目标在100米外，角度和力度怎么调？",
                "math_knowledge": ["方程求解", "参数调节"],
                "simulator_type": "missile_level3",
                "simulator_config": {
                    "angle_range": [0, 90],
                    "power_range": [0, 100],
                    "target_distance": 100,
                    "wind": False,
                    "help_button": True,
                },
                "completion_criteria": {"hit_target": True},
                "rewards": {"xp": 50, "card": "card_thinking_modeling"},
                "level_knowledge": [
                    {
                        "id": "elem_fangcheng",
                        "name": "简易方程",
                        "explanation": (
                            "目标在100米外，把'距离=速度×时间'列成方程，反推出需要多大的初速度。"
                        ),
                    },
                    {
                        "id": "equation_solving",
                        "name": "方程求解",
                        "explanation": (
                            "给定落地距离100米，反解出角度和力度，这就是解方程的过程——"
                            "把未知数一步步挪到等号一边。"
                        ),
                    },
                ],
            },
            {
                "id": 4,
                "name": "风的影响",
                "description": "有风（水平方向），怎么修正？",
                "math_knowledge": ["向量分解", "复合运动"],
                "simulator_type": "missile_level4",
                "simulator_config": {
                    "angle_range": [0, 90],
                    "power_range": [0, 100],
                    "wind": True,
                    "wind_range": [-20, 20],
                    "target_moving": False,
                },
                "completion_criteria": {"hit_target": True},
                "rewards": {"xp": 60, "card": "card_thinking_decomp"},
                "level_knowledge": [
                    {
                        "id": "vector_decomp",
                        "name": "向量分解",
                        "explanation": (
                            "风是水平方向的力，把它和导弹自己的速度合成就是向量的相加；"
                            "把合运动拆成水平和竖直两个分运动来分析。"
                        ),
                    },
                ],
            },
            {
                "id": 5,
                "name": "移动靶",
                "description": "目标匀速移动，怎么预判提前量？",
                "math_knowledge": ["相对运动", "方程组"],
                "simulator_type": "missile_level5",
                "simulator_config": {
                    "angle_range": [0, 90],
                    "power_range": [0, 100],
                    "target_moving": True,
                    "target_speed": 3,
                },
                "completion_criteria": {"hit_target": True},
                "rewards": {"xp": 80, "card": "card_thinking_transform"},
                "level_knowledge": [
                    {
                        "id": "relative_motion",
                        "name": "相对运动",
                        "explanation": (
                            "靶子在动、导弹也在动，要算'导弹相对靶子'的位置变化；"
                            "先假设自己站在靶子上看导弹，再列方程求提前量。"
                        ),
                    },
                ],
            },
            {
                "id": 6,
                "name": "总工程师",
                "description": "自己设计一个导弹打靶小游戏",
                "math_knowledge": ["综合", "编程思维"],
                "simulator_type": "missile_level6",
                "simulator_config": {"editor": True},
                "completion_criteria": {"hit_target": True},
                "rewards": {"xp": 120, "card": "card_thinking_modeling"},
                "level_knowledge": [
                    {
                        "id": "synthesis",
                        "name": "综合应用",
                        "explanation": (
                            "综合运用函数、三角函数、向量和方程，把现实问题翻译成数学，"
                            "再亲手设计一个游戏——这就是建模与编程思维。"
                        ),
                    },
                ],
            },
        ],
        "badge": "badge_missile_master",
        "locked": False,
        "prerequisite_project": None,
    },
}


def _validate_cards() -> None:
    """校验每个关卡的 rewards.card 是否在卡片库中，不在则替换为兜底卡。"""
    for project in PBL_PROJECTS.values():
        for level in project.get("levels", []):
            rewards = level.get("rewards")
            if not isinstance(rewards, dict):
                continue
            card = rewards.get("card")
            if card not in CARD_LIBRARY:
                rewards["card"] = _FALLBACK_CARD if _FALLBACK_CARD in CARD_LIBRARY else None


_validate_cards()


def get_project(project_id: str) -> dict | None:
    """按 id 获取项目定义。"""
    return PBL_PROJECTS.get(project_id)


def all_projects() -> list[dict]:
    """返回全部项目定义列表。"""
    return list(PBL_PROJECTS.values())


def level_def(project_id: str, level_id: int) -> dict | None:
    """获取某项目的某个关卡定义（level_id 为 int）。"""
    project = get_project(project_id)
    if project is None:
        return None
    for level in project.get("levels", []):
        if level.get("id") == level_id:
            return level
    return None
