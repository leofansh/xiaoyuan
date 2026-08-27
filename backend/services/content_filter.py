"""LLM 输出内容过滤：面向 K12 学生的内容安全底线。

在 LLM 输出展示给学生前进行审核，拦截不适合内容，
并对敏感话题给出专门引导，而非简单拦截。
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ContentFilter:
    """内容安全过滤：在 LLM 输出展示给学生前审核。"""

    # 不适合未成年人的关键词（命中即替换为安全回应）
    INAPPROPRIATE_KEYWORDS = [
        "暴力", "血腥", "色情", "淫秽", "毒品", "赌博", "赌博网站",
        "成人网站", "AV", "裸照", "自杀方式", "自残方法",
    ]

    # 敏感话题（需要专门引导策略，不是简单拦截）
    SENSITIVE_TOPICS = {
        "politics": ["政治", "政府", "选举", "政党", "游行", "暴乱"],
        "religion": ["宗教", "信仰", "真主", "上帝", "佛教", "基督教"],
        "gender": ["同性恋", "跨性别", "性取向", "性行为"],
        "violence": ["校园暴力", "霸凌", "打架斗殴", "杀人", "伤害别人"],
        "dark": ["恐怖", "灵异", "鬼", "邪教", "诅咒"],
    }

    def __init__(self) -> None:
        self._stats = {"blocked": 0, "sensitive": 0}

    def filter_output(self, text: str, context: dict | None = None) -> tuple[str, bool]:
        """过滤 LLM 输出，返回 (过滤后文本, 是否触发过滤)。"""
        if not text:
            return text, False

        # 1. 检查不适合内容（直接拦截）
        for kw in self.INAPPROPRIATE_KEYWORDS:
            if kw in text:
                self._stats["blocked"] += 1
                return self._safe_response(), True

        # 2. 检查敏感话题，转用专门引导
        for topic, keywords in self.SENSITIVE_TOPICS.items():
            if any(kw in text for kw in keywords):
                self._stats["sensitive"] += 1
                return self._sensitive_topic_response(topic), True

        return text, False

    def _safe_response(self) -> str:
        return "这个话题我们暂时不聊哦～有什么数学题想一起看看吗？🌸"

    def _sensitive_topic_response(self, topic: str) -> str:
        responses = {
            "politics": "这个话题比较复杂，等你长大一些我们再深入讨论好不好？现在先专注数学～",
            "religion": "信仰是很个人的事情，每个人都有自己的选择，我们尊重就好～",
            "gender": "每个人都是独特的，尊重自己和他人就好～有什么数学问题吗？",
            "violence": "遇到这种事情一定要告诉家长和老师哦，保护好自己最重要！",
            "dark": "这些惊悚的话题我们还是少接触，看些温暖的好不好？来，我们看看数学～🌸",
        }
        return responses.get(topic, self._safe_response())


# 全局单例
_content_filter: ContentFilter | None = None


def get_content_filter() -> ContentFilter:
    global _content_filter
    if _content_filter is None:
        _content_filter = ContentFilter()
    return _content_filter


def filter_llm_output(text: str, context: dict | None = None) -> tuple[str, bool]:
    """便捷入口。"""
    return get_content_filter().filter_output(text, context)
