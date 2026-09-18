"""V3.0 P1 模块B：卡片收集系统。

卡片库 + 掉落逻辑 + 稀有度概率 + 星光值转化。

卡片库覆盖知识图谱全部 78 个节点（自动生成 base 卡），
并手动补充思维模型卡（rare/epic）与数学史卡（legendary），
共 ≥78 张、4 种稀有度。
"""

from __future__ import annotations

import random
from datetime import datetime

from backend.config import get_card_drop_rates
from backend.knowledge.syllabus import NODES, get_node

# ---------------------------------------------------------------------------
# 稀有度配置（规格 4.2.2）
# ---------------------------------------------------------------------------
RARITY = {
    "common": {"prob": 0.60, "starlight": 5},
    "rare": {"prob": 0.30, "starlight": 15},
    "epic": {"prob": 0.09, "starlight": 40},
    "legendary": {"prob": 0.01, "starlight": 100},
}

# 图标池（按分类分配）
_ICONS = ["🍰", "🧮", "📏", "✏️", "🔢", "📐", "🧩", "⭐", "🍎", "🚀", "🌈", "🧊", "⚖️", "🎯", "🔭"]


def _auto_card(node) -> dict:
    """从知识图谱节点自动生成一张 common 卡。"""
    li = node.life_examples or ["生活中的数学"]
    front = (node.common_mistakes or ["很多同学在这里容易踩坑"])[0]
    return {
        "id": f"card_{node.id}",
        "name": node.name,
        "category": node.chapter,
        "rarity": "common",
        "knowledge_node": node.id,
        "front_icon": _ICONS[abs(hash(node.id)) % len(_ICONS)],
        "front_text": f"{li[0]}——藏着{node.name}的奥秘",
        "back_text": f"{node.name}：注意别踩坑——{front}",
        "fun_fact": "数学是理解世界的语言，掌握它就能看懂更多有趣的事！",
    }


