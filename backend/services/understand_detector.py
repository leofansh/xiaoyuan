"""双向有效交流（模块 L.2）：模糊表达消解信号分类器。

规格：docs/V3.0开发规格说明书.md 模块 L

孩子说"我不会"有 8 种含义，本模块用关键词规则把模糊表达归类为
确定性信号（置信度 + 建议消解动作），供 chat 层触发确认流程。

设计原则（与 offload_detector 一致）：
- 纯规则实现，不依赖 LLM，可独立单测
- 规则优先：关键词命中即返回信号；未命中返回 None（由 persona 自然应对）
- 不产生误伤：语境敏感词（如"我不会"）只在教学节点内才被判定为需求助信号，
  节点判定由 chat 层结合会话状态完成，本模块只负责分类
"""
import re
from dataclasses import dataclass, field
from typing import Literal


SignalType = Literal[
    "cant_do",             # "我不会" → 概念不懂/题目没读懂/不想做
    "text_confusion",      # "看不懂""没读懂" → 文字理解障碍
    "calc_wrong",          # "算出来不对""答案不对" → 计算/方法错误
    "method_conflict",     # "老师不是这么教的" → 方法冲突
    "fake_understand",     # "知道了""嗯""哦" → 假性理解/敷衍
    "metacognition_gap",   # "我就是不会" → 元认知不足
    "emotional_fatigue",   # "好烦""不想做" → 情绪疲劳
    "claimed_understand",  # "我懂了""我会了" → 真懂/假懂
]


@dataclass
class UnderstandingSignal:
    """模糊表达信号。"""
    signal: SignalType        # 信号类型（8 类之一）
    confidence: float         # 检测置信度 0-1
    detail: str               # 触发原因说明
    student_quote: str        # 学生原话
    matched_keyword: str = ""  # 命中的关键词/短语
    # 建议消解动作（对应规格 L.2 信号分类表的"消解动作"）
    action: str = ""          # confirm_question / feynman_check / show_steps / verify_variant / existing_flow / calm_fatigue

    @property
    def needs_confirmation(self) -> bool:
        """是否需要 chat 层短路确认（不进 LLM 直接回复）。"""
        return self.signal in ("fake_understand", "metacognition_gap", "cant_do", "text_confusion")


# ===== 信号关键词词典（规格 L.2） =====

# 1. "我不会"——最模糊的表达，需确认属于哪一种
_CANT_DO = [
    "我不会", "不会做", "不会写", "不会算", "做不来", "写不出来",
    "搞不定", "解不出", "弄不出来", "不会解",
]

# 2. 文字理解障碍
_TEXT_CONFUSION = [
    "看不懂", "没读懂", "读不懂", "看不明白", "没看明白", "不理解题意",
    "看不懂题", "题目看不懂", "不知道题目什么意思",
]

# 3. 计算/方法错误
_CALC_WRONG = [
    "算出来不对", "答案不对", "算错了", "结果不对", "算的不对", "答案错了",
    "算的数不对", "和答案不一样", "验算不对",
]

# 4. 方法冲突（"老师不是这么教的"）
_METHOD_CONFLICT = [
    "老师不是这么教的", "老师不是这样说", "我们老师不这样", "老师教的不是这样",
    "老师不是这么讲", "课本不是这么写", "老师说的不一样",
]

# 5. 假性理解/敷衍（短确认词，须在教学讲解节点内才判定）
_FAKE_UNDERSTAND = [
    "知道了", "懂了", "知道啦", "懂啦", "明白了", "明白啦",
    "了解", "晓得了", "嗯", "哦", "嗯嗯", "哦哦", "好",
    "ok", "OK", "不错", "会了", "会啦",
]

# 6. 元认知不足（说不出卡点）
_METACOGNITION_GAP = [
    "我就是不会", "就是不懂", "反正不会", "说不出哪里不会", "不知道卡在哪",
    "不知道哪不懂", "就是不知道", "说不上来", "不知道为什么不会",
]

# 7. 情绪疲劳（转已有心理保护流程）
_EMOTIONAL_FATIGUE = [
    "好烦", "不想做", "不想做了", "烦死了", "不想学", "好累不想", "没心情",
]

# 8. 声称已懂（真懂/假懂，须出变式题验证）
_CLAIMED_UNDERSTAND = [
    "我懂了", "我会了", "我明白了", "我知道了", "我懂啦", "我会啦", "我明白啦",
    "听懂了", "学会了",
]


