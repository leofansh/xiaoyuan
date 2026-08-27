"""错误模式库与漏洞分类体系（架构优化 B2 / E1）。

提供：
- GAP_CATEGORIES：漏洞精细分类（22 种）
- ERROR_PATTERNS：从学生表述/错误行为识别具体错误模式的规则
- classify_gap：根据 eval 信息 + 学生消息自动分类漏洞
"""

from typing import Any

# ===== 漏洞分类体系 =====
GAP_CATEGORIES: dict[str, str] = {
    # 计算类
    "calc_carry": "进位错误",
    "calc_borrow": "借位错误",
    "calc_sign": "符号错误",
    "calc_multiplication": "乘法口诀错误",
    "calc_copy": "抄错数字",
    "calc_decimal": "小数点位错误",
    "calc_fraction": "分数运算错误",
    # 概念类
    "concept_prerequisite": "前置知识缺失",
    "concept_misunderstanding": "概念误解",
    "concept_formula": "公式记错",
    "concept_condition": "适用条件不清",
    "concept_definition": "定义不清",
    # 审题类
    "read_miss_condition": "漏看条件",
    "read_misunderstand": "理解偏差",
    "read_unit": "单位错误",
    "read_keyword": "关键词误读",
    # 思维类
    "think_rigid": "思维定式",
    "think_no_reverse": "缺乏逆向思维",
    "think_no_decomposition": "不会拆分",
    "think_no_modeling": "不会建模",
    # 其他
    "careless_general": "一般性粗心",
    "unknown": "未知",
}

# 旧类型 → 新分类的映射（B2 数据迁移）
LEGACY_TYPE_TO_CATEGORY: dict[str, str] = {
    "concept": "concept_misunderstanding",
    "careless": "careless_general",
}


def category_name(category: str) -> str:
    """返回分类的中文名，未知返回 '未知'。"""
    return GAP_CATEGORIES.get(category, "未知")


