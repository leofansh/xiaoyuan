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
        "choices": [
            {
                "id": "lv2_wind_choice",
                "at_level": 2,
                "prompt": "风要来了。你想先训练什么？",
                "options": [
                    {
                        "id": "wind_first",
                        "label": "先练顶风射击",
                        "hint": "顶风时导弹会被吹偏，射程变短",
                        "focus": "wind",
                    },
                    {
                        "id": "distance_first",
                        "label": "先练远距离瞄准",
                        "hint": "距离越远，角度误差被放大得越明显",
                        "focus": "distance",
                    },
                ],
            },
        ],
        "badge": "badge_missile_master",
        "locked": False,
        "prerequisite_project": None,
    },
    "minecraft_building": {
        "id": "minecraft_building",
        "name": "我的世界建筑",
        "icon": "🧱",
        "description": "你是一名方块建筑师，用一块块砖搭出城墙、房间、坐标小镇和立体仓库！",
        "category": "游戏/建筑",
        "interests": ["游戏", "建筑", "创造", "科学"],
        "difficulty": "beginner",
        "estimated_time": "2-4小时",
        "knowledge_coverage": ["几何", "坐标", "比例", "体积"],
        "grade_range": "三~六年级",
        "levels": [
            {
                "id": 1,
                "name": "城墙工程师",
                "description": "给小镇修一段城墙，每块砖长 1 格，铺到正好 12 格长。",
                "simulator_type": "building_level1",
                "simulator_config": {
                    "mode": "length",
                    "target_length": 12,
                    "grid_cols": 14,
                    "grid_rows": 4,
                },
                "completion_criteria": {"hit_target": True},
                "rewards": {"xp": 30, "card": "card_thinking_visual"},
                "level_knowledge": [
                    {
                        "id": "6a_xianduan",
                        "name": "线段的比较与和差倍",
                        "explanation": (
                            "铺城墙就是在数线段：从第一块砖到第十二块砖，正好 12 个单位长。"
                            "看一段线段有多长，就是数它包含几个单位长度。"
                        ),
                    },
                ],
            },
            {
                "id": 2,
                "name": "地砖设计师",
                "description": "房间长 6 米、宽 4 米，用 1m² 的地砖铺满，需要多少块？",
                "simulator_type": "building_level2",
                "simulator_config": {
                    "mode": "area",
                    "room_w": 6,
                    "room_h": 4,
                    "target_area": 24,
                    "grid_cols": 8,
                    "grid_rows": 6,
                },
                "completion_criteria": {"hit_target": True},
                "rewards": {"xp": 40, "card": "card_thinking_modeling"},
                "level_knowledge": [
                    {
                        "id": "elem_mianji",
                        "name": "面积公式",
                        "explanation": (
                            "地砖数 = 房间面积 = 长 × 宽。6×4=24，所以需要 24 块 1m² 的砖。"
                            "面积就是'一个面里能铺下多少个单位正方形'。"
                        ),
                    },
                ],
            },
            {
                "id": 3,
                "name": "坐标规划师",
                "description": "规划师用坐标指挥搭建：在 (3,2) 放红色方块、(-2,4) 放蓝色方块、(0,-3) 放绿色方块。",
                "simulator_type": "building_level3",
                "simulator_config": {
                    "mode": "coordinate",
                    "grid_cols": 11,
                    "grid_rows": 9,
                    "axis_range": [-5, 5],
                    "targets": [
                        {"color": "red", "x": 3, "y": 2},
                        {"color": "blue", "x": -2, "y": 4},
                        {"color": "green", "x": 0, "y": -3},
                    ],
                },
                "completion_criteria": {"hit_target": True},
                "rewards": {"xp": 50, "card": "card_thinking_reverse"},
                "level_knowledge": [
                    {
                        "id": "7b_pingmianzhijiao",
                        "name": "平面直角坐标系",
                        "explanation": (
                            "(3,2) 意思是先往右走 3 格，再往上走 2 格。坐标就是地图上的'经纬度'，"
                            "把'第几个'和'第几层'都说得清清楚楚。"
                        ),
                    },
                    {
                        "id": "6a_shuzhou",
                        "name": "数轴",
                        "explanation": (
                            "负数坐标往左/往下走：(-2,4) 就是先往左 2 格再往上 4 格。"
                            "数轴的方向感是坐标的基础。"
                        ),
                    },
                ],
            },
            {
                "id": 4,
                "name": "缩放建造师",
                "description": "设计图画的长 3 格、宽 2 格，比例尺 1:2——真实尺寸要放大几倍？在地块上铺出来。",
                "simulator_type": "building_level4",
                "simulator_config": {
                    "mode": "scale",
                    "design_w": 3,
                    "design_h": 2,
                    "scale": 2,
                    "scale_label": "1:2",
                    "target_w": 6,
                    "target_h": 4,
                    "grid_cols": 10,
                    "grid_rows": 8,
                },
                "completion_criteria": {"hit_target": True},
                "rewards": {"xp": 60, "card": "card_thinking_transform"},
                "level_knowledge": [
                    {
                        "id": "elem_fenshu",
                        "name": "分数运算",
                        "explanation": (
                            "比例尺 1:2 就是'图上 1 格 = 真实 2 格'，真实尺寸 = 图上尺寸 × 2，"
                            "也就是 ×(2/1)。把比看成倍数，缩放就变成了乘法。"
                        ),
                    },
                    {
                        "id": "elem_sifasuan",
                        "name": "四则运算",
                        "explanation": (
                            "3 格放成 3×2=6 格、2 格放成 2×2=4 格。缩放就是把每个尺寸都乘上"
                            "同一个倍数，不能只改一条边。"
                        ),
                    },
                ],
            },
            {
                "id": 5,
                "name": "立体仓库",
                "description": "给小镇设计一个长方体仓库，长 5、宽 3、高 2，体积要达到 30m³。",
                "simulator_type": "building_level5",
                "simulator_config": {
                    "mode": "volume",
                    "target_volume": 30,
                    "length_range": [1, 8],
                    "width_range": [1, 8],
                    "height_range": [1, 8],
                },
                "completion_criteria": {"hit_target": True},
                "rewards": {"xp": 80, "card": "card_thinking_decomp"},
                "level_knowledge": [
                    {
                        "id": "elem_tiji",
                        "name": "体积公式",
                        "explanation": (
                            "仓库体积 = 长 × 宽 × 高。5×3×2=30，正好 30m³。"
                            "体积就是'里面能装几个 1m³ 的小方块'。"
                        ),
                    },
                    {
                        "id": "6b_changfangti",
                        "name": "长方体的再认识",
                        "explanation": (
                            "仓库就是长方体：有长、宽、高三个方向。缺一个尺寸，体积就算不出来"
                            "（乘三个数才能得到体积）。"
                        ),
                    },
                ],
            },
            {
                "id": 6,
                "name": "建筑大师",
                "description": "自由创造！用方块搭一座你自己的建筑，搭完保存成作品。",
                "simulator_type": "building_level6",
                "simulator_config": {
                    "mode": "creator",
                    "grid_cols": 10,
                    "grid_rows": 8,
                    "max_height": 6,
                },
                "completion_criteria": {"hit_target": True},
                "rewards": {"xp": 120, "card": "card_thinking_modeling"},
                "level_knowledge": [
                    {
                        "id": "elem_mianji",
                        "name": "面积公式",
                        "explanation": (
                            "你的建筑占地面子 = 长 × 宽，每个柱底都是 1×1 = 1m²。"
                        ),
                    },
                    {
                        "id": "elem_tiji",
                        "name": "体积公式",
                        "explanation": (
                            "建筑总体积 = 所有方块数 = 占地底面积 × 平均高度，"
                            "把搭建的每个方块数一数，就是体积。"
                        ),
                    },
                ],
            },
        ],
        "choices": [
            {
                "id": "lv3_build_choice",
                "at_level": 3,
                "prompt": "城市蓝图打开了！你想先当哪一种建筑师？",
                "options": [
                    {
                        "id": "builder_first",
                        "label": "先做图纸放大师（缩放）",
                        "hint": "把设计图按比例放大成真房子",
                        "focus": "building",
                    },
                    {
                        "id": "warehouse_first",
                        "label": "先做仓库规划师（体积）",
                        "hint": "算好长宽高，装下所有物资",
                        "focus": "volume",
                    },
                ],
            },
        ],
        "badge": "badge_building_master",
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
