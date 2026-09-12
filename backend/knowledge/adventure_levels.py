"""V3.0 P2 模块D：闯关冒险地图关卡定义（规格 6.2）。

从知识图谱（backend/knowledge/syllabus.py 的 78 个 KnowledgeNode）自动生成
normal 关卡，并在每个章节末尾补充 1 个 boss 关。关卡字段严格遵循规格 6.2：

- id / name / continent / chapter / knowledge_node / order / type
- unlock_condition / completion_condition / rewards / boss_data

大陆按年级段聚合（共 7 个），normal 关卡在大陆内连续编号 order 1..N，
boss 关 order 900+ 排在大陆最后。数据与知识星空图共用同一份 syllabus，
只是"游戏化视图"。
"""

from __future__ import annotations

from backend.knowledge.syllabus import NODES, BY_ID

# ---------------------------------------------------------------------------
# 大陆划分（规格 6.2）：按章节前缀聚合为 7 个年级段大陆
# ---------------------------------------------------------------------------
CONTINENT_ORDER = [
    "小学回顾",
    "六年级上册",
    "六年级下册",
    "七年级",
    "八年级",
    "九年级",
    "高中",
]


def _continent_for(chapter: str) -> str:
    """按章节前缀判定所属大陆。"""
    if chapter == "小学回顾":
        return "小学回顾"
    if chapter.startswith("六上·"):
        return "六年级上册"
    if chapter.startswith("六下·"):
        return "六年级下册"
    if chapter.startswith("七上·") or chapter.startswith("七下·"):
        return "七年级"
    if chapter.startswith("八上·") or chapter.startswith("八下·"):
        return "八年级"
    if chapter.startswith("九上·") or chapter.startswith("九下·"):
        return "九年级"
    if chapter.startswith("高中·"):
        return "高中"
    return "小学回顾"


# ---------------------------------------------------------------------------
# 趣味命名映射表（规格 6.2：前 10 个章节的关卡用趣味命名）
# 键为知识点 id，值为游戏化关卡名。
# ---------------------------------------------------------------------------
_FUN_NAMES: dict[str, str] = {
    # 第 1 章 小学回顾
    "elem_sifasuan": "算账小能手",
    "elem_yunsuanlv": "凑整魔法师",
    "elem_fenshu": "披萨切分师",
    "elem_xiaoshu": "小数点神探",
    "elem_yinshu": "分组小队长",
    "elem_sushu": "素数守门人",
    "elem_fensujiayin": "拆解大师",
    "elem_fangcheng": "天平预言家",
    "elem_mianji": "铺砖小工匠",
    "elem_tiji": "鱼缸测算师",
    # 第 2 章 六上·第一章 有理数
    "6a_yinru": "正负侦察兵",
    "6a_shuzhou": "数轴向导",
    "6a_jueduizhi": "距离守护者",
    "6a_jiafa": "红包账房先生",
    "6a_jianfa": "温差小能手",
    "6a_chengfa": "负负得正魔术师",
    "6a_chufa": "欠款分配师",
    "6a_chengfang": "折纸倍增师",
    "6a_hunhe": "小票核对员",
    # 第 3 章 六上·第二章 代数式
    "6a_zimu": "字母小侦探",
    "6a_daishushi": "话费精算师",
    "6a_yicishi": "打车计价师",
    # 第 4 章 六上·第三章 一元一次方程
    "6a_fangcheng_gn": "等量关系猎人",
    "6a_fangcheng_jie": "天平平衡师",
    "6a_fangcheng_yy": "追及小飞侠",
    # 第 5 章 六上·第四章 线段与角
    "6a_xianduan": "斑马线测绘师",
    "6a_xianduan_bj": "对折测量员",
    "6a_jiao_gn": "时钟读角人",
    "6a_jiao_bj": "披萨均分师",
    "6a_yubujiao": "直角搭档",
    # 第 6 章 六下·第五章 科学记数法
    "6b_kexuejinshu": "光速小记者",
    # 第 7 章 六下·第六章 一次方程与不等式
    "6b_eryuan": "双未知数猎人",
    "6b_xiaoyuan": "鸡兔同笼大侦探",
    "6b_fangchengzu_yy": "奶茶单价比拼师",
    "6b_dengshi_xz": "余额守护者",
    "6b_jiebudengshi": "套餐精算师",
    # 第 8 章 六下·第七章 尺规作图
    "6b_huaxianduan": "尺规小画家",
    "6b_huajiao": "量角器小能手",
    # 第 9 章 六下·第八章 长方体
    "6b_changfangti": "快递箱探险家",
    # 第 10 章 七上·第二章 整式
    "7a_zhengshi": "购物清单合并师",
    "7a_zhengshi_chufa": "单项式分配师",
}


def _base_name(node_id: str) -> str:
    """节点的趣味名（无映射时退回原名，用于 boss 命名）。"""
    return _FUN_NAMES.get(node_id, BY_ID.get(node_id).name if node_id in BY_ID else node_id)


