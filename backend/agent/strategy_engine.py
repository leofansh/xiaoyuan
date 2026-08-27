"""教学策略引擎（架构优化 C1）。

显式定义教学策略（触发条件、执行步骤、适用范围、预期效果），
策略选择由确定性规则决定，LLM 只负责"执行策略"（生成具体引导语言）。
"""

from typing import Any, Optional

from pydantic import BaseModel


class TeachingStrategy(BaseModel):
    id: str
    name: str
    description: str
    trigger_conditions: list[str] = []      # 触发条件（规则描述）
    steps: list[str] = []                   # 执行步骤
    cognitive_stages: list[str] = []        # 适用认知阶段
    problem_types: list[str] = []           # 适用题型（"all" 表示通用）
    priority: int = 0                       # 优先级（数字越大越优先）
    expected_outcome: str = ""


# 策略库：6 个核心策略
STRATEGIES: dict[str, TeachingStrategy] = {
    "scaffold_questioning": TeachingStrategy(
        id="scaffold_questioning",
        name="脚手架提问法",
        description="通过递进式提问引导学生自己建构知识，不直接给答案。",
        trigger_conditions=[
            "学生说'不会''不懂'",
            "概念掌握度 < 0.5",
            "状态为 CORE_DERIVE",
        ],
        steps=[
            "问：题目里已知什么？要求什么？",
            "问：已知和要求之间有什么关系？",
            "问：我们学过的哪个知识点可以用在这里？",
            "引导学生自己写出第一步",
            "确认学生理解后再推进",
        ],
        cognitive_stages=["concrete", "transitional", "formal"],
        problem_types=["all"],
        priority=10,
        expected_outcome="学生通过自己思考得出答案，概念理解加深",
    ),
    "analogy_explanation": TeachingStrategy(
        id="analogy_explanation",
        name="类比讲解法",
        description="用生活中的熟悉事物类比抽象数学概念，降低认知负荷。",
        trigger_conditions=[
            "学生连续 2 次答错",
            "抽象思维 < 0.4",
            "概念涉及抽象关系（方程、函数、比例）",
        ],
        steps=[
            "识别概念的核心关系",
            "选择学生熟悉的生活类比（如方程=天平、分数=披萨）",
            "用类比解释概念",
            "引导学生把类比映射回数学",
            "出一道简单题验证理解",
        ],
        cognitive_stages=["concrete", "transitional"],
        problem_types=["equation", "fraction", "ratio", "function"],
        priority=8,
        expected_outcome="学生通过类比建立直觉理解",
    ),
    "visualization_guide": TeachingStrategy(
        id="visualization_guide",
        name="图形化引导法",
        description="引导学生画图、用图形化思维理解问题。",
        trigger_conditions=[
            "题目涉及几何、行程、工程问题",
            "学习偏好为 visual",
            "学生说'想象不出来'",
        ],
        steps=[
            "问：能不能用图表示题目中的关系？",
            "引导学生画线段图/示意图",
            "在图上标注已知量和未知量",
            "从图中找出等量关系",
            "列式求解",
        ],
        cognitive_stages=["concrete", "transitional", "formal"],
        problem_types=["geometry", "motion", "engineering", "ratio"],
        priority=7,
        expected_outcome="学生通过图形化建立问题表征",
    ),
    "decomposition": TeachingStrategy(
        id="decomposition",
        name="问题拆分法",
        description="把复杂问题拆成小步骤，一步一验证。",
        trigger_conditions=[
            "题目步骤 > 3 步",
            "工作记忆容量 = low",
            "学生说'太复杂了''无从下手'",
        ],
        steps=[
            "和学生一起把题目拆成 2-3 个小问题",
            "解决第一个小问题，验证",
            "解决第二个小问题，验证",
            "合并结果",
            "回顾整体思路",
        ],
        cognitive_stages=["concrete", "transitional"],
        problem_types=["word_problem", "multi_step"],
        priority=6,
        expected_outcome="学生通过拆分降低认知负荷，逐步解决复杂问题",
    ),
    "error_root_cause": TeachingStrategy(
        id="error_root_cause",
        name="错误根因分析法",
        description="不简单说'错了'，而是分析错误根因，针对性修复。",
        trigger_conditions=[
            "学生犯错",
            "错误模式可识别（查错误模式库）",
            "同一错误出现 >= 2 次",
        ],
        steps=[
            "指出具体错误位置（不是'全错了'）",
            "分析错误类型（查错误模式库）",
            "解释根因为什么导致这个错误",
            "用针对性练习修复",
            "出一道同类题验证修复效果",
        ],
        cognitive_stages=["concrete", "transitional", "formal"],
        problem_types=["all"],
        priority=9,
        expected_outcome="学生理解错误根因，不再犯同类错误",
    ),
    "positive_reframing": TeachingStrategy(
        id="positive_reframing",
        name="归因重构法",
        description="当学生自我否定时，把归因从'能力'转向'策略/努力'。",
        trigger_conditions=[
            "学生说'我太笨了''我学不会'",
            "数学焦虑 > 0.6",
            "连续错误 >= 2 次",
        ],
        steps=[
            "立即否定'笨'的归因：'不是笨，是这个积木还没搭稳'",
            "把问题具体化：'是哪一步觉得难？'",
            "回顾之前的成功：'你之前XX都学会了，这个也可以'",
            "换一个更简单的切入点",
            "小步成功后及时肯定",
        ],
        cognitive_stages=["concrete", "transitional", "formal"],
        problem_types=["all"],
        priority=10,
        expected_outcome="学生从自我否定转向成长心态",
    ),
    "variant_practice": TeachingStrategy(
        id="variant_practice",
        name="变式提升法",
        description="学生掌握基础后，通过变式题深化理解和迁移能力。",
        trigger_conditions=[
            "基础题连续 2 次正确",
            "掌握度 >= 0.7",
            "状态为 OPTIONAL_VARIANT",
        ],
        steps=[
            "改变题目中的数字（巩固计算）",
            "改变题目中的情境（巩固概念）",
            "改变题目中的问法（巩固理解）",
            "逆向出题（已知答案求条件）",
            "总结这类题的通用解法",
        ],
        cognitive_stages=["transitional", "formal"],
        problem_types=["all"],
        priority=5,
        expected_outcome="学生从'会做一道题'到'会做一类题'",
    ),
}