# ===== 排除规则：避免把"教/学"语境误判为求助 =====
# 出现在"我会了/我学会了"等短语中不算求助（由 _CLAIMED 优先处理）
_CANT_DO_EXCLUDE = ["我不会放弃", "我不怕", "我不会输"]  # 励志/对抗语境


def _strip_punct(text: str) -> str:
    return re.sub(r"[，。！？,.!?、\s]", "", text or "")


def _match_any(text: str, keywords: list[str]) -> str:
    """返回命中的第一个关键词（保持原文判断，不剥离标点）。"""
    stripped = _strip_punct(text)
    for kw in keywords:
        if kw in stripped:
            return kw
    return ""


def _match_any_raw(text: str, keywords: list[str]) -> str:
    """原样匹配（保留标点与大小写敏感词）。"""
    for kw in keywords:
        if kw in text:
            return kw
    return ""


def classify_utterance(message: str) -> UnderstandingSignal | None:
    """把学生消息分类为理解信号（规则优先，8 类）。

    Args:
        message: 学生原始消息

    Returns:
        命中信号；未命中返回 None。优先级：
        情绪疲劳 > 方法冲突 > 元认知不足 > 假性理解 > 声称已懂 >
        文字障碍 > 计算错误 > "我不会"。多重含义时择高优先级。
    """
    msg = (message or "").strip()
    if not msg:
        return None

    # 7. 情绪疲劳（最高优先级——先照顾情绪，转已有心理保护流程）
    kw = _match_any_raw(msg, _EMOTIONAL_FATIGUE)
    if kw:
        return UnderstandingSignal(
            signal="emotional_fatigue",
            confidence=0.9,
            detail="表达疲惫/烦躁，情绪疲劳信号",
            student_quote=msg,
            matched_keyword=kw,
            action="existing_flow",
        )

    # 8. 声称已懂——优先于假性理解（"我懂了"含"懂了"）
    kw = _match_any(msg, _CLAIMED_UNDERSTAND)
    if kw:
        return UnderstandingSignal(
            signal="claimed_understand",
            confidence=0.85,
            detail="声称已懂，需变式题验证真假",
            student_quote=msg,
            matched_keyword=kw,
            action="verify_variant",
        )

    # 4. 方法冲突
    kw = _match_any(msg, _METHOD_CONFLICT)
    if kw:
        return UnderstandingSignal(
            signal="method_conflict",
            confidence=0.95,
            detail="教学方法冲突，先接住再讲等价性",
            student_quote=msg,
            matched_keyword=kw,
            action="confirm_question",
        )

    # 5. 假性理解/敷衍（短确认词；是否触发费曼由 chat 层按教学节点判定）
    kw = _match_any(msg, _FAKE_UNDERSTAND)
    if kw and len(_strip_punct(msg)) <= 12:
        return UnderstandingSignal(
            signal="fake_understand",
            confidence=0.8,
            detail="短确认词/敷衍回应，疑似假性理解",
            student_quote=msg,
            matched_keyword=kw,
            action="feynman_check",
        )

    # 6. 元认知不足
    kw = _match_any(msg, _METACOGNITION_GAP)
    if kw:
        return UnderstandingSignal(
            signal="metacognition_gap",
            confidence=0.9,
            detail="说不出卡点，元认知不足，需台阶式诊断",
            student_quote=msg,
            matched_keyword=kw,
            action="show_steps",
        )

    # 1. "我不会"（排除励志语境）
    if not any(ex in msg for ex in _CANT_DO_EXCLUDE):
        kw = _match_any(msg, _CANT_DO)
        if kw:
            return UnderstandingSignal(
                signal="cant_do",
                confidence=0.8,
                detail='"我不会"有 8 种含义，需确认是哪一种再对症行动',
                student_quote=msg,
                matched_keyword=kw,
                action="confirm_question",
            )

    # 2. 文字理解障碍
    kw = _match_any(msg, _TEXT_CONFUSION)
    if kw:
        return UnderstandingSignal(
            signal="text_confusion",
            confidence=0.9,
            detail="文字理解障碍，拆句子+圈关键词+画图",
            student_quote=msg,
            matched_keyword=kw,
            action="confirm_question",
        )

    # 3. 计算/方法错误
    kw = _match_any(msg, _CALC_WRONG)
    if kw:
        return UnderstandingSignal(
            signal="calc_wrong",
            confidence=0.8,
            detail="计算/方法错误，请孩子展示过程",
            student_quote=msg,
            matched_keyword=kw,
            action="existing_flow",
        )

    return None