# ---------------------------------------------------------------------------
# 关卡生成
# ---------------------------------------------------------------------------
def _build_levels() -> dict[str, dict]:
    levels: dict[str, dict] = {}

    # ---- normal 关卡：每个知识点一关，order 在大陆内连续编号 ----
    continent_counter: dict[str, int] = {}
    for node in NODES:
        continent = _continent_for(node.chapter)
        continent_counter[continent] = continent_counter.get(continent, 0) + 1
        order = continent_counter[continent]
        name = _FUN_NAMES.get(node.id, f"冒险：{node.name}")
        levels[f"level_{node.id}"] = {
            "id": f"level_{node.id}",
            "name": name,
            "continent": continent,
            "chapter": node.chapter,
            "knowledge_node": node.id,
            "order": order,
            "type": "normal",
            "unlock_condition": {
                "prerequisite_levels": [f"level_{p}" for p in node.prerequisites],
                "prerequisite_stars": 0,
            },
            "completion_condition": {
                "mastery_threshold": 0.7,
                "min_correct_answers": 1,
            },
            "rewards": {
                "xp": 30,
                "card": f"card_{node.id}",
                "badge": None,
                "stars_max": 3,
            },
            "boss_data": None,
        }

    # ---- boss 关卡：每章节末尾一关，order 900+ 排在大陆最后 ----
    # 章节按 NODES 首次出现顺序排列
    chapter_order: list[str] = []
    for node in NODES:
        if node.chapter not in chapter_order:
            chapter_order.append(node.chapter)

    # 每章全部 normal 关卡 id（保持 NODES 原始顺序）
    chapter_normal_ids: dict[str, list[str]] = {}
    for node in NODES:
        chapter_normal_ids.setdefault(node.chapter, []).append(f"level_{node.id}")

    boss_counter: dict[str, int] = {}
    for chapter in chapter_order:
        nodes = [n for n in NODES if n.chapter == chapter]
        first_node = nodes[0]
        last_node = nodes[-1]
        continent = _continent_for(chapter)
        boss_counter[continent] = boss_counter.get(continent, 0) + 1
        order = 900 + boss_counter[continent]

        prereq_levels = chapter_normal_ids[chapter]
        prerequisite_stars = max(0, len(prereq_levels) * 3 - 6)
        slug = first_node.id
        boss_name = f"{_base_name(first_node.id)}大魔王"
        level_id = f"level_{first_node.id}_boss"

        levels[level_id] = {
            "id": level_id,
            "name": boss_name,
            "continent": continent,
            "chapter": chapter,
            "knowledge_node": last_node.id,
            "order": order,
            "type": "boss",
            "unlock_condition": {
                "prerequisite_levels": prereq_levels,
                "prerequisite_stars": prerequisite_stars,
            },
            "completion_condition": {
                "mastery_threshold": 0.7,
                "min_correct_answers": 3,
            },
            "rewards": {
                "xp": 100,
                "card": f"card_{last_node.id}",
                "badge": f"badge_{slug}_master",
                "stars_max": 3,
            },
            "boss_data": {
                "boss_name": boss_name,
                "boss_hp": 3,
                "problem_count": 3,
            },
        }

    return levels


ADVENTURE_LEVELS: dict[str, dict] = _build_levels()


# ---------------------------------------------------------------------------
# 查询接口
# ---------------------------------------------------------------------------
def all_levels() -> list[dict]:
    """返回全部关卡（normal + boss），按大陆顺序 → order 升序。"""
    def _sort_key(lv: dict) -> tuple[int, int]:
        continent_idx = CONTINENT_ORDER.index(lv["continent"]) if lv["continent"] in CONTINENT_ORDER else 999
        return (continent_idx, lv["order"])

    return sorted(ADVENTURE_LEVELS.values(), key=_sort_key)


def get_level(level_id: str) -> dict | None:
    """按关卡 id 获取定义，不存在返回 None。"""
    return ADVENTURE_LEVELS.get(level_id)


def continents() -> list[dict]:
    """聚合大陆 + 进度占位（规格 6.3.1 的静态骨架，进度由 service 填充）。"""
    result: list[dict] = []
    for cname in CONTINENT_ORDER:
        lvls = sorted(
            (l for l in ADVENTURE_LEVELS.values() if l["continent"] == cname),
            key=lambda l: l["order"],
        )
        result.append({
            "name": cname,
            "levels": [
                {
                    "id": l["id"],
                    "name": l["name"],
                    "order": l["order"],
                    "type": l["type"],
                    "chapter": l["chapter"],
                    "stars_max": l["rewards"]["stars_max"],
                }
                for l in lvls
            ],
            "progress": {
                "completed": 0,
                "total": len(lvls),
                "stars": 0,
                "stars_max": sum(l["rewards"]["stars_max"] for l in lvls),
            },
        })
    return result


def validate() -> list[str]:
    """校验关卡定义完整性，返回错误列表（空列表表示通过）。

    检查项：id 全局唯一、前置关卡引用存在、每个知识点只生成一次、
    boss 的 knowledge_node 存在于 syllabus。
    """
    errors: list[str] = []
    ids = list(ADVENTURE_LEVELS.keys())
    if len(ids) != len(set(ids)):
        errors.append("存在重复的关卡 id")

    normal_nodes: set[str] = set()
    for lid, lv in ADVENTURE_LEVELS.items():
        if lv["type"] == "normal":
            if lv["knowledge_node"] in normal_nodes:
                errors.append(f"知识点 {lv['knowledge_node']} 生成了多个 normal 关卡")
            normal_nodes.add(lv["knowledge_node"])

        for pre in lv["unlock_condition"].get("prerequisite_levels", []):
            if pre not in ADVENTURE_LEVELS:
                errors.append(f"{lid} 的前置关卡 {pre} 不存在（悬空前置）")

        if lv["type"] == "boss":
            if lv["knowledge_node"] not in BY_ID:
                errors.append(f"boss 关 {lid} 的 knowledge_node {lv['knowledge_node']} 不在 syllabus 中")

    if len(normal_nodes) != len(NODES):
        errors.append(f"normal 关卡数 {len(normal_nodes)} 与 syllabus 节点数 {len(NODES)} 不一致")

    return errors
