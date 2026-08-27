"""元认知策略库：帮学生学会学习。

四种常见卡点场景 + 对应策略，通过 system prompt 注入小圆的引导话术。
"""

STRATEGIES: dict[str, dict] = {
    "read_unknown": {
        "name": "画图理解",
        "trigger": ["读不懂", "看不明白", "题目在说什么", "看不懂题", "看不懂", "理解不了"],
        "prompt": "题目读不懂的时候，我们试试把题目里的条件画成图好不好？把已知的量标上去，看看能不能看出关系～",
    },
    "calculation_error": {
        "name": "分步验算",
        "trigger": ["算错了", "结果不对", "怎么算出来不一样", "算不出来", "算错"],
        "prompt": "算错了没关系，我们试试分步验算：把每一步单独写出来，盖住答案重算一遍，看看哪一步出了问题～",
    },
    "no_idea": {
        "name": "从问题倒推",
        "trigger": ["没思路", "不知道从哪开始", "怎么下手", "不知道怎么做", "无从下手"],
        "prompt": "没思路的时候，我们试试从问题倒推：题目要我们求什么？要求出这个，需要先知道什么？一步步往回找～",
    },
    "concept_confusion": {
        "name": "回到定义",
        "trigger": ["概念搞混了", "分不清", "这两个有什么区别", "搞不清楚", "混淆", "搞混"],
        "prompt": "概念搞混了，我们回到最原始的定义：用自己的话说说，这两个概念分别是什么意思？举个例子就清楚了～",
    },
}


def detect_strategy(user_message: str) -> str | None:
    """根据学生发言检测推荐的元认知策略，返回策略 key 或 None。"""
    msg = user_message.strip()
    for key, info in STRATEGIES.items():
        for trigger in info["trigger"]:
            if trigger in msg:
                return key
    return None


def get_strategy_prompt(key: str) -> str:
    """返回策略引导话术。"""
    info = STRATEGIES.get(key)
    if not info:
        return ""
    return info["prompt"]