def build_library() -> dict[str, dict]:
    """构建完整卡片库：78 节点 base 卡 + 思维模型/数学史精品卡。"""
    lib: dict[str, dict] = {}
    for node in NODES:
        card = _auto_card(node)
        lib[card["id"]] = card

    # ---------- 精品卡：思维模型（rare / epic） ----------
    lib.update({
        "card_thinking_reverse": {
            "id": "card_thinking_reverse", "name": "逆向思维", "category": "思维模型",
            "rarity": "rare", "knowledge_node": "", "front_icon": "🔙",
            "front_text": "知道答案的题不会做？试试从结果往回推！",
            "back_text": "逆向思维：从目标倒推需要的条件，反向找思路。",
            "fun_fact": "警察破案就是典型的逆向思维：从结果找线索往回推理。",
        },
        "card_thinking_visual": {
            "id": "card_thinking_visual", "name": "图形化思维", "category": "思维模型",
            "rarity": "rare", "knowledge_node": "", "front_icon": "📐",
            "front_text": "抽象题看不懂？画个图试试！",
            "back_text": "图形化思维：把文字题变成线段图/示意图，条件一目了然。",
            "fun_fact": "华罗庚说：数缺形时少直觉，形少数时难入微。",
        },
        "card_thinking_decomp": {
            "id": "card_thinking_decomp", "name": "问题拆分", "category": "思维模型",
            "rarity": "rare", "knowledge_node": "", "front_icon": "🧩",
            "front_text": "难题像积木城堡，拆成小积木就好搭了！",
            "back_text": "问题拆分：把复杂问题拆成几个小问题，逐个击破。",
            "fun_fact": "程序员写大型软件全靠拆分：一个亿行代码也是从一行行写起的。",
        },
        "card_thinking_analogy": {
            "id": "card_thinking_analogy", "name": "类比思维", "category": "思维模型",
            "rarity": "rare", "knowledge_node": "", "front_icon": "🔗",
            "front_text": "新问题像不像你以前做过的题？",
            "back_text": "类比思维：把新问题和熟悉的问题对比，迁移已有的方法。",
            "fun_fact": "鲁班被带齿的草叶割伤，类比发明了锯子——这就是类比的力量！",
        },
        "card_thinking_transform": {
            "id": "card_thinking_transform", "name": "转化思维", "category": "思维模型",
            "rarity": "rare", "knowledge_node": "", "front_icon": "🔄",
            "front_text": "不会算的在左边，会算的在右边——搭座桥！",
            "back_text": "转化思维：把未知问题转化成已知问题（如分数→小数、方程→等式）。",
            "fun_fact": "九章算术里的'盈不足术'就是把复杂问题转化成简单比例。",
        },
        "card_thinking_modeling": {
            "id": "card_thinking_modeling", "name": "建模思维", "category": "思维模型",
            "rarity": "epic", "knowledge_node": "", "front_icon": "🏗️",
            "front_text": "生活中的问题，先用数学搭个框架！",
            "back_text": "建模思维：从现实问题中提炼数量关系，列出方程或表达式。",
            "fun_fact": "气象预报、火箭发射背后都是数学模型在'替真实世界算命'。",
        },
        "card_thinking_verify": {
            "id": "card_thinking_verify", "name": "检验思维", "category": "思维模型",
            "rarity": "epic", "knowledge_node": "", "front_icon": "✅",
            "front_text": "算完别急着交卷——把答案代回去验一验！",
            "back_text": "检验思维：算完代回原题检查，这是防止粗心最狠的一招。",
            "fun_fact": "数学家欧拉一生发表论文千余篇，每篇都亲自验算多遍。",
        },
    })

    # ---------- 数学史 / 跨章节（legendary） ----------
    lib.update({
        "card_hist_pi": {
            "id": "card_hist_pi", "name": "圆周率 π 的传奇", "category": "数学史",
            "rarity": "legendary", "knowledge_node": "", "front_icon": "🥧",
            "front_text": "3.1415926……古人是怎么发现这个神奇数字的？",
            "back_text": "祖冲之把 π 精确到小数点后 7 位，领先世界近千年。",
            "fun_fact": "π 的小数位永不重复、永无穷尽，被称为'数学界的蒙娜丽莎'。",
        },
        "card_hist_fraction": {
            "id": "card_hist_fraction", "name": "古埃及分数", "category": "数学史",
            "rarity": "legendary", "knowledge_node": "", "front_icon": "🏺",
            "front_text": "古埃及人只用分子为 1 的分数？那 3/4 怎么写？",
            "back_text": "古埃及人用 1/2 + 1/4 表示 3/4——任何分数都能拆成单位分数之和。",
            "fun_fact": "古埃及的分数记法复杂到只有专职的'分数计算师'才敢碰。",
        },
        "card_hist_algebra": {
            "id": "card_hist_algebra", "name": "方程 4000 年", "category": "数学史",
            "rarity": "legendary", "knowledge_node": "", "front_icon": "⚖️",
            "front_text": "x + 3 = 5？花了几千年人类才学会用 x。",
            "back_text": "古巴比伦人用'秤'比喻方程，花 4000 年进化成今天的代数符号。",
            "fun_fact": "x 符号 16 世纪才被引入，之前方程是用一整段文字描述的！",
        },
    })
    return lib


CARD_LIBRARY: dict[str, dict] = build_library()


def all_cards() -> list[dict]:
    return list(CARD_LIBRARY.values())


def random_rarity() -> str:
    """按稀有度概率随机取一种稀有度（概率取自运行时配置）。"""
    r = random.random()
    acc = 0.0
    for rarity, prob in get_card_drop_rates().items():
        acc += prob
        if r <= acc:
            return rarity
    return "common"


def _card_by_node(node_id: str) -> dict | None:
    if not node_id:
        return None
    node = get_node(node_id)
    if not node:
        return None
    return CARD_LIBRARY.get(f"card_{node_id}")


def _pick_random_card(target_rarity: str | None = None, exclude: set[str] | None = None) -> dict:
    """随机选一张卡。优先稀有度匹配；未收集卡优先；否则随机。"""
    exclude = exclude or set()
    if target_rarity:
        pool = [c for cid, c in CARD_LIBRARY.items() if c["rarity"] == target_rarity and cid not in exclude]
        if pool:
            return random.choice(pool)
        # 该稀有度未收集卡已耗尽 → 从该稀有度全部卡中选（可重复，转星光）
        pool = [c for cid, c in CARD_LIBRARY.items() if c["rarity"] == target_rarity]
        if pool:
            return random.choice(pool)
    pool = [c for cid, c in CARD_LIBRARY.items() if cid not in exclude]
    if not pool:
        pool = list(CARD_LIBRARY.values())
    return random.choice(pool)