# 中文题型关键词 → 题型类别映射（从学生消息/知识点推断题型）
_PROBLEM_TYPE_KEYWORDS: dict[str, list[str]] = {
    "equation": ["方程", "解方程", "等量关系"],
    "fraction": ["分数", "通分", "约分"],
    "ratio": ["比例", "比", "百分比", "百分数"],
    "function": ["函数", "一次函数"],
    "geometry": ["几何", "角度", "面积", "周长", "三角形", "圆形", "线段"],
    "motion": ["速度", "相遇", "追及", "行程", "路程"],
    "engineering": ["工程", "合作", "单独做"],
    "word_problem": ["应用题", "买了", "一共", "还剩", "单价"],
    "multi_step": ["混合运算", "综合题"],
}


def infer_problem_type(topic_name: str = "", user_message: str = "") -> str:
    """从知识点名称或学生消息推断题型（未匹配返回空串）。"""
    text = (topic_name or "") + " " + (user_message or "")
    for ptype, kws in _PROBLEM_TYPE_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return ptype
    return ""


def select_strategy(
    student,
    problem_type: str = "",
    context: Optional[dict[str, Any]] = None,
) -> Optional[TeachingStrategy]:
    """根据学生状态和题目类型选择教学策略（确定性规则）。

    context 支持：
    - consecutive_wrong / consecutive_correct
    - mastery（当前知识点掌握度）
    - step_count
    - self_doubt_expression（是否自我否定）

    Returns: 匹配度最高的策略，或 None（默认策略）。
    """
    context = context or {}
    candidates: list[tuple[float, TeachingStrategy]] = []
    for sid, strategy in STRATEGIES.items():
        score = _match_strategy(student, strategy, problem_type, context)
        if score > 0:
            candidates.append((score, strategy))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x[0], x[1].priority), reverse=True)
    return candidates[0][1]


def _match_strategy(student, strategy: TeachingStrategy, problem_type: str, context: dict) -> float:
    """计算策略匹配度（0-1）。"""
    score = 0.0
    cp = student.cognitive_profile

    # 认知阶段匹配
    if cp.cognitive_stage in strategy.cognitive_stages:
        score += 0.3
    elif "all" in strategy.cognitive_stages:
        score += 0.2

    # 题型匹配
    if problem_type and (problem_type in strategy.problem_types or "all" in strategy.problem_types):
        score += 0.3

    # 触发条件匹配
    consecutive_wrong = context.get("consecutive_wrong", 0)
    consecutive_correct = context.get("consecutive_correct", 0)
    mastery = context.get("mastery", 0.5)
    step_count = context.get("step_count", 1)

    if strategy.id == "scaffold_questioning" and mastery < 0.5 and consecutive_wrong < 2:
        score += 0.4
    if strategy.id == "analogy_explanation" and consecutive_wrong >= 2 and cp.abstract_thinking < 0.4:
        score += 0.4
    if strategy.id == "error_root_cause" and consecutive_wrong >= 1 and cp.abstract_thinking >= 0.4:
        score += 0.4
    if strategy.id == "positive_reframing" and (
        context.get("self_doubt_expression") or cp.math_anxiety > 0.6
    ):
        score += 0.4
    if strategy.id == "variant_practice" and consecutive_correct >= 2 and mastery >= 0.7:
        score += 0.4
    if strategy.id == "decomposition" and step_count > 3:
        score += 0.4

    return min(score, 1.0)


def strategy_instruction(strategy: TeachingStrategy) -> str:
    """把策略转成注入 prompt 的指令文本。"""
    lines = [f"当前教学策略：{strategy.name}（{strategy.description}）", "执行步骤："]
    for i, step in enumerate(strategy.steps, 1):
        lines.append(f"{i}. {step}")
    return "\n".join(lines)