# ===== 错误模式库（E1：从表述识别错误模式）=====
# 每个模式：keywords 触发词 / repair_strategy 修复策略 / category 对应分类
ERROR_PATTERNS: list[dict[str, Any]] = [
    {
        "category": "calc_sign",
        "name": "符号错误",
        "keywords": ["负号", "符号", "正负", "带错了", "减号", "变号"],
        "repair_strategy": "用「括号展开法」重新演示去括号，强调变号规则，出 3 道同类题巩固。",
    },
    {
        "category": "calc_decimal",
        "name": "小数点错误",
        "keywords": ["小数点", "点错了", "几位小数", "小数点位置"],
        "repair_strategy": "用「数位对齐」方法，把小数乘除转化为整数运算再定位小数点。",
    },
    {
        "category": "calc_fraction",
        "name": "分数运算错误",
        "keywords": ["通分", "约分", "分母", "分子", "分数加减", "假分数"],
        "repair_strategy": "回退到「同分母 → 通分 → 异分母」三步法，用直观图演示分数相加。",
    },
    {
        "category": "calc_copy",
        "name": "抄错数字",
        "keywords": ["抄错", "看错", "写错了", "看串行"],
        "repair_strategy": "训练「抄题三步」：读题 → 复述 → 落笔，并要求做完回看一遍原题。",
    },
    {
        "category": "calc_multiplication",
        "name": "乘法口诀错误",
        "keywords": ["口诀", "乘法", "九九", "背错"],
        "repair_strategy": "针对记错的乘法口诀做专项记忆，用口诀表+口算游戏强化。",
    },
    {
        "category": "concept_prerequisite",
        "name": "前置知识缺失",
        "keywords": ["没学过", "忘了", "不记得", "没印象", "没讲过"],
        "repair_strategy": "找到前置知识节点，先补前置，再回到当前知识点。",
    },
    {
        "category": "concept_misunderstanding",
        "name": "概念误解",
        "keywords": ["以为", "觉得是", "不懂概念", "理解错", "以为是这样"],
        "repair_strategy": "用反例和类比澄清概念边界，让学生自己说出概念定义。",
    },
    {
        "category": "concept_formula",
        "name": "公式记错",
        "keywords": ["公式", "记错公式", "套错公式", "用错公式"],
        "repair_strategy": "用「公式推导」而非死记：引导学生自己推一遍公式，理解来源。",
    },
    {
        "category": "read_miss_condition",
        "name": "漏看条件",
        "keywords": ["漏", "没看到", "没注意", "忽略了", "条件没看见"],
        "repair_strategy": "训练「圈画关键词」：读题时圈出数字和条件词，做完核对。",
    },
    {
        "category": "read_misunderstand",
        "name": "理解偏差",
        "keywords": ["没读懂", "不理解题意", "没看懂题目", "题意"],
        "repair_strategy": "让学生用自己的话复述题目，找出理解偏差点，再翻译成数学语言。",
    },
    {
        "category": "read_keyword",
        "name": "关键词误读",
        "keywords": ["关键词", "以为是要", "理解成"],
        "repair_strategy": "辨析「至少/至多/增加了/增加到」等易混关键词的数学含义。",
    },
    {
        "category": "think_rigid",
        "name": "思维定式",
        "keywords": ["只会这一种", "想不到别的", "只会套", "只会用这个方法"],
        "repair_strategy": "用「一题多解」训练认知灵活性，鼓励换角度思考。",
    },
    {
        "category": "think_no_decomposition",
        "name": "不会拆分",
        "keywords": ["太复杂", "无从下手", "不知道从哪", "没头绪", "拆不开"],
        "repair_strategy": "用「问题拆分法」：把题目拆成 2-3 个小问题，逐步解决。",
    },
    {
        "category": "think_no_modeling",
        "name": "不会建模",
        "keywords": ["不会列式", "不会设", "列不出", "不知道设什么"],
        "repair_strategy": "引导「找等量关系」：先找题目里的数量关系，再设未知数列方程。",
    },
    {
        "category": "careless_general",
        "name": "一般性粗心",
        "keywords": ["粗心", "马虎", "不小心", "算错没检查"],
        "repair_strategy": "培养「检验习惯」：做完代入验算、估算合理性、回看单位。",
    },
]


def classify_gap(
    topic_id: str,
    error_type: str = "",
    evidence: str = "",
    error_pattern: str = "",
) -> str:
    """自动分类漏洞。

    优先级：
    1. 显式 error_pattern（LLM 评估给的）若在 GAP_CATEGORIES 中，直接采用
    2. 从 evidence 中匹配错误模式库关键词
    3. 由旧 error_type 映射（concept→concept_misunderstanding, careless→careless_general）
    4. unknown
    """
    if error_pattern and error_pattern in GAP_CATEGORIES:
        return error_pattern

    if evidence:
        for pattern in ERROR_PATTERNS:
            if any(kw in evidence for kw in pattern["keywords"]):
                return pattern["category"]

    return LEGACY_TYPE_TO_CATEGORY.get(error_type, "unknown")


def repair_strategy_for(category: str, evidence: str = "") -> str:
    """返回分类对应的修复策略描述。"""
    if category in GAP_CATEGORIES:
        for pattern in ERROR_PATTERNS:
            if pattern["category"] == category:
                return pattern["repair_strategy"]
    if evidence:
        for pattern in ERROR_PATTERNS:
            if any(kw in evidence for kw in pattern["keywords"]):
                return pattern["repair_strategy"]
    return "先通过针对性提问定位具体错误，再回到前置知识点补基础，最后用同类题验证。"


# ===== E1：结构化错误模式库（12 种核心，五大类）=====
from pydantic import BaseModel, Field  # noqa: E402


class ErrorPattern(BaseModel):
    """结构化错误模式。"""
    id: str
    name: str
    category: str                # calc / concept / read / think / careless
    description: str
    examples: list[str] = Field(default_factory=list)
    root_cause: str = ""
    repair_strategy: str = ""
    detection_keywords: list[str] = Field(default_factory=list)
    related_topics: list[str] = Field(default_factory=list)


