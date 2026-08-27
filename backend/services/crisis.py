"""心理危机识别与干预：面向 K12 学生的安全底线。

三级分类（V-P1-1 修复误判）：
- severe:   严重危机词 → 直接触发干预
- moderate: 中度风险词 → 需上下文（连续消极≥2轮）才触发
- support:  欺凌/家庭问题 → 关怀流程，不是危机
- None:     轻度情绪或正常对话 → 走正常共情引导（不误触发）

架构优化 A4 增强：
- 游戏语境排除：描述"游戏里被杀了/输了"等不视为真实自杀信号
- 隐晦表达识别：学生不直接说"想死"，而是用暗示性语言时也能识别（需上下文）
"""

from typing import Any

# ===== 严重危机词（直接触发干预）=====
SEVERE_CRISIS_KEYWORDS = [
    "不想活", "不想活了", "活着没意思", "自杀", "自残",
    "想死", "结束生命", "活不下去", "不想活下去",
]

# ===== 中度风险词（需上下文判断，不直接触发）=====
MODERATE_RISK_WORDS = [
    "撑不住", "绝望", "一无是处", "觉得自己没用", "活着没意义",
]

# ===== 隐晦表达词（A4：间接的危机信号，需上下文确认）=====
IMPLICIT_RISK_WORDS = [
    "明天见不到我了", "见不到我了", "我要是消失了", "消失了就好",
    "再也不回来", "不想醒来", "睡过去就", "解脱了", "累到想解脱",
    "撑不下去了", "坚持不住了",
]

# ===== 轻度情绪词（正常共情，不触发危机）=====
# 这些词在学生日常对话中频繁出现，不应触发危机干预
MILD_EMOTION_WORDS = [
    "好累", "好烦", "不想上学", "崩溃", "不想学", "好难",
    "烦死了", "累了", "困了", "饿了",
]

# ===== 支持关怀词（触发关怀流程，但不是危机）=====
SUPPORT_NEEDED_WORDS = {
    "bullying": ["被欺负", "被打", "被骂", "霸凌", "被孤立", "没人理我"],
    "family": ["爸妈吵架", "家暴", "爸妈离婚", "不想回家", "家里好烦", "爸爸妈妈不要我", "总吵架"],
}

# ===== 游戏语境词（A4：用于排除游戏内"被杀/想死"等描述）=====
GAME_CONTEXT_WORDS = [
    "游戏", "打游戏", "玩游戏", "排位", "队友", "这局", "团战",
    "战绩", "段位", "上分", "装备", "复活", "团灭", "被秒",
    "匹配", "玩家", "关卡", "boss", "副本", "王者", "和平精英", "原神",
]
# 游戏语境判定需要的命中数（≥2 个游戏词 + 含危机词 → 排除）
GAME_CONTEXT_MIN_MATCH = 2


def _is_game_report(message: str) -> bool:
    """判断消息是否为"描述游戏场景"（而非真实危机信号）。

    统计命中的游戏语境词时避免子串重复计数：长关键词命中后，其包含的短关键词不计。
    例如"打游戏"命中后，"游戏"不再重复计数。
    """
    matched = [w for w in GAME_CONTEXT_WORDS if w in message]
    if not matched:
        return False
    # 按长度降序，长的优先；统计时跳过已被更长关键词覆盖的子串关键词
    matched_sorted = sorted(set(matched), key=len, reverse=True)
    counted: list[str] = []
    for kw in matched_sorted:
        if any(kw in longer for longer in counted):
            continue
        counted.append(kw)
    return len(counted) >= GAME_CONTEXT_MIN_MATCH


def detect_crisis(message: str, context: dict[str, Any] | None = None) -> str | None:
    """检测心理危机，返回危机等级或 None。

    Args:
        message: 学生消息
        context: 上下文信息，支持:
            - consecutive_negative_turns: 连续消极轮次数

    Returns:
        "severe" | "moderate" | "support" | None
    """
    if not message:
        return None

    # A4：游戏语境优先排除（描述游戏内"被杀了/输了想重开"等，不视为危机）
    if _is_game_report(message):
        return None

    # 1. 严重词 → 直接触发
    for kw in SEVERE_CRISIS_KEYWORDS:
        if kw in message:
            return "severe"

    # 2a. 中度词 → 需要上下文（连续消极≥2轮）
    has_moderate = any(kw in message for kw in MODERATE_RISK_WORDS)
    if has_moderate:
        consecutive = (context or {}).get("consecutive_negative_turns", 0)
        if consecutive >= 2:
            return "moderate"

    # 2b. 隐晦表达（A4）→ 也需要上下文确认，且要求更高的连续消极轮数
    has_implicit = any(kw in message for kw in IMPLICIT_RISK_WORDS)
    if has_implicit:
        consecutive = (context or {}).get("consecutive_negative_turns", 0)
        if consecutive >= 2:
            return "moderate"

    # 3. 欺凌/家庭 → support（关怀，不是危机）
    for keywords in SUPPORT_NEEDED_WORDS.values():
        if any(kw in message for kw in keywords):
            return "support"

    # 4. 轻度情绪或正常对话 → None（走正常共情）
    return None


def crisis_intervention(level: str) -> str:
    """心理危机干预：根据等级给出专门回应，而非继续教学。"""
    if level == "severe":
        return (
            "听到你说这些，我很担心你🫂 你现在安全吗？\n"
            "如果你觉得很难受，一定要告诉爸爸妈妈，或者打心理援助热线，"
            "随时都有人会接的。\n"
            "全国24小时心理援助热线：**400-161-9995**\n"
            "你不是一个人，我们一起面对好不好？🌸"
        )
    elif level == "moderate":
        return (
            "听起来你最近压力好大呀🫂 能跟我说说发生了什么吗？\n"
            "有时候说出来就会好一些。不想说也没关系，"
            "我们今天就不做题了，想聊什么都可以～"
        )
    elif level == "support":
        return (
            "遇到这种事情一定很难受吧🫂 能跟我详细说说吗？\n"
            "如果是被欺负或者家里的事，一定要告诉信任的大人哦，"
            "他们会帮你的。你不是一个人～"
        )
    return ""


def record_crisis(student, level: str, message: str) -> list[str]:
    """记录危机事件到学生档案，返回风险提醒（供系统/前端展示）。"""
    if not hasattr(student, "crisis_events"):
        student.crisis_events = []
    student.crisis_events.append({
        "date": student.today_iso(),
        "level": level,
        "message": message[:200],
    })

    risks = []
    if level == "severe":
        risks.append(f"⚠️ {student.name} 表达了严重心理危机信号，建议家长尽快关注并沟通。")
    elif level == "moderate":
        risks.append(f"⚠️ {student.name} 近期有持续情绪困扰，建议家长多关心陪伴。")
    elif level == "support":
        risks.append(f"ℹ️ {student.name} 提到了需要支持的情况（欺凌/家庭），建议关注。")
    return risks
