"""挑战题库（模块 I-11.9 P0）。

按知识点和难度分级的趣味挑战题，与生活/兴趣相关。
"""
import random
from dataclasses import dataclass, field


@dataclass
class ChallengeProblem:
    id: str
    topic_id: str
    title: str
    question: str
    difficulty: int            # 1-5
    hints: list[str] = field(default_factory=list)
    solution_approach: str = ""
    interest_tags: list[str] = field(default_factory=list)
    estimated_minutes: int = 5


CHALLENGE_BANK: list[ChallengeProblem] = [
    ChallengeProblem(
        id="ch_001", topic_id="G6.C.F.A", title="井盖为什么是圆的",
        question="城市的井盖都是圆形的，而不是方形的。你能想到为什么吗？",
        difficulty=2,
        hints=["想象正方形井盖立起来", "正方形沿对角线可以掉下去", "圆形无论怎么转都不会掉下去"],
        solution_approach="圆的直径处处相等，正方形对角线比边长长",
        interest_tags=["生活"], estimated_minutes=3,
    ),
    ChallengeProblem(
        id="ch_002", topic_id="G6.C.R.P", title="荷叶翻倍",
        question="一个池塘里放了1片荷叶，每天面积翻一倍。如果30天刚好铺满整个池塘，那第几天铺了一半？",
        difficulty=3,
        hints=["倒着想", "第30天是100%，前一天呢？", "30天满，29天就是一半"],
        solution_approach="逆向思维：最后一天满，前一天就是一半",
        interest_tags=["自然"], estimated_minutes=3,
    ),
    ChallengeProblem(
        id="ch_003", topic_id="G6.C.R.A", title="赛跑悖论",
        question="小明跑100米用了10秒，小红跑50米用了5秒。他们一样快吗？",
        difficulty=2,
        hints=["速度 = 距离 / 时间", "算一下各自的速度", "别被数字迷惑"],
        solution_approach="速度都是10m/s，但跑更长距离需要更多耐力",
        interest_tags=["运动"], estimated_minutes=3,
    ),
    ChallengeProblem(
        id="ch_004", topic_id="G6.C.P.A", title="披萨分量",
        question="你和3个朋友分一个12寸的披萨，每人一样多。切4块但有2块大，怎么保证公平？",
        difficulty=2,
        hints=["公平=每块面积相同", "圆面积和半径的关系", "切法比大小重要"],
        solution_approach="圆面积与半径平方成正比，需精确计算每块面积",
        interest_tags=["食物"], estimated_minutes=4,
    ),
    ChallengeProblem(
        id="ch_005", topic_id="G7.E.B", title="电梯之谜",
        question="一栋30层大楼有两部电梯。为什么有时候等电梯来得快，有时候很慢？和你在哪层按键有关系吗？",
        difficulty=3,
        hints=["电梯停靠是均匀分布的吗？", "中间楼层被停概率最高", "顶楼和底楼只停一次"],
        solution_approach="中间楼层停靠概率最高",
        interest_tags=["生活"], estimated_minutes=4,
    ),
    ChallengeProblem(
        id="ch_006", topic_id="G6.C.P.B", title="打折陷阱",
        question="一件衣服原价200元，先打8折再打7折，最终价格是多少？和直接打5折比哪个便宜？",
        difficulty=2,
        hints=["8折=乘0.8，再7折=乘0.7", "0.8 x 0.7 = ?", "直接5折=乘0.5"],
        solution_approach="0.8x0.7=0.56，最终56折，比5折贵",
        interest_tags=["购物"], estimated_minutes=2,
    ),
    ChallengeProblem(
        id="ch_007", topic_id="G7.P.A", title="火车过桥",
        question="一列火车长200米，要通过一座长800米的桥。从车头进桥到车尾离桥，一共走了多少米？",
        difficulty=3,
        hints=["火车要完全过桥", "总距离 = 桥长 + 车长", "画个示意图"],
        solution_approach="总距离 = 800+200=1000米",
        interest_tags=["旅行"], estimated_minutes=3,
    ),
    ChallengeProblem(
        id="ch_008", topic_id="G6.C.F.B", title="对称的艺术",
        question="取一张正方形纸片，对折3次后剪一刀，展开后有几块洞？为什么不是3块？",
        difficulty=4,
        hints=["对折3次=2的3次方=8层", "剪一刀穿透所有层", "展开后洞数取决于对称性"],
        solution_approach="每对折一次层数翻倍，剪一刀穿透8层",
        interest_tags=["画画"], estimated_minutes=5,
    ),
]


def get_challenge_by_topic(
    topic_id: str, difficulty_range: tuple[int, int] = (1, 3)
) -> ChallengeProblem | None:
    """根据知识点ID和难度范围获取挑战题。"""
    candidates = [
        c for c in CHALLENGE_BANK
        if c.topic_id == topic_id and difficulty_range[0] <= c.difficulty <= difficulty_range[1]
    ]
    if not candidates:
        candidates = [
            c for c in CHALLENGE_BANK
            if difficulty_range[0] <= c.difficulty <= difficulty_range[1]
        ]
    if not candidates:
        candidates = CHALLENGE_BANK[:3]
    return random.choice(candidates) if candidates else None


def get_random_challenge(max_difficulty: int = 3) -> ChallengeProblem | None:
    """随机获取一道挑战题。"""
    candidates = [c for c in CHALLENGE_BANK if c.difficulty <= max_difficulty]
    return random.choice(candidates) if candidates else None