ERROR_PATTERN_LIBRARY: dict[str, ErrorPattern] = {
    "calc_carry_addition": ErrorPattern(
        id="calc_carry_addition", name="加法进位错误", category="calc",
        description="多位数加法个位相加超过10忘记进位。",
        examples=["28+47=65（正确75）", "56+38=84（正确94）"],
        root_cause="进位概念不熟练，只关注个位相加结果忽略进位。",
        repair_strategy="1. 进位标记训练（进位位置写小1）；2. 竖式分步每步确认进位；3. 熟练后增加位数。",
        detection_keywords=["进位", "加错了", "个位"],
        related_topics=["加法", "竖式计算"],
    ),
    "calc_borrow_subtraction": ErrorPattern(
        id="calc_borrow_subtraction", name="减法借位错误", category="calc",
        description="多位数减法个位不够减忘借位，或借位后十位忘减1。",
        examples=["52-18=46（正确34）", "70-25=55（正确45）"],
        root_cause="借位概念不理解，或借位后忘记更新高位数字。",
        repair_strategy="1. 用实物（小棒）演示借位；2. 借位标记训练（被借位数字打点）；3. 借位后立即更新高位。",
        detection_keywords=["借位", "减错了", "不够减"],
        related_topics=["减法", "竖式计算"],
    ),
    "calc_sign_error": ErrorPattern(
        id="calc_sign_error", name="正负号错误", category="calc",
        description="负数运算符号处理错误，如负负得正忘记、移项变号忘记。",
        examples=["-3+5=-8（正确2）", "2x=-6→x=3（正确-3）"],
        root_cause="负数概念抽象，符号规则记忆不牢，或只关注数字忽略符号。",
        repair_strategy="1. 数轴演示负数运算；2. 符号口诀强化（同号得正异号得负）；3. 每步先定符号再算数值。",
        detection_keywords=["负号", "符号", "变号", "正负"],
        related_topics=["负数", "有理数运算", "方程"],
    ),
    "calc_multiplication_table": ErrorPattern(
        id="calc_multiplication_table", name="乘法口诀错误", category="calc",
        description="乘法口诀不熟练导致计算错误。",
        examples=["7×8=54（正确56）", "6×9=52（正确54）"],
        root_cause="乘法口诀记忆不牢。",
        repair_strategy="1. 找常错口诀针对性练习；2. 用加法验证乘法结果；3. 每日5分钟口诀练习。",
        detection_keywords=["口诀", "乘法", "背错"],
        related_topics=["乘法", "乘法口诀"],
    ),
    "calc_copy_error": ErrorPattern(
        id="calc_copy_error", name="抄错数字", category="careless",
        description="从题目抄写到计算过程时数字抄错。",
        examples=["题目25写成52", "题目3.14写成3.41"],
        root_cause="注意力不集中，读题不仔细。",
        repair_strategy="1. 读题后复述确认数字；2. 抄写后对照检查；3. 手指指题逐字抄写。",
        detection_keywords=["抄错", "看错", "写错", "抄串"],
        related_topics=["所有计算"],
    ),
    "concept_prerequisite_missing": ErrorPattern(
        id="concept_prerequisite_missing", name="前置知识缺失", category="concept",
        description="学习新知识时所需前置知识没掌握。",
        examples=["学解方程不会移项→等式性质没掌握", "学分式不会约分→最大公因数没掌握"],
        root_cause="知识链条断裂，前置没掌握就推进。",
        repair_strategy="1. 诊断具体缺哪个前置；2. 先补前置再回当前；3. 用知识图谱检查依赖链。",
        detection_keywords=["没学过", "忘了", "不记得", "没印象", "没讲过"],
        related_topics=["所有知识点"],
    ),
    "concept_formula_misremember": ErrorPattern(
        id="concept_formula_misremember", name="公式记错", category="concept",
        description="公式记忆错误或遗漏关键部分。",
        examples=["三角形面积=底×高（忘除以2）", "圆面积=2πr（混淆周长面积）"],
        root_cause="死记硬背不理解推导。",
        repair_strategy="1. 推导而非死记；2. 理解每个量含义；3. 用特殊值验证公式。",
        detection_keywords=["公式", "记错", "套错", "用错"],
        related_topics=["几何", "代数公式"],
    ),
    "concept_condition_unclear": ErrorPattern(
        id="concept_condition_unclear", name="适用条件不清", category="concept",
        description="知道方法但不知道何时适用。",
        examples=["所有方程都用求根公式", "非直角三角形用勾股定理"],
        root_cause="只记方法不记前提。",
        repair_strategy="1. 明确'何时用/何时不能用'；2. 对比方法适用场景；3. 做题前先判断方法。",
        detection_keywords=["什么都能用", "都行", "套公式"],
        related_topics=["所有知识点"],
    ),
    "read_miss_condition": ErrorPattern(
        id="read_miss_condition", name="漏看条件", category="read",
        description="读题遗漏关键条件导致列式错误。",
        examples=["'至少'没看到算成'恰好'", "'往返'只算单程"],
        root_cause="读题太快，只关注数字不关注文字。",
        repair_strategy="1. 圈关键词训练（至少/最多/往返）；2. 读题后复述；3. 列已知条件清单。",
        detection_keywords=["漏", "没看到", "没注意", "忽略了"],
        related_topics=["应用题"],
    ),
    "read_unit_error": ErrorPattern(
        id="read_unit_error", name="单位错误", category="read",
        description="单位不统一就计算，或答案单位写错。",
        examples=["km/h和分钟直接相乘", "面积答案写成长度单位"],
        root_cause="单位意识弱，计算前不统一单位。",
        repair_strategy="1. 解题前先统一单位；2. 计算过程带单位；3. 最终检查单位合理性。",
        detection_keywords=["单位", "厘米", "米", "千克", "克"],
        related_topics=["应用题", "几何"],
    ),
    "think_rigid": ErrorPattern(
        id="think_rigid", name="思维定式", category="think",
        description="只会一种方法，不能灵活选择。",
        examples=["所有题都用方程", "所有几何题都用代数方法"],
        root_cause="练习单一，缺一题多解训练。",
        repair_strategy="1. 一题多解训练（2-3种方法）；2. 对比方法优劣；3. 做题前想'有几种方法'。",
        detection_keywords=["只会这一种", "想不到别的", "只会套"],
        related_topics=["所有知识点"],
    ),
    "think_no_decomposition": ErrorPattern(
        id="think_no_decomposition", name="不会拆分问题", category="think",
        description="面对复杂问题无从下手。",
        examples=["多步应用题直接列综合式出错", "复杂图形不会分解"],
        root_cause="工作记忆容量有限，缺拆分训练。",
        repair_strategy="1. 问题拆分思维模型；2. 复杂题拆成2-3个小问题；3. 一步一验证。",
        detection_keywords=["太复杂", "无从下手", "不知道从哪", "没头绪"],
        related_topics=["多步应用题", "复杂几何"],
    ),
}


def get_error_pattern(error_id: str) -> ErrorPattern | None:
    """按 ID 获取错误模式。"""
    return ERROR_PATTERN_LIBRARY.get(error_id)


def get_repair_strategy(error_id: str) -> str | None:
    """获取错误模式的修复策略（E1）。"""
    ep = ERROR_PATTERN_LIBRARY.get(error_id)
    return ep.repair_strategy if ep else None


def detect_error_pattern(evidence: str = "") -> ErrorPattern | None:
    """从学生表述/证据中检测错误模式（E1 自动识别）。"""
    if not evidence:
        return None
    for pattern in ERROR_PATTERN_LIBRARY.values():
        if any(kw in evidence for kw in pattern.detection_keywords):
            return pattern
    return None
