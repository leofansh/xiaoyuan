"""V3.0 P1 模块A：宠物/伙伴系统。

虚拟宠物随学习成长：学习行为转化为 XP 喂养宠物，升级解锁外观/皮肤/互动语音。
宠物有心情值（距上次学习时间计算），仅影响展示和话术，不惩罚。
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# 默认宠物初始状态
# ---------------------------------------------------------------------------

DEFAULT_PET = {
    "species": "egg",          # egg/cat/rabbit/dino
    "name": "小蛋蛋",           # 蛋期间的可称，首次学习孵化后可自定义
    "level": 1,
    "exp": 0,
    "exp_to_next": 100,        # 公式 100 * level^1.2
    "mood": "normal",
    "mood_last_update": None,  # ISO 时间
    "unlocked_skins": ["default"],
    "current_skin": "default",
    "total_study_minutes": 0,
    "total_xp_earned": 0,
    "last_feed_time": None,
}

# 皮肤定义：id -> {name, unlock_level, emoji(展示用)}
SKINS = {
    "default": {"name": "初始皮肤", "unlock_level": 1, "emoji": "🐱"},
    "sakura": {"name": "樱花限定", "unlock_level": 5, "emoji": "🌸"},
    "starry": {"name": "星空幻想", "unlock_level": 10, "emoji": "🌌"},
    "golden": {"name": "黄金传说", "unlock_level": 15, "emoji": "👑"},
    "cosmic": {"name": "宇宙霸主", "unlock_level": 20, "emoji": "🪐"},
}

# 物种可选集合（孵化时选择）
SPECIES_CHOICES = ["cat", "rabbit", "dino"]
SPECIES_EMOJI = {"cat": "🐱", "rabbit": "🐰", "dino": "🦕"}


def exp_to_next(level: int) -> int:
    """升级所需经验公式：100 * level^1.2。"""
    return int(100 * (level ** 1.2))


def default_pet() -> dict:
    """获取一份全新的默认宠物状态（每次调用返回独立副本）。"""
    pet = dict(DEFAULT_PET)
    pet["exp_to_next"] = exp_to_next(1)
    return pet


def ensure_pet(pet_raw: dict | None) -> dict:
    """确保 pet 结构完整（旧档案懒初始化 / 缺字段补齐）。

    原地补齐并返回同一对象——保证 add_xp/rename/set_skin 等内部修改
    能同步到调用方持有的引用（否则 XP/升级/皮肤会写入副本丢失）。
    """
    if not isinstance(pet_raw, dict) or not pet_raw:
        return default_pet()
    for k, v in DEFAULT_PET.items():
        if pet_raw.get(k) is None:
            pet_raw[k] = v
    if not pet_raw.get("exp_to_next") or pet_raw["exp_to_next"] < exp_to_next(pet_raw.get("level", 1) or 1):
        pet_raw["exp_to_next"] = exp_to_next(pet_raw.get("level", 1) or 1)
    return pet_raw


def compute_mood(pet: dict) -> tuple[str, str]:
    """实时计算宠物心情（规格 3.2）：<24h happy / 24-72h normal / >72h sad。

    返回 (mood, mood_message)。
    """
    last = pet.get("last_feed_time") or pet.get("mood_last_update")
    now = datetime.now()
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
        except (ValueError, TypeError):
            last_dt = now - timedelta(days=2)
        hours = (now - last_dt).total_seconds() / 3600
        if hours < 24:
            mood = "happy"
        elif hours <= 72:
            mood = "normal"
        else:
            mood = "sad"
    else:
        mood = "normal"
    pet["mood"] = mood
    pet["mood_last_update"] = now.isoformat(timespec="seconds")
    return mood, MOOD_MESSAGES.get(mood, MOOD_MESSAGES["normal"])


# ---------------------------------------------------------------------------
# XP 获取规则（规格 3.2）
# ---------------------------------------------------------------------------
XP_RULES = {
    "session_complete": 20,   # 完成一次会话（≥3轮对话）
    "correct_answer": 5,      # 答对一道题（经评估块确认）
    "combo_5": 10,            # 连续学习 5 连击额外
    "mastery_new": 30,        # 掌握一个新知识点（≥0.7）
    "pbl_level": 50,          # 完成 PBL 项目一关
    "teach_pet": 50,          # I-11.3：讲给宠物听懂
    "problem_create": 10,     # I-11.3：出一道好题
}


def estimate_study_minutes(pet: dict, turn_count: int = 0) -> int:
    """粗估本次会话学习分钟数（用于 total_study_minutes 累计）。"""
    return max(1, min(turn_count, 30))


# ---------------------------------------------------------------------------
# 升级与皮肤
# ---------------------------------------------------------------------------

def add_xp(pet: dict, amount: int, source: str = "", message: str = "") -> dict:
    """给宠物加 XP，处理升级与皮肤解锁。

    返回结果：{"success", "xp_gained", "new_exp", "leveled_up",
               "new_level", "unlocked_skin", "pet"}
    """
    pet = ensure_pet(pet)
    pet["exp"] = pet.get("exp", 0) + amount
    pet["total_xp_earned"] = pet.get("total_xp_earned", 0) + amount
    pet["last_feed_time"] = datetime.now().isoformat(timespec="seconds")
    # 连续升级
    leveled_up = False
    new_level = None
    unlocked_skin = None
    while pet["exp"] >= pet["exp_to_next"]:
        pet["exp"] -= pet["exp_to_next"]
        pet["level"] += 1
        leveled_up = True
        new_level = pet["level"]
        pet["exp_to_next"] = exp_to_next(pet["level"])
        # 皮肤解锁检查
        for skin_id, skin in SKINS.items():
            if skin_id not in pet["unlocked_skins"] and pet["level"] >= skin["unlock_level"]:
                pet["unlocked_skins"].append(skin_id)
                if skin_id != "default" and not unlocked_skin:
                    unlocked_skin = skin_id
    return {
        "success": True,
        "xp_gained": amount,
        "new_exp": pet["exp"],
        "leveled_up": leveled_up,
        "new_level": new_level,
        "unlocked_skin": unlocked_skin,
        "pet": pet,
    }


def hatch(pet: dict, species: str) -> dict:
    """孵化：选择物种并命名（首次学习后调用）。species in SPECIES_CHOICES。"""
    pet = ensure_pet(pet)
    if species in SPECIES_CHOICES:
        pet["species"] = species
        if pet.get("name") == "小蛋蛋":
            pet["name"] = {"cat": "小猫猫", "rabbit": "小兔兔", "dino": "小恐龙"}[species]
    return pet


def set_skin(pet: dict, skin_id: str) -> dict:
    """切换皮肤。"""
    pet = ensure_pet(pet)
    unlocked = set(pet.get("unlocked_skins") or [])
    if skin_id not in unlocked:
        raise ValueError(f"皮肤 {skin_id} 未解锁")
    pet["current_skin"] = skin_id
    return pet


def rename(pet: dict, name: str) -> dict:
    """重命名宠物（长度≤10字符）。"""
    pet = ensure_pet(pet)
    name = name.strip()
    if not name or len(name) > 10:
        raise ValueError("名字需 1-10 个字符")
    pet["name"] = name
    return pet


# ---------------------------------------------------------------------------
# 互动语料库（规格 3.6：按心情+场景分类，每类≥5条；互动随机≥10条）
# ---------------------------------------------------------------------------

MOOD_MESSAGES = {
    "happy": "今天也很开心，在等你一起学数学呢！",
    "normal": "状态不错，随时可以开始学习哦。",
    "sad": "有点想你啦……今天学5分钟也好呀。",
}

_CORPUS = {
    "happy_开场": [
        "喵～今天也来学数学啦！",
        "汪！准备好一起闯关了吗？",
        "今天天气不错，正好适合学点新知识！",
        "我看到你来了，超开心的！",
        "嘿嘿，等你好久啦，我们开始吧！",
    ],
    "happy_答对": [
        "太棒了！我就知道你可以！",
        "哇！答对了！你越来越厉害了！",
        "我就说嘛，你是有天赋的！",
        "耶！又进步了一点点！",
        "这种题也难不倒你啦！",
    ],
    "normal_开场": [
        "喵……你终于来了，我等好久了。",
        "今天想学点什么呀？我陪你。",
        "来了就好，我们慢慢来～",
        "嘿，今天的你状态看起来不错！",
        "一起加油吧！",
    ],
    "sad_开场": [
        "喵……你好久没来了，我有点想你。今天学5分钟也好呀。",
        "你终于来啦！我还以为你忘了我呢。",
        "等你等得好辛苦，不过你来就好！",
        "下次早点来找我玩好不好？",
        "就陪你聊聊天也好，不一定要学习。",
    ],
    "升级": [
        "哇！我升级了！都是因为你努力学数学！",
        "叮！闪闪发光！我又变强了！",
        "升级的感觉太棒了，谢谢你！",
        "我越来越厉害啦，都是你的功劳！",
        "下一个皮肤在向我招手！",
    ],
    "互动_随机": [
        "喵～今天也要加油学数学哦！",
        "你在想什么呀？",
        "我最近在学心算呢，要不要考考我？",
        "一二三，木头人！嘿嘿。",
        "你觉得我今天换皮肤好不好看？",
        "悄悄告诉你，大人说话我都听得懂！",
        "如果你累了，就休息一下，我等你。",
        "我最喜欢看你认真做题的样子！",
        "猜猜我现在什么心情？",
        "数学其实很好玩的对吧？",
        "我们一起把错题变成宝藏吧！",
        "你的进步我都记在心里呢。",
    ],
    "sad_安慰": [
        "别难过啦，谁都有不会的时候。",
        "慢慢来，我会一直陪着你的。",
        "错了也没关系，我们把这个漏洞补上就好。",
        "你已经很棒了，休息下再战！",
    ],
}


def interact_message(pet: dict, scene: str = "互动_随机") -> tuple[str, str]:
    """随机互动语音。返回 (message, animation)。"""
    pet = ensure_pet(pet)
    mood = pet.get("mood", "normal")
    if scene == "开场":
        key = f"{mood}_开场" if mood in ("happy", "normal", "sad") else "normal_开场"
    elif scene == "答对":
        key = f"{mood}_答对" if mood in ("happy", "normal", "sad") else "happy_答对"
    elif scene == "升级":
        key = "升级"
    else:
        key = "互动_随机"
    pool = _CORPUS.get(key) or _CORPUS["互动_随机"]
    message = random.choice(pool)
    animations = ["happy_jump", "wooble", "sparkle", "spin"]
    return message, random.choice(animations)