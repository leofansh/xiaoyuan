"""防认知卸载护栏（模块 K.2）：规则式检测认知卸载信号。

认知卸载：学生用「抄步骤 / 乱猜答案 / 频繁索要提示 / 直接索要答案」等方式，
把本应自己承担的思考责任推给小圆。检测器为纯规则实现，不依赖 LLM，可独立单测。
"""
import difflib
import re
from dataclasses import dataclass
from typing import Literal


SignalType = Literal["copy_steps", "random_guessing", "hint_dependent", "direct_ask"]


@dataclass
class OffloadSignal:
    """认知卸载信号。"""
    signal: SignalType          # 信号类型
    confidence: float           # 检测置信度 0-1
    detail: str                 # 触发原因说明
    student_quote: str          # 学生原话


# ===== 直接索要答案短语（中英） =====
_DIRECT_ASK_CN = [
    "告诉我答案", "直接说", "答案给我", "报答案",
    "直接告诉我", "就说答案", "写出来",
]
_DIRECT_ASK_EN = ["just tell me", "give me the answer"]

# ===== 求助词（用于排除乱猜误判） =====
_HELP_WORDS = ("不知道", "不会", "不懂", "提示", "教我", "怎么做")

# ===== 索要提示短语（hint_dependent） =====
_HINT_WORDS = ("提示", "再说一点", "继续提示")

_SENTENCE_SPLIT = re.compile(r"[。！？!?\n]+")


def _split_sentences(text: str) -> list[str]:
    """按中文/英文句末标点与换行切分句子。"""
    if not text:
        return []
    return [part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip()]


def detect_copy_steps(
    user_message: str,
    history: list[dict[str, str]],
) -> OffloadSignal | None:
    """检测「抄步骤」：学生直接复述小圆上一步的讲解。

    Args:
        user_message: 当前学生消息
        history: 对话历史 [{role, content}, ...]

    Returns:
        取 history 最后一条 assistant 消息切句，逐句与 user_message 做
        difflib 相似度比较，ratio >= 0.9 或（长度 >10 且 ratio >= 0.85）
        视为照抄。返回 OffloadSignal 或 None。
    """
    msg = (user_message or "").strip()
    if not msg or not history:
        return None

    last_assistant = next(
        (m.get("content", "") for m in reversed(history) if m.get("role") == "assistant"),
        "",
    )
    if not last_assistant:
        return None

    best_ratio = max(
        (difflib.SequenceMatcher(None, sent, msg).ratio()
         for sent in _split_sentences(last_assistant)),
        default=0.0,
    )

    if best_ratio >= 0.9 or (len(msg) > 10 and best_ratio >= 0.85):
        return OffloadSignal(
            signal="copy_steps",
            confidence=0.9,
            detail="疑似照抄/复述小圆上一步讲解的步骤",
            student_quote=msg,
        )
    return None


def detect_random_guessing(
    recent_user_msgs: list[str],
    consecutive_wrong: int,
) -> OffloadSignal | None:
    """检测「乱猜答案」：连续 3 条用户消息都很短且不含求助词。

    Args:
        recent_user_msgs: 最近的用户消息（含当前消息，按时间升序）
        consecutive_wrong: 连续错误轮数（保留上下文，当前规则未使用）

    Returns:
        连续 3 条消息长度 <12 且不含「不知道/不会/不懂/提示/教我/怎么做」
        等求助词时触发。返回 OffloadSignal 或 None。
    """
    msgs = [m for m in (recent_user_msgs or [])[-3:]]
    if len(msgs) < 3:
        return None

    def _is_guess(m: str) -> bool:
        s = (m or "").strip()
        return len(s) < 12 and not any(w in s for w in _HELP_WORDS)

    if all(_is_guess(m) for m in msgs):
        return OffloadSignal(
            signal="random_guessing",
            confidence=0.75,
            detail="连续 3 条短消息且未求助，疑似随机试答案",
            student_quote=msgs[-1],
        )
    return None


