"""10大核心数学思维模型的结构化知识库。

每个思维模型包含：核心思想、适用场景、使用步骤、教学引导语、常见错误。
persona.py 根据当前知识点和学生掌握度，动态注入最相关的思维模型引导。
"""

from dataclasses import dataclass, field


@dataclass
class ThinkingModel:
    id: str
    name: str
    core_idea: str
    apply_steps: list[str] = field(default_factory=list)
    teaching_hints: list[str] = field(default_factory=list)
    common_mistakes: list[str] = field(default_factory=list)
    typical_topics: list[str] = field(default_factory=list)


THINKING_MODELS: dict[str, ThinkingModel] = {
    "reverse": ThinkingModel(
        id="reverse",
        name="逆向思维",
        core_idea="从问题要求的结果出发，倒推需要什么条件",
        apply_steps=[
            "明确要求什么",
            "要得到这个结果需要先知道什么",
            "一步步倒推到已知条件",
        ],
        teaching_hints=[
            "题目要我们求什么？要求出这个，需要先知道什么？",
            "我们从结果倒着想，要得到这个答案，上一步应该是什么？",
            "如果答案是X，那它必须满足什么条件？",
        ],
        common_mistakes=["倒推到一半跳步", "倒推路径不唯一时没考虑所有可能"],
        typical_topics=["一元一次方程", "一元一次方程应用", "几何证明"],
    ),
    "visualization": ThinkingModel(
        id="visualization",
        name="图形化思维",
        core_idea="把抽象的数量关系转化为图形，或用代数方法解决几何问题",
        apply_steps=[
            "判断能否画图",
            "画图标注已知条件",
            "从图形中找关系",
            "转回代数表达",
        ],
        teaching_hints=[
            "这道题我们画个图看看？把已知的标上去",
            "如果把这个式子画成图，会长什么样？",
            "图上哪一段代表我们要求的量？",
        ],
        common_mistakes=["图画得不标准导致误判", "画图时漏标条件", "只画图不转回代数"],
        typical_topics=["数轴", "一元一次方程应用", "线段与角"],
    ),
    "decomposition": ThinkingModel(
        id="decomposition",
        name="问题拆分",
        core_idea="把复杂问题拆成若干简单子问题，逐个解决",
        apply_steps=[
            "通读全题",
            "列出所有已知条件和要求",
            "判断可以分成几步",
            "第一步解决什么",
            "逐步推进",
        ],
        teaching_hints=[
            "这道题看起来有点吓人，我们把它拆成小步。第一步先做什么？",
            "题目里有几个条件？我们一个一个来处理",
            "先不管最后答案，我们先把能求的求出来",
        ],
        common_mistakes=["拆分时跳步", "子问题之间的关系没理清", "拆得太碎反而混乱"],
        typical_topics=["有理数混合运算", "一元一次方程应用"],
    ),
    "analogy": ThinkingModel(
        id="analogy",
        name="类比思维",
        core_idea="找到当前问题与已解决问题的相似结构，迁移解法",
        apply_steps=[
            "这道题和之前做过的哪道题像？",
            "相同的结构是什么？",
            "不同的地方在哪？",
            "能否套用类似方法？",
        ],
        teaching_hints=[
            "这道题让你想起之前做过的哪道题？它们哪里像？",
            "我们之前做过一道类似的，还记得是怎么做的吗？",
            "这道题和那道题有什么不一样的地方？方法需要调整吗？",
        ],
        common_mistakes=["只看表面相似不看结构", "生搬硬套不调整", "忽略关键差异"],
        typical_topics=["一元一次方程", "二元一次方程组"],
    ),
    "transformation": ThinkingModel(
        id="transformation",
        name="转化思维",
        core_idea="把未知问题转化为已知问题，把复杂形式转化为简单形式",
        apply_steps=[
            "这个问题能不能变成我会的形式？",
            "做什么变换可以简化？",
            "转化后解决",
            "转化回原问题",
        ],
        teaching_hints=[
            "这个形式看起来复杂，我们能不能做个变换让它简单一点？",
            "如果把它变成我们学过的形式，会是什么样？",
            "这一步我们做了什么变换？为什么可以这样变？",
        ],
        common_mistakes=["变换后忘记变回来", "变换的等价性没验证", "过度变换反而复杂"],
        typical_topics=["一元一次方程", "二元一次方程组", "因式分解"],
    ),
    "case_analysis": ThinkingModel(
        id="case_analysis",
        name="分类讨论",
        core_idea="当问题有多种可能情况时，分情况讨论，确保不重复不遗漏",
        apply_steps=[
            "有几种可能情况？",
            "分类标准是什么？",
            "每种情况分别解决",
            "检查是否覆盖所有情况",
        ],
        teaching_hints=[
            "这道题有没有可能分几种情况？我们先想想有哪几种",
            "绝对值里面的数可能是正的也可能是负的，我们分开讨论好不好？",
            "分完了吗？有没有漏掉什么情况？有没有重复的？",
        ],
        common_mistakes=["漏掉某种情况", "分类标准不统一导致重复", "分完后没有综合结论"],
        typical_topics=["有理数乘法", "一元一次方程"],
    ),
    "extreme": ThinkingModel(
        id="extreme",
        name="极端思维",
        core_idea="考虑极端情况来快速判断或验证",
        apply_steps=[
            "取一个特殊值或极端情况",
            "在这个情况下结果是什么？",
            "能否推广到一般情况？",
        ],
        teaching_hints=[
            "我们试试取个特殊值，比如让x=0，看看会怎么样？",
            "如果这个数特别大或特别小，会发生什么？",
            "我们用边界情况检验一下答案对不对",
        ],
        common_mistakes=["把特殊情况当成一般结论", "特殊值选得不够极端", "用极端思维替代严格证明"],
        typical_topics=["有理数乘方", "一元一次方程"],
    ),
    "holistic": ThinkingModel(
        id="holistic",
        name="整体思维",
        core_idea="不从局部入手，把某个复杂部分看作一个整体来处理",
        apply_steps=[
            "有没有一个复杂的部分反复出现？",
            "把它看作一个整体",
            "先求整体的值",
            "再求局部",
        ],
        teaching_hints=[
            "这个式子反复出现，我们把它看作一个整体，看看会不会简单点",
            "不用急着把每个量都求出来，我们看看能不能整体代入",
            "如果把这两个方程加在一起或减一减，会怎么样？",
        ],
        common_mistakes=["看不出哪个部分可以看作整体", "整体求值后忘记求局部"],
        typical_topics=["二元一次方程组", "因式分解"],
    ),
    "modeling": ThinkingModel(
        id="modeling",
        name="建模思维",
        core_idea="把实际问题中的数量关系抽象为数学模型",
        apply_steps=[
            "问题中有哪些量？",
            "量之间有什么关系？",
            "用什么数学模型表达？",
            "解模型",
            "检验是否符合实际",
        ],
        teaching_hints=[
            "这道题在说一件什么事？里面有哪些量？它们之间是什么关系？",
            "我们能不能用方程把这个关系写出来？",
            "解出来了，这个答案符合实际情况吗？",
        ],
        common_mistakes=["找错等量关系", "单位不统一", "解完不检验是否符合实际"],
        typical_topics=["一元一次方程应用", "二元一次方程组"],
    ),
    "verification": ThinkingModel(
        id="verification",
        name="检验思维",
        core_idea="做完题后主动检验答案是否正确、合理、完整",
        apply_steps=[
            "代入验证",
            "估算是否合理",
            "检查是否有遗漏情况",
            "反思用了什么方法",
        ],
        teaching_hints=[
            "做完了？我们来检验一下。把答案代回去看看对不对？",
            "这个结果合理吗？估算一下大概应该在什么范围？",
            "再想想有没有漏掉什么情况？用了什么方法？下次遇到类似题还能用吗？",
        ],
        common_mistakes=["做完不检查", "只检查计算不检查思路", "检验方法单一"],
        typical_topics=["一元一次方程", "有理数混合运算"],
    ),
}


