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