# ===== 确认话术库（每次随机选一句，避免机械重复，规格 L.2） =====
CONFIRM_PHRASES: dict[SignalType, list[str]] = {
    "cant_do": [
        "没关系，我们先弄清楚是哪一种「不会」——是看不懂题目，还是不知道从哪里开始？",
        "「我不会」其实有好几种，你先告诉我是哪种：是题目没读懂，还是中间的哪一步卡住了？还是现在有点不想做？",
        "好，那我们一步步来——你先说说，是哪儿让你觉得难？是题目看不懂，还是不知道第一步干什么？",
    ],
    "text_confusion": [
        "没关系，我们先把这句话拆开看。你觉得哪个词或哪句话看不懂？",
        "看不懂很正常，我们一句一句来——先告诉我，题目里哪些字不认识或者不明白？",
        "来，我们把题目拆成小块。我先读一遍，你随时喊停：哪里模糊我们就圈哪里。",
    ],
    "calc_wrong": [
        "差一点点！把你的计算过程给我看看（打字或者拍照都行），我们一起找找卡在哪一步？",
        "答案不对没关系，过程比答案更重要——你把这题的步骤发给我看看？",
        "我们一起验算一下——你是按什么顺序算的？写出来我们对比看看？",
    ],
    "method_conflict": [
        "两种方法其实都对，都通向同一个答案！我们先看看老师的方法，再对比我们学的方法，它们为什么等价？",
        "老师的方法和小圆的方法都是好方法。我们先弄明白老师那一步为什么要这样做，再连回我们学的知识。",
        "不冲突哦，就像去同一个地方有两条路。我们把两条路都摆出来，看看它们在哪里汇合？",
    ],
    "fake_understand": [
        "你这么快就说「知道了」啦？那用你自己的话说说看，这个规律/方法是什么？",
        "真的懂啦？那我考考你——用自己的话给我讲讲，刚才这儿是怎么回事？",
        "很好！既然知道了，那你来说说看：这一步我们到底在做什么？用自己的话讲一遍？",
    ],
    "metacognition_gap": [
        "说不出卡在哪没关系，我们把这道题拆成几个小台阶，你告诉我是哪个台阶让你觉得难？",
        "没有头绪很正常！我把解题过程拆成几步，你一步一步看，在第几步停下来告诉我？",
        "我们换个方式：下面是这道题的几个步骤，你看看自己是卡在哪一步？",
    ],
    "emotional_fatigue": [
        "辛苦啦，觉得烦就先歇口气，没关系的。我们也可以只聊聊天。",
        "不想做就不做，你已经很努力了。我们先放松一下好吗？",
    ],
    "claimed_understand": [
        "哇，很棒！那我出一道小小的变式题考考你，看看是不是真会了？就一道，超快！",
        "太好了！既然会了，我们换个数字试一道类似的，巩固一下？",
    ],
}


def pick_confirm_phrase(signal: SignalType) -> str:
    """按信号类型随机取一句确认话术。"""
    import random

    phrases = CONFIRM_PHRASES.get(
        signal,
        ["没关系，我们慢慢来，你先说说看？"],
    )
    return random.choice(phrases)


# ===== 费曼检查话术（L.4）与台阶诊断话术 =====
FEYNMAN_OPENERS: list[str] = [
    "用你的话说说看，刚才这个规律/方法是什么？",
    "你自己来讲一遍：我们刚才学会的是什么？怎么用它？",
    "现在轮到你当小老师啦——给我讲讲这个知识点？",
]

FEYNMAN_PASS_PRAISE: list[str] = [
    "讲得清清楚楚！你这不是知道，是真正理解了！",
    "你用自己的话讲出来，说明是真的懂了！",
    "声音里都是自信呀，这个知识点你拿下了！",
]

FEYNMAN_FAIL_GUIDE: list[str] = [
    "没关系！能说出来一半已经很棒了。我们换个讲法，再讲一遍。",
    "记不起来很正常，我们不着急。这次我用另一个角度再讲一遍。",
]


def build_step_diagnostic(topic_name: str, steps: list[dict]) -> str:
    """台阶式诊断的候选列表文本（L.3）。

    Args:
        topic_name: 知识点名称
        steps: diagnostic_steps 列表（每项含 step/name/check_question）

    Returns:
        排版好的台阶列表，供小圆输出。
    """
    lines = [f"关于「{topic_name}」，我们把它拆成几个小台阶，你看看卡在哪一步？"]
    for s in steps:
        lines.append(
            f"{s['step']}. {s['name']}——{s.get('check_question', '这步你会吗？')}"
        )
    lines.append("直接告诉我数字就行，比如「第2步」；如果都觉得会，就从第1步开始试～")
    return "\n".join(lines)