def detect_hint_dependent(
    user_message: str,
    history: list[dict[str, str]],
) -> OffloadSignal | None:
    """检测「提示依赖」：用户消息累计索要提示 >=3 次。

    Args:
        user_message: 当前学生消息
        history: 对话历史 [{role, content}, ...]

    Returns:
        history 中用户消息 + 当前消息中，含「提示/再说一点/继续提示」
        的次数 >=3 时触发。返回 OffloadSignal 或 None。
    """
    user_msgs = [m.get("content", "") for m in (history or []) if m.get("role") == "user"]
    user_msgs.append(user_message or "")

    hint_count = sum(1 for m in user_msgs if any(w in m for w in _HINT_WORDS))
    if hint_count >= 3:
        return OffloadSignal(
            signal="hint_dependent",
            confidence=0.8,
            detail="累计多次索要提示，疑似依赖外部提示而非自主思考",
            student_quote=(user_message or "").strip(),
        )
    return None


def detect_direct_ask(message: str) -> OffloadSignal | None:
    """检测「直接索要答案」：学生明确要求直接给出答案。

    Args:
        message: 学生消息

    Returns:
        命中中英文直接索要答案短语时触发，置信度 1.0。返回 OffloadSignal 或 None。
    """
    msg = (message or "").strip()
    if not msg:
        return None

    lowered = msg.lower()
    if any(p in msg for p in _DIRECT_ASK_CN) or any(p in lowered for p in _DIRECT_ASK_EN):
        return OffloadSignal(
            signal="direct_ask",
            confidence=1.0,
            detail="直接索要答案，未展示自主思考意图",
            student_quote=msg,
        )
    return None


def detect_offload_signals(
    student,
    user_message: str,
    recent_user_msgs: list[str],
) -> list[OffloadSignal]:
    """汇总检测认知卸载信号（单轮最多返回 1 个）。

    优先级：direct_ask > copy_steps > random_guessing > hint_dependent。

    Args:
        student: 学生档案（保留上下文，内部读取 current_session 的
            history 与 consecutive_wrong）
        user_message: 当前学生消息
        recent_user_msgs: 最近的用户消息（含当前消息）

    Returns:
        命中信号列表（最多 1 个）。
    """
    sess = getattr(student, "current_session", None)
    history = getattr(sess, "history", None) or []
    consecutive_wrong = getattr(sess, "consecutive_wrong", 0) or 0

    msg = user_message or ""

    signal = detect_direct_ask(msg)
    if signal:
        return [signal]

    signal = detect_copy_steps(msg, history)
    if signal:
        return [signal]

    signal = detect_random_guessing(recent_user_msgs or [], consecutive_wrong)
    if signal:
        return [signal]

    signal = detect_hint_dependent(msg, history)
    if signal:
        return [signal]

    return []


# ===== 干预话术（温暖引导式，绝不批评） =====
INTERVENTION_PHRASES: dict[str, list[str]] = {
    "copy_steps": [
        "等等，这一步我们不用抄——你试着用自己的话重新说一遍，不会的地方我陪你慢慢捋",
        "我发现你在复述我刚才的话啦。没关系，我们换种方式：你用自己的理解讲讲这步为什么这么走？",
        "先停一下下，别急着照着说。你闭上眼睛想想，这一步到底在做什么？用自己的话说给我听好不好？",
    ],
    "random_guessing": [
        "先别急着试数字，我们停一下。这道题你想先从哪里入手？",
        "感觉你在猜答案哦，没关系的。我们先读读题目，它给了我们哪些条件？",
        "不着急填答案，我们慢慢来。你觉得第一个要想清楚的是什么？",
    ],
    "hint_dependent": [
        "这次我们不用提示，你先告诉我：你觉得第一步该做什么？",
        "我先不给你提示啦，因为我相信你可以自己想起来。试着回忆一下，类似的题我们是怎么开的头？",
        "你已经问了好几次提示了，我想听听你的想法。哪怕只是猜一个开头，也大胆说出来？",
    ],
    "direct_ask": [
        "我可不能直接给你答案哦，那样你就学不到啦。我们先看看题目在问什么——你觉得哪个条件最关键？",
        "直接要答案可不行呀，我想陪你一起把它想明白。你觉得这道题第一步该看什么？",
        "答案留给你自己去发现才最有意思。我们一起看看题目，你觉得题目想让我们求出什么？",
    ],
}