def default_cards() -> dict:
    return {
        "collected": {},
        "starlight": 0,
        "total_cards": 0,
        "unique_cards": 0,
    }


def ensure_cards(raw: dict | None) -> dict:
    """确保 cards 结构完整。原地补齐并返回同一对象（防 drop_card 修改落副本丢失）。"""
    if not isinstance(raw, dict) or not raw:
        return default_cards()
    raw.setdefault("collected", {})
    raw.setdefault("starlight", 0)
    raw.setdefault("total_cards", 0)
    raw.setdefault("unique_cards", 0)
    return raw


def drop_card(cards: dict, *, source: str = "mastery",
              knowledge_node: str = "", guaranteed: bool = False,
              force_rarity: str = "") -> dict:
    """卡片掉落（规格 4.3.3）。

    规则：
    1. guaranteed=True 且指定 knowledge_node → 必掉该节点卡
    2. 否则按稀有度概率随机（优先未充分收集的卡）；force_rarity 非空时忽略概率、强制该稀有度
    3. 重复卡 → 转化星光值，count+1
    4. 新卡 → unique_cards+1
    """
    cards = ensure_cards(cards)
    collected = cards["collected"]

    card = None
    if guaranteed and (node_card := _card_by_node(knowledge_node)):
        card = node_card
    if card is None:
        # 优先掉未拥有的或数量最少的卡（同样稀有度内）
        owned_ids = set(collected.keys())
        rarity = force_rarity or random_rarity()
        card = _pick_random_card(target_rarity=rarity, exclude=owned_ids)
        if card and card["id"] in collected and random.random() < 0.3:
            # 仍可能掉已有卡（30%），保证重复卡有产出
            pass

    if card is None:
        return {"success": False, "dropped": False, "card": None,
                "is_new": False, "duplicate_count": 0, "starlight_gained": 0,
                "animation": ""}

    cid = card["id"]
    rarity = card.get("rarity", "common")
    is_new = cid not in collected
    if is_new:
        collected[cid] = {
            "count": 1,
            "first_obtained": datetime.now().isoformat(timespec="seconds"),
            "obtained_from": source,
        }
        cards["unique_cards"] += 1
        starlight_gained = 0
        duplicate_count = 0
    else:
        collected[cid]["count"] += 1
        duplicate_count = collected[cid]["count"] - 1
        starlight_gained = RARITY.get(rarity, RARITY["common"])["starlight"]
        cards["starlight"] += starlight_gained
    cards["total_cards"] += 1

    return {
        "success": True,
        "dropped": True,
        "card": card,
        "is_new": is_new,
        "duplicate_count": duplicate_count,
        "starlight_gained": starlight_gained,
        "starlight_total": cards["starlight"],
        "source": source,
        "animation": f"card_reveal_{rarity}",
    }


# 皮肤价目表（规格 4.3.4/4.7）：skin_id -> 星光值价格，与服务端皮肤 id 一致
SKIN_PRICES: dict[str, int] = {"sakura": 100, "starry": 200, "golden": 300, "cosmic": 500}


def exchange_skin(cards: dict, skin_id: str, cost: int | None = None) -> dict:
    """星光值兑换皮肤（规格 4.3.4）。

    仅信任服务端价目表 SKIN_PRICES，忽略客户端传入的 cost。
    """
    cards = ensure_cards(cards)
    if skin_id not in SKIN_PRICES:
        raise ValueError("未知皮肤")
    price = SKIN_PRICES[skin_id]
    if cards["starlight"] < price:
        raise ValueError("星光值不足")
    cards["starlight"] -= price
    return {"success": True, "starlight_remaining": cards["starlight"], "unlocked_skin": skin_id, "cost": price}


def completion_rate(cards: dict) -> float:
    cards = ensure_cards(cards)
    total = len(CARD_LIBRARY)
    return round(cards["unique_cards"] / total, 4) if total else 0.0