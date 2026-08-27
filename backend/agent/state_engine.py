"""确定性状态转移规则引擎（架构优化 A1）。

LLM 的 eval 块从"指令"降级为"建议"，最终状态转移由本引擎的确定性规则决定。
规则优先级：确定性规则（熔断/推进/回退）> LLM 合法建议 > 保持当前状态。
所有输出都必须通过 VALID_TRANSITIONS 校验，防止非法转移。
"""

from typing import Any, Optional

from backend.agent.assessment import VALID_TRANSITIONS


class StateTransitionResult:
    def __init__(self, new_state: str, reason: str, source: str):
        self.new_state = new_state
        self.reason = reason
        # source: "rule"（确定性规则）/ "llm"（LLM 建议）/ "keep"（保持）
        self.source = source

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"StateTransitionResult({self.new_state!r}, {self.source!r}, {self.reason})"


def _is_valid(current: str, target: str | None) -> bool:
    """检查 target 是否为从 current 出发的合法转移，或与当前相同。"""
    if not target:
        return False
    allowed = VALID_TRANSITIONS.get(current, set())
    return target == current or target in allowed


def decide_next_state(
    current: str,
    llm_suggested_state: Optional[str] = None,
    consecutive_correct: int = 0,
    consecutive_wrong: int = 0,
    turns_in_current_state: int = 0,
    mastery_avg: Optional[float] = None,
    abstract_thinking: Optional[float] = None,
    learning_preference: str = "",
    problem_type: str = "",
) -> StateTransitionResult:
    """根据确定性规则决定下一个状态（A1 + D1 动态化）。

    规则优先级：
    1. 熔断 — 同状态停留过久 → BREAK_SUGGESTION（若合法）或收尾
    2. 连续错误 → 回退或进入特殊讲解状态（ANALOGY/VISUALIZATION/ERROR_ROOT_CAUSE）
    3. 连续正确 → 推进（遵循转发表）
    4. 掌握度足够 → 跳过中间检查（D1：已掌握跳过 EXAMPLE_CHECK）
    5. LLM 建议（合法性校验后采纳）
    6. 保持当前状态
    """
    # ===== 规则1：熔断（D1：同状态停留过久 → 休息建议）=====
    if turns_in_current_state >= 8:
        if _is_valid(current, "BREAK_SUGGESTION"):
            return StateTransitionResult("BREAK_SUGGESTION", f"在 {current} 停留 {turns_in_current_state} 轮，触发休息建议", "rule")
        if _is_valid(current, "WRAP_UP"):
            return StateTransitionResult("WRAP_UP", f"在 {current} 停留过久，收尾", "rule")
        return StateTransitionResult(current, f"在 {current} 停留过久且无休息/收尾路径，保持", "keep")

    # ===== 规则2：连续错误 → 特殊讲解或回退（D1）=====
    if consecutive_wrong >= 3:
        # 抽象思维低 + CORE_DERIVE 连续错 → 类比讲解
        if current == "CORE_DERIVE" and abstract_thinking is not None and abstract_thinking < 0.4:
            if _is_valid(current, "ANALOGY_EXPLANATION"):
                return StateTransitionResult("ANALOGY_EXPLANATION", f"连续 {consecutive_wrong} 错且抽象思维低，转入类比讲解", "rule")
        # 几何/行程类 + visual 偏好 → 图形化引导
        if problem_type in ("geometry", "motion", "engineering", "ratio") and learning_preference == "visual":
            if _is_valid(current, "VISUALIZATION"):
                return StateTransitionResult("VISUALIZATION", f"几何/行程题 + visual 偏好，转入图形化引导", "rule")
        # 错误可识别 → 错误根因分析（ERROR_REVIEW 状态下）
        if current == "ERROR_REVIEW":
            if _is_valid(current, "ERROR_ROOT_CAUSE"):
                return StateTransitionResult("ERROR_ROOT_CAUSE", f"连续 {consecutive_wrong} 错，转入错误根因分析", "rule")
        # 例题检查连续错 → 回退核心推导
        if _is_valid(current, "CORE_DERIVE"):
            return StateTransitionResult("CORE_DERIVE", f"连续 {consecutive_wrong} 轮出错，回退到核心推导", "rule")
        return StateTransitionResult(current, f"连续 {consecutive_wrong} 轮出错，保持当前状态并切换讲解策略", "keep")

    # ===== 规则3：连续正确 → 推进（遵循转发表）=====
    if consecutive_correct >= 2:
        next_map = {
            "BLIND_SPOT": "CORE_DERIVE",
            "PLAN": "CORE_DERIVE",
            "CORE_DERIVE": "EXAMPLE_CHECK",
            "EXAMPLE_CHECK": "OPTIONAL_VARIANT",
            "QUICK_REVIEW": "FIX_ONE_ERROR",
            "FIX_ONE_ERROR": "WRAP_UP",
            "ANALOGY_EXPLANATION": "CORE_DERIVE",
            "VISUALIZATION": "CORE_DERIVE",
            "ERROR_ROOT_CAUSE": "FIX_ONE_ERROR",
            "BREAK_SUGGESTION": "CORE_DERIVE",
        }
        nxt = next_map.get(current)
        if nxt and _is_valid(current, nxt):
            return StateTransitionResult(nxt, f"连续 {consecutive_correct} 轮正确，推进到 {nxt}", "rule")

    # ===== 规则4：掌握度足够 → 跳过中间检查（D1）=====
    if current == "CORE_DERIVE" and mastery_avg is not None and mastery_avg >= 0.7:
        if _is_valid(current, "OPTIONAL_VARIANT"):
            return StateTransitionResult("OPTIONAL_VARIANT", f"掌握度 {mastery_avg:.2f} 足够，跳过例题检查直达变式", "rule")
        if _is_valid(current, "EXAMPLE_CHECK"):
            return StateTransitionResult("EXAMPLE_CHECK", f"掌握度 {mastery_avg:.2f} 足够，快速进入例题自检", "rule")

    # ===== 规则5：LLM 合法建议 =====
    if _is_valid(current, llm_suggested_state) and llm_suggested_state != current:
        return StateTransitionResult(
            llm_suggested_state,
            f"采纳 LLM 建议：{current} → {llm_suggested_state}",
            "llm",
        )

    # ===== 规则6：保持当前 =====
    return StateTransitionResult(current, "无明确转移信号，保持当前状态", "keep")


def update_consecutive_counts(student, eval_data: dict, current_state: str) -> None:
    """根据本轮对错更新连续正确/错误计数，并维护停留轮数。

    应在 apply_eval 完成状态转移**之前**调用，用旧状态判断。
    """
    sess = student.current_session

    # 停留轮数：无论是否转移，进入该状态后累计（由调用方在转移后重置）
    # 这里只累加正确/错误计数（基于本轮是否答对/答错）
    answered = eval_data.get("independent_success")
    error_type = eval_data.get("error_type")

    # 记录最近错误类型（供 C2 思维模型选择器使用）
    if error_type:
        sess.last_error_type = error_type

    if answered is True:
        sess.consecutive_correct += 1
        sess.consecutive_wrong = 0
    elif answered is False or error_type:
        sess.consecutive_wrong += 1
        sess.consecutive_correct = 0
    else:
        # 无明确对错信号（讲解/闲聊轮）不清零，保持现状（不因非作答轮打断连续计数）
        pass