def get_model(model_id: str) -> ThinkingModel | None:
    return THINKING_MODELS.get(model_id)


def models_for_topic(topic_id: str) -> list[ThinkingModel]:
    """返回适用于某知识点的所有思维模型。"""
    return [m for m in THINKING_MODELS.values() if topic_id in m.typical_topics]


# ===== C2：确定性思维模型触发规则 =====
# 错误类型 → 推荐的思维模型（确定性映射）
ERROR_TYPE_MODEL_MAP: dict[str, list[str]] = {
    "careless": ["verification"],        # 粗心 → 检验思维
    "concept": ["visualization", "analogy"],  # 概念不清 → 图形化/类比
    "formula": ["transformation"],       # 公式用错 → 转化思维
    "steps": ["decomposition"],          # 步骤混乱 → 问题拆分
    "reading": ["modeling"],             # 审题不清 → 建模思维
}

# 认知偏好 → 优先思维模型（学生画像学习偏好）
PREFERENCE_MODEL_MAP: dict[str, list[str]] = {
    "visual": ["visualization"],
    "verbal": ["analogy"],
    "kinesthetic": ["modeling"],
    "logical": ["decomposition", "verification"],
}

# 状态 → 默认推荐思维模型
STATE_MODEL_MAP: dict[str, list[str]] = {
    "BLIND_SPOT": ["modeling", "decomposition"],
    "CORE_DERIVE": ["transformation", "visualization"],
    "EXAMPLE_CHECK": ["case_analysis", "verification"],
    "ERROR_REVIEW": ["verification", "reverse"],
    "OPTIONAL_VARIANT": ["analogy", "holistic"],
    "QUICK_REVIEW": ["verification"],
    "THINKING_TRAINING": ["reverse", "visualization", "analogy"],
}