# ===== L.2 LLM 兜底通道（规格：关键词规则优先 + LLM 判断兜底，命中任一即触发确认） =====
# 规则未命中时，由 chat 层调用 LLM 判定孩子表达是否属于 8 类信号之一。
# 解析函数 parse_llm_classify 为纯函数（无 LLM 依赖），可独立单测。

# 给 LLM 的信号分类依据（与上方关键词词典同源的 8 类定义，供 LLM 对未命中表达做语义判定）
_LLM_CLASSIFY_GUIDE = "\n".join([
    "cant_do: 孩子说\"我不会\"\"做不来\"等，但表达较绕/具体，判定：概念不懂或题目没读懂或不知从何入手",
    "text_confusion: 孩子说\"看不懂\"\"没读懂\"\"不理解\"(文字/题目层面)，判定：文字理解障碍",
    "calc_wrong: 孩子说\"算出来不对\"\"答案不对\"\"这步错了\"，判定：计算/方法错误",
    "method_conflict: 孩子说\"老师不是这么教的\"\"我们老师不是这样\"，判定：教学方法冲突",
    "fake_understand: 孩子用很短的话表示懂了/敷衍（\"知道了\"\"哦\"\"嗯\"\"好\"），判定：假性理解/敷衍",
    "metacognition_gap: 孩子表达出\"说不出自己卡在哪\"（\"反正不会\"\"就是不懂\"\"说不上来\"），判定：元认知不足",
    "emotional_fatigue: 孩子表达烦躁/疲惫/抗拒（\"好烦\"\"不想做\"\"没心情\"），判定：情绪疲劳",
    "claimed_understand: 孩子明确声称自己会了（\"我懂了\"\"我会了\"\"明白了\"），判定：真懂/假懂待验证",
])

LLM_CLASSIFY_PROMPT = (
    "你是小圆助教（陪伴小学生学数学）的理解信号分类器。孩子可能用多种口语表达学习困难，"
    "请把以下孩子说的话归类为 8 种理解信号之一。信号定义：\n"
    + _LLM_CLASSIFY_GUIDE
    + "\n\n要求：\n"
    "1. 只能输出上述 8 类中恰好的一个信号名，或输出 none 表示不属于任何一类\n"
    "2. 除非信号非常明确，否则倾向 none（宁可不打扰，也不误伤孩子）\n"
    "3. 只需输出信号名，不要输出任何解释"
)

# LLM 兜底命中的置信度（低于规则命中——无关键词依据，仅为语义判断）
LLM_FALLBACK_CONFIDENCE = 0.6

# 信号名 → 建议消解动作（与 classify_utterance 返回一致，供 chat 层短路）
_LLM_SIGNAL_ACTIONS: dict[str, str] = {
    "cant_do": "confirm_question",
    "text_confusion": "confirm_question",
    "calc_wrong": "existing_flow",
    "method_conflict": "confirm_question",
    "fake_understand": "feynman_check",
    "metacognition_gap": "show_steps",
    "emotional_fatigue": "existing_flow",
    "claimed_understand": "verify_variant",
}


def parse_llm_classify(text: str) -> UnderstandingSignal | None:
    """解析 LLM 兜底输出为 UnderstandingSignal。

    兼容 LLM 输出各种形态：纯信号名 / 带引号 / 带标点 / 多余解释 / 全大写。
    解析失败或输出非法 → None（宁缺毋滥，由 persona 自然应对）。

    Args:
        text: LLM 原始输出

    Returns:
        合法信号（置信度 LLM_FALLBACK_CONFIDENCE）；否则 None。
    """
    raw = (text or "").strip()
    if not raw:
        return None
    # 按行/逗号切分取出候选词，逐个清洗匹配
    candidates = re.split(r"[\s,，。.!！?？;；]+", raw)
    for cand in candidates:
        word = cand.strip().strip("\"'`“”‘’")
        word = word.lower()
        word = re.sub(r"\W+", "", word)
        if word == "none":
            return None
        if word in _LLM_SIGNAL_ACTIONS:
            return UnderstandingSignal(
                signal=word,  # type: ignore[arg-type]
                confidence=LLM_FALLBACK_CONFIDENCE,
                detail="LLM 兜底语义判定",
                student_quote="",
                matched_keyword="",
                action=_LLM_SIGNAL_ACTIONS[word],
            )
    return None
