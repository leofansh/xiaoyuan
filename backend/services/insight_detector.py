"""顿悟时刻信号检测（模块 I-11.9 P0）。

规则式检测：通过对话内容模式匹配识别顿悟信号。
"""
import logging
import re
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class InsightEvent:
    """顿悟事件。"""
    insight_type: str          # exclamation | key_step | attitude_shift | new_approach | delayed
    student_quote: str         # 学生原话
    confidence: float          # 检测置信度 0-1
    knowledge_node: str = ""   # 关联知识点


EXCLAMATION_PATTERNS = [
    r"啊[！!]", r"哇[！!]", r"原来如此[！!]?", r"我知道了[！!]?",
    r"懂了[！!]", r"明白了[！!]", r"会了[！!]", r"天哪[！!]",
    r"我懂了", r"我知道怎么做", r"原来[是这]么",
]


def detect_insight(
    student_message: str,
    previous_messages: list[dict[str, str]] | None = None,
) -> InsightEvent | None:
    """检测学生消息中的顿悟信号。

    Args:
        student_message: 当前学生消息
        previous_messages: 最近几轮对话历史 [{role, content}, ...]

    Returns: InsightEvent 或 None
    """
    if not student_message:
        return None

    msg = student_message.strip()

    # 1. 感叹词触发（最高优先级）
    for pattern in EXCLAMATION_PATTERNS:
        if re.search(pattern, msg):
            return InsightEvent(
                insight_type="exclamation",
                student_quote=msg,
                confidence=0.9,
            )

    # 2. 态度转变：上一轮说不会，这一轮说会/试
    if previous_messages and len(previous_messages) >= 2:
        prev_user = [
            m for m in previous_messages[-4:] if m.get("role") == "user"
        ]
        if prev_user:
            last_user = prev_user[-1]["content"]
            if (
                re.search(r"(不会|不知道|不懂|不行|做不到)", last_user)
                and re.search(r"(试试|我知道|让我|我想到了|等一下)", msg)
            ):
                return InsightEvent(
                    insight_type="attitude_shift",
                    student_quote=msg,
                    confidence=0.85,
                )

    # 3. 主动说出关键步骤（无小圆提示的解题关键步骤）
    key_step_indicators = [
        r"如果.{0,20}那么", r"所以.{0,10}应该是", r"先.{0,10}再",
        r"等一下.{0,15}可以", r"换个角度", r"反过来想",
    ]
    for pattern in key_step_indicators:
        if re.search(pattern, msg):
            return InsightEvent(
                insight_type="key_step",
                student_quote=msg,
                confidence=0.75,
            )

    # 4. 提出新思路
    new_approach_indicators = [
        r"用.{0,5}是不是可以", r"还有没有别的方法",
        r"我想到一个", r"能不能.{0,10}来",
    ]
    for pattern in new_approach_indicators:
        if re.search(pattern, msg):
            return InsightEvent(
                insight_type="new_approach",
                student_quote=msg,
                confidence=0.7,
            )

    return None


def is_delayed_insight(message: str) -> InsightEvent | None:
    """检测延迟顿悟：学生在非学习时间主动说想通了。"""
    if not message:
        return None
    patterns = [
        r"昨天.{0,10}想通了", r"昨天.{0,10}懂了",
        r"之前.{0,10}想明白了", r"那道题.{0,10}我会了",
        r"突然.{0,5}想通", r"刚才.{0,5}想到",
    ]
    for p in patterns:
        if re.search(p, message):
            return InsightEvent(
                insight_type="delayed",
                student_quote=message,
                confidence=0.95,
            )
    return None
