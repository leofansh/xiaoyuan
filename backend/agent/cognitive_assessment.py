"""认知发展评估：入学诊断题 + 评分逻辑 + 对话式评估流程。

评估认知阶段、工作记忆容量、抽象思维、元认知、执行功能、数学焦虑、学习偏好。
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class AssessmentQuestion:
    id: str
    question: str
    measures: list[str]          # 测量维度
    order: int = 0               # 出题顺序
    concrete_indicator: str = ""  # 具体运算阶段的回答特征
    formal_indicator: str = ""    # 形式运算阶段的回答特征
    low_wm_indicator: str = ""    # 低工作记忆的回答特征
    high_wm_indicator: str = ""   # 高工作记忆的回答特征


# 6道诊断题（5-10分钟完成）
DIAGNOSTIC_QUESTIONS: list[AssessmentQuestion] = [
    AssessmentQuestion(
        id="conservation",
        question="一个长方形，如果把它的长缩短2厘米，宽增加2厘米，面积会变吗？说说你的想法～",
        measures=["concrete_operational", "abstract_thinking"],
        order=1,
        concrete_indicator="需要画图或举具体数字才能判断",
        formal_indicator="能直接用代数推理：(a-2)(b+2) = ab+2a-2b-4 ≠ ab",
    ),
    AssessmentQuestion(
        id="hypothetical",
        question="如果一个数的平方是负数，你觉得这个数可能是什么样的？",
        measures=["abstract_thinking", "hypothetical_reasoning"],
        order=2,
        concrete_indicator="觉得不可能，因为任何数平方都是正的",
        formal_indicator="能想到'可能存在一种新的数'或'在实数范围内不可能'",
    ),
    AssessmentQuestion(
        id="working_memory",
        question="心里算一下：25 × 16，不用写下来，然后告诉我你是怎么一步步算的～",
        measures=["working_memory", "step_decomposition"],
        order=3,
        low_wm_indicator="需要写下来、频繁说'等一下我想想'、步骤混乱",
        high_wm_indicator="能在脑中完成并清晰描述步骤（如拆成25×4×4）",
    ),
    AssessmentQuestion(
        id="metacognition",
        question="做数学题的时候，你怎么知道自己是真的懂了，还是只是记住了答案？",
        measures=["metacognition", "self_monitoring"],
        order=4,
        concrete_indicator="说不清楚，或'做对了就是懂了'、'记住了就会了'",
        formal_indicator="能说出'换一道类似的题我还能做'或'我能给别人讲明白'或'我知道为什么这样做'",
    ),
    AssessmentQuestion(
        id="flexibility",
        question="125 × 8 这道题，你能想到几种不同的算方法？随便说说看～",
        measures=["executive_function", "cognitive_flexibility"],
        order=5,
        concrete_indicator="只会一种方法（直接乘）",
        formal_indicator="能想到拆分（125×8=100×8+25×8）、凑整（125×8=1000）等多种方法",
    ),
    AssessmentQuestion(
        id="anxiety_probe",
        question="下次数学考试的时候，你一般是什么感觉？",
        measures=["math_anxiety"],
        order=6,
        concrete_indicator="'有点紧张'/'还好吧'/'挺期待的'",
        formal_indicator="能具体描述焦虑场景或应对策略",
    ),
]


@dataclass
class AssessmentResult:
    """评估结果：7个维度的初始评分。"""
    cognitive_stage: Literal["concrete", "transitional", "formal"] = "concrete"
    working_memory_capacity: Literal["low", "medium", "high"] = "medium"
    abstract_thinking: float = 0.3
    metacognition_level: float = 0.2
    executive_function: dict[str, float] = field(default_factory=lambda: {
        "inhibition": 0.5,
        "flexibility": 0.4,
    })
    math_anxiety: float = 0.2
    learning_preference: Literal["visual", "verbal", "kinesthetic"] = "visual"
    confidence: float = 0.0  # 评估置信度


def score_answer(question: AssessmentQuestion, answer: str) -> dict[str, float]:
    """根据学生回答评分，返回各维度的增量。

    这是一个基于规则的评分器。LLM 可以在后续版本中替代规则评分。
    """
    ans = answer.strip().lower()
    scores: dict[str, float] = {}

    if question.id == "conservation":
        # 抽象思维
        if any(k in ans for k in ["不会变", "一样", "不变", "相等"]):
            # 猜对了结论但可能不知道为什么
            if any(k in ans for k in ["因为", "所以", "面积", "公式"]):
                scores["abstract_thinking"] = 0.15  # 能推理
            else:
                scores["abstract_thinking"] = 0.05  # 猜对
        elif any(k in ans for k in ["会变", "变了", "变大", "变小"]):
            scores["abstract_thinking"] = -0.05  # 答错
        # 如果提到画图/举例子 → 偏具体运算
        if any(k in ans for k in ["画", "图", "比如", "假设长是"]):
            scores["concrete_hint"] = 0.1

    elif question.id == "hypothetical":
        if any(k in ans for k in ["不可能", "没有", "不存在", "都是正"]):
            scores["abstract_thinking"] = 0.0  # 具体运算水平
        elif any(k in ans for k in ["新的数", "虚数", "不存在于实数", "可能有"]):
            scores["abstract_thinking"] = 0.2  # 形式运算萌芽
        elif any(k in ans for k in ["不知道", "没想过"]):
            scores["abstract_thinking"] = -0.02

    elif question.id == "working_memory":
        # 步骤清晰度
        step_indicators = ["先", "然后", "接着", "第一步", "第二步", "拆"]
        step_count = sum(1 for k in step_indicators if k in ans)
        if step_count >= 3:
            scores["working_memory"] = 0.15
        elif step_count >= 1:
            scores["working_memory"] = 0.05
        else:
            scores["working_memory"] = -0.03
        # 答案正确性（25×16=400）
        if "400" in ans:
            scores["working_memory"] += 0.05

    elif question.id == "metacognition":
        if any(k in ans for k in ["换一道", "类似的", "讲给别人", "讲明白", "为什么", "理解原理"]):
            scores["metacognition"] = 0.2
        elif any(k in ans for k in ["做对了", "记住了", "会了"]):
            scores["metacognition"] = 0.0
        elif any(k in ans for k in ["不知道", "没想过"]):
            scores["metacognition"] = -0.02

    elif question.id == "flexibility":
        methods = 0
        if any(k in ans for k in ["直接乘", "列竖式"]):
            methods += 1
        if any(k in ans for k in ["拆", "分开", "125×4×", "125×2×"]):
            methods += 1
        if any(k in ans for k in ["凑整", "1000", "125×8=1000"]):
            methods += 1
        if any(k in ans for k in ["简便", "交换", "分配律"]):
            methods += 1
        if methods >= 3:
            scores["flexibility"] = 0.15
        elif methods >= 2:
            scores["flexibility"] = 0.08
        else:
            scores["flexibility"] = 0.0

    elif question.id == "anxiety_probe":
        if any(k in ans for k in ["害怕", "紧张", "焦虑", "担心", "不想考", "好难"]):
            scores["math_anxiety"] = 0.15
        elif any(k in ans for k in ["还好", "一般", "正常", "有点"]):
            scores["math_anxiety"] = 0.05
        elif any(k in ans for k in ["期待", "喜欢", "不怕", "有信心"]):
            scores["math_anxiety"] = -0.05

    return scores


def compute_final_result(all_scores: dict[str, list[float]]) -> AssessmentResult:
    """汇总所有题目的评分，生成最终认知画像。"""
    result = AssessmentResult()

    # 抽象思维
    abs_scores = all_scores.get("abstract_thinking", [])
    if abs_scores:
        avg = sum(abs_scores) / len(abs_scores)
        result.abstract_thinking = max(0.1, min(1.0, 0.3 + avg))

    # 认知阶段推断
    concrete_hint = sum(all_scores.get("concrete_hint", []))
    if result.abstract_thinking >= 0.65:
        result.cognitive_stage = "formal"
    elif result.abstract_thinking >= 0.4 or concrete_hint > 0:
        result.cognitive_stage = "transitional"
    else:
        result.cognitive_stage = "concrete"

    # 工作记忆
    wm_scores = all_scores.get("working_memory", [])
    if wm_scores:
        avg_wm = sum(wm_scores) / len(wm_scores)
        if avg_wm >= 0.12:
            result.working_memory_capacity = "high"
        elif avg_wm >= 0.04:
            result.working_memory_capacity = "medium"
        else:
            result.working_memory_capacity = "low"

    # 元认知
    meta_scores = all_scores.get("metacognition", [])
    if meta_scores:
        avg_meta = sum(meta_scores) / len(meta_scores)
        result.metacognition_level = max(0.1, min(1.0, 0.2 + avg_meta * 2))

    # 执行功能
    flex_scores = all_scores.get("flexibility", [])
    if flex_scores:
        avg_flex = sum(flex_scores) / len(flex_scores)
        result.executive_function["flexibility"] = max(0.2, min(1.0, 0.4 + avg_flex * 2))

    # 数学焦虑
    anx_scores = all_scores.get("math_anxiety", [])
    if anx_scores:
        avg_anx = sum(anx_scores) / len(anx_scores)
        result.math_anxiety = max(0.0, min(1.0, 0.2 + avg_anx * 2))

    # 置信度（基于回答完整度）
    total_questions = len(DIAGNOSTIC_QUESTIONS)
    answered = len([v for v in all_scores.values() if v])
    result.confidence = min(0.8, answered / total_questions * 0.8)

    return result


def get_next_question(answered_ids: list[str]) -> AssessmentQuestion | None:
    """获取下一道未回答的诊断题。"""
    for q in DIAGNOSTIC_QUESTIONS:
        if q.id not in answered_ids:
            return q
    return None


def get_assessment_summary(result: AssessmentResult) -> str:
    """生成评估结果的自然语言摘要（给小圆告诉学生用）。"""
    stage_map = {
        "concrete": "喜欢用画图和具体例子来理解",
        "transitional": "正在从具体思维向抽象思维过渡",
        "formal": "抽象思维能力较强，能理解符号推理",
    }
    wm_map = {
        "low": "一次消化1-2步比较舒服",
        "medium": "一次能跟上2-3步",
        "high": "一次能处理较多信息",
    }
    parts = [
        f"认知风格：{stage_map.get(result.cognitive_stage, '')}",
        f"信息处理：{wm_map.get(result.working_memory_capacity, '')}",
    ]
    if result.math_anxiety >= 0.5:
        parts.append("数学焦虑偏高，需要多鼓励少施压")
    if result.metacognition_level >= 0.5:
        parts.append("元认知能力不错，能主动反思")
    return "；".join(parts)