def select_thinking_model(
    topic_id: str,
    *,
    state: str | None = None,
    error_type: str | None = None,
    thinking_model_mastery: dict[str, float] | None = None,
    learning_preference: str | None = None,
    consecutive_wrong: int = 0,
) -> str | None:
    """确定性选择要引导的思维模型（C2）。

    规则（按优先级）：
    1. 错误类型映射（学生刚出错时，按错误类型选修复模型）
    2. 认知偏好映射（学生画像稳定偏好）
    3. 当前教学状态映射
    4. 知识点推荐模型中的最弱项（现有启发式兜底）
    """
    mastery = thinking_model_mastery or {}

    # 1. 错误类型驱动（出错时优先级最高——针对当下卡点）
    if error_type:
        candidates = ERROR_TYPE_MODEL_MAP.get(error_type)
        if candidates:
            return _pick_weakest(candidates, mastery)

    # 2. 连续错 → 换策略（当前模型不管用，换一个互补的）
    if consecutive_wrong >= 2:
        candidates = ["visualization", "analogy", "decomposition"]
        return _pick_weakest(candidates, mastery)

    # 3. 认知偏好驱动
    if learning_preference:
        candidates = PREFERENCE_MODEL_MAP.get(learning_preference)
        if candidates:
            return _pick_weakest(candidates, mastery)

    # 4. 当前教学状态驱动
    if state:
        candidates = STATE_MODEL_MAP.get(state)
        if candidates:
            return _pick_weakest(candidates, mastery)

    # 5. 兜底：知识点推荐模型中最弱项
    # 优先用 syllabus 节点声明的 common_thinking_models，其次 typical_topics 推断
    from backend.knowledge import syllabus
    node = syllabus.get_node(topic_id)
    ids = list(node.common_thinking_models) if node and node.common_thinking_models else [m.id for m in models_for_topic(topic_id)]
    if ids:
        return _pick_weakest(ids, mastery)

    return None


def _pick_weakest(candidates: list[str], mastery: dict[str, float]) -> str | None:
    """从候选中选掌握度最低者（最需要练习的模型）。"""
    valid = [c for c in candidates if c in THINKING_MODELS]
    if not valid:
        return None
    return min(valid, key=lambda mid: mastery.get(mid, 0.0))
