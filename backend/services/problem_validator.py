"""出题质量验证器（架构优化 E3）。

验证 LLM 出的题：
1. 答案正确性（SymPy 验证 + 异常值检查）
2. 难度匹配（与学生掌握度匹配）
3. 无歧义（指代不明等）
4. 知识点匹配（题目确实考察目标知识点）
"""

import re

import sympy as sp


class ProblemValidationResult:
    def __init__(self, is_valid: bool, issues: list = None, corrected: str = ""):
        self.is_valid = is_valid
        self.issues = issues or []
        self.corrected = corrected


def validate_problem(
    problem: str,
    answer: str,
    target_topic: str = "",
    student_mastery: float = 0.5,
) -> ProblemValidationResult:
    """验证题目质量。返回 (是否有效, 问题列表)。"""
    issues: list[str] = []

    # 1. 答案正确性验证
    answer_valid, answer_issue = _validate_answer(problem, answer)
    if not answer_valid:
        issues.append(answer_issue)

    # 2. 难度匹配
    difficulty = _estimate_difficulty(problem)
    if abs(difficulty - student_mastery) > 0.4:
        if difficulty > student_mastery:
            issues.append(f"题目难度（{difficulty:.2f}）高于学生水平（{student_mastery:.2f}），可能太难")
        else:
            issues.append(f"题目难度（{difficulty:.2f}）低于学生水平（{student_mastery:.2f}），可能太简单")

    # 3. 歧义检查
    issues.extend(_check_ambiguity(problem))

    # 4. 知识点匹配（基础检查）
    if target_topic:
        topic_in_problem = target_topic in problem or _topic_keywords_in(target_topic, problem)
        if not topic_in_problem:
            issues.append(f"题目疑似未考察目标知识点「{target_topic}」")

    return ProblemValidationResult(is_valid=len(issues) == 0, issues=issues)


def _validate_answer(problem: str, answer: str) -> tuple[bool, str]:
    """验证答案是否合理。"""
    # 空答案
    if not answer or not answer.strip():
        return False, "缺少答案，需要人工补全"

    answer_nums = re.findall(r'-?\d+\.?\d*', answer)
    if not answer_nums:
        return True, ""  # 非数字答案（如 x>3），跳过数值验证

    # 异常大的数
    for num in answer_nums:
        try:
            val = float(num)
            if abs(val) > 1e10:
                return False, f"答案数值异常大（{val}），疑似错误"
        except ValueError:
            continue

    # 尝试 SymPy 验证：如果题目是纯计算式且答案为数值
    computed = _try_compute_from_problem(problem, answer_nums[0])
    if computed is not None:
        try:
            claimed = float(answer_nums[0])
            if abs(computed - claimed) > 0.001:
                return False, f"答案 {claimed} 与题目计算结果 {computed} 不一致"
        except ValueError:
            pass

    return True, ""


def _try_compute_from_problem(problem: str, first_answer_num: str) -> float | None:
    """尝试从题目中提取算式并计算（用于验证答案）。"""
    # 匹配形如 "3×4" / "3*4+5" / "25 × 16" 的纯算式（允许空格）
    match = re.search(r'(\d+\s*[×xX*\/+\-]\s*\d+(?:\s*[×xX*\/+\-]\s*\d+)*)', problem)
    if not match:
        return None
    try:
        expr_str = match.group(1).replace("×", "*").replace("x", "*").replace("X", "*")
        expr_str = expr_str.replace(" ", "")
        # 保护：仅允许数字和运算符
        if not re.fullmatch(r'[\d\+\-\*\/\.]+', expr_str):
            return None
        expr = sp.sympify(expr_str)
        if expr.is_number:
            return float(expr.evalf())
    except Exception:  # noqa: BLE001
        pass
    return None


def _estimate_difficulty(problem: str) -> float:
    """估算题目难度（0-1）。"""
    difficulty = 0.3  # 基础难度

    # 数字位数越多越难
    large_nums = re.findall(r'\d{3,}', problem)
    difficulty += len(large_nums) * 0.05

    # 运算步骤（逗号/分号分隔的子问题）
    steps = problem.count("，") + problem.count(";") + problem.count("。") + 1
    difficulty += min(steps * 0.05, 0.3)

    # 关键词难度
    hard_keywords = ["至少", "最多", "证明", "求证", "分类讨论", "动点", "存在性", "为什么"]
    for kw in hard_keywords:
        if kw in problem:
            difficulty += 0.1

    return min(difficulty, 1.0)


def _check_ambiguity(problem: str) -> list[str]:
    """检查题目歧义。"""
    issues = []
    # 指代不明：多个"它"且无明显所指
    if problem.count("它") > 1:
        issues.append("'它'出现多次，可能指代不明")
    # 缺失单位（含数字运算但没提到单位，且不是纯代数题）
    if re.search(r'\d+\s*[+\-*/×xX]\s*\d+', problem) and "单位" not in problem and "元" not in problem:
        # 纯算术题可能不需要单位，这里仅作弱提示
        pass
    # 数值之间缺少明确关系词
    if re.search(r'\d+\s+\d+', problem) and "个" not in problem and "元" not in problem:
        issues.append("存在相邻数字，关系表述可能不清晰")
    return issues


def _topic_keywords_in(topic: str, problem: str) -> bool:
    """检查题目是否包含目标知识点相关关键词。"""
    # 提取知识点名称中的核心词（去常见后缀）
    core = re.sub(r'(及其解法|的认识|的概念|与应用)', '', topic)
    return core in problem
