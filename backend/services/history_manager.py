"""对话历史 token 管理（架构优化 P3 项 H3）。

纯函数、纯标准库、确定性规则实现，绝不调用 LLM / 网络做摘要。
DeepSeek 系模型、中文为主的场景下，用「字符级规则估算」近似 token 数，
避免引入任何三方 tokenizer 依赖。

各函数职责：
  - estimate_tokens        单条文本 token 估算
  - estimate_history_tokens 整段历史 token 估算（含每条消息的固定开销）
  - build_summary_block     确定性抽样摘要（不调 LLM）
  - trim_history            裁剪核心：轮数 + token 预算 + 摘要兜底
"""

import math

# 每条消息固定开销（role/content 的开/关标签等结构化字符的 token 近似）
MESSAGE_OVERHEAD = 4

# 摘要兜底时的最小非空头部标记（极端长单条消息预算占满时仍保留）
_SUMMARY_MIN = "[早前对话摘要]"


def estimate_tokens(text: str) -> int:
    """确定性估算单段文本的 token 数（纯 stdlib，不依赖 tokenizer）。

    依据：DeepSeek 系模型使用 BPE 分词，英文常见词约 3~4 字符/token，
    单个中文字符约占 0.6 token（全角标点同档）。因此按字符分类加权：
      - 空白字符            0.1 token/字符（几乎可忽略）
      - ASCII（字母/数字/标点）0.3 token/字符
      - 非 ASCII（中文/全角）  0.6 token/字符
    结果向上取整，非空文本至少为 1。

    Args:
        text: 待估算的文本。

    Returns:
        估算 token 数；空串返回 0。
    """
    if not text:
        return 0
    total = 0.0
    for ch in text:
        if ch.isspace():
            total += 0.1
        elif ord(ch) < 128:
            total += 0.3
        else:
            total += 0.6
    return max(1, math.ceil(total))


def estimate_history_tokens(history: list[dict]) -> int:
    """估算整段对话历史的 token 数。

    逐条 content 估算求和，每条消息额外加 MESSAGE_OVERHEAD（4 token）
    作为 role/content 结构化标签的开销。

    Args:
        history: 形如 [{"role": "user"|"assistant", "content": str}, ...] 的列表。

    Returns:
        估算 token 数。
    """
    total = 0
    for msg in history:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if content is None:
            content = ""
        total += estimate_tokens(str(content)) + MESSAGE_OVERHEAD
    return total


def _truncate(text: str, max_chars: int) -> str:
    """按字符上限截断，超长时追加省略号（不抛异常，任何上限值均安全）。"""
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)] + "…"


def _sample_user_messages(user_msgs: list[str], limit: int = 4) -> list[str]:
    """从 user 消息列表中均匀抽样，首条必取，最多返回 limit 条。"""
    n = len(user_msgs)
    if n <= limit:
        return list(user_msgs)
    result = [user_msgs[0]]
    step = (n - 1) / (limit - 1)
    for k in range(1, limit):
        idx = min(round(k * step), n - 1)
        if user_msgs[idx] not in result:
            result.append(user_msgs[idx])
    return result


def build_summary_block(history: list[dict], max_chars: int | None = None) -> str:
    """确定性摘要（绝不调用 LLM）：抽样早期 user 消息拼为一段固定格式文字。

    策略：取历史中所有 user 消息，抽样「第 1 条 + 中间均匀间隔 ≤3 条」，
    每条截短到 40 字符（去换行），拼成：
      [早前对话摘要] 学生说过：...；知识点进展：见最近对话
    受 max_chars 限制截断并加省略号；空历史或没有 user 消息时返回空串。

    Args:
        history: 对话历史消息列表。
        max_chars: 可选字符上限，超长时截断。

    Returns:
        摘要字符串；无内容时返回 ""。
    """
    if not history:
        return ""
    user_msgs = [
        str(m.get("content", ""))
        for m in history
        if isinstance(m, dict) and m.get("role") == "user" and m.get("content")
    ]
    if not user_msgs:
        return ""
    samples = _sample_user_messages(user_msgs)
    previews: list[str] = []
    for s in samples:
        s = s.strip().replace("\n", " ").replace("\r", " ")
        if len(s) > 40:
            s = s[:40] + "…"
        previews.append(s)
    said = "；".join(previews)
    block = f"[早前对话摘要] 学生说过：{said}；知识点进展：见最近对话"
    if max_chars is not None:
        block = _truncate(block, max_chars)
    return block


def _split_turns(history: list[dict]) -> list[list[dict]]:
    """把扁平消息列表切分为轮（一个 turn 以 user 消息为界，含其后的 assistant）。"""
    turns: list[list[dict]] = []
    cur: list[dict] = []
    for msg in history:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "user":
            if cur:
                turns.append(cur)
            cur = [msg]
        else:
            cur.append(msg)
    if cur:
        turns.append(cur)
    return turns


def _flatten(turns: list[list[dict]]) -> list[dict]:
    """把轮列表还原为扁平消息列表。"""
    flat: list[dict] = []
    for turn in turns:
        flat.extend(turn)
    return flat


def _count_turns(history: list[dict]) -> int:
    """统计轮数（一个 turn = 一条 user 消息打头）。"""
    return sum(1 for m in history if isinstance(m, dict) and m.get("role") == "user")


def trim_history(
    history: list[dict],
    *,
    max_turns: int = 20,
    max_tokens: int = 6000,
    min_recent_turns: int = 4,
) -> list[dict]:
    """裁剪对话历史，避免超出轮数/token 限制。

    一个 turn = 一对 user+assistant（或单条 user）。

    策略：
      1. 若总轮数 ≤ max_turns 且估算 token ≤ max_tokens → 原样返回；
      2. 否则保留最近 min_recent_turns 轮（无论如何不低于这些轮），
         再向前逐轮补足到 max_turns 轮，但受 max_tokens 预算约束（超预算即停）；
      3. 若保留最少轮后仍超出预算（极端长单条消息），对最早被裁剪的部分
         生成确定性摘要，以一条 role="assistant" 插入最前（不可用 system）；
         摘要自身也计入预算，预算不足时缩短摘要内容。

    说明：本函数只处理 history 列表本身，不涉及 system_prompt 的位置；
    返回列表中不会出现 role="system" 的元素。

    Args:
        history: 对话历史消息列表（纯 user/assistant 交替）。
        max_turns: 保留的最大轮数。
        max_tokens: 保留历史的最大估算 token 预算。
        min_recent_turns: 无论预算如何都保留的最近轮数下限。

    Returns:
        裁剪后的新列表。
    """
    if not history:
        return []

    turns = _split_turns(history)
    total_turns = len(turns)

    # 1. 完全在预算内：原样返回
    if total_turns <= max_turns and estimate_history_tokens(history) <= max_tokens:
        return list(history)

    # 2. 保留最近 min_recent_turns 轮（至少），再向前补足
    keep_recent = min(min_recent_turns, total_turns)
    result_turns = list(turns[-keep_recent:])

    for turn in reversed(turns[:-keep_recent]):
        candidate = [turn] + result_turns
        if len(candidate) > max_turns:
            break
        if estimate_history_tokens(_flatten(candidate)) > max_tokens:
            break
        result_turns = candidate

    result = _flatten(result_turns)

    # 预算内：直接返回（正常裁剪路径，无摘要）
    if estimate_history_tokens(result) <= max_tokens:
        return result

    # 3. 极端长单条消息：保留最少轮仍超预算 → 对最早被裁剪部分做摘要兜底
    earlier = _flatten(turns[:-len(result_turns)])
    summary_text = build_summary_block(earlier)
    if not summary_text:
        return result

    # 摘要自身计入预算：先算剩余空间，不足则缩短摘要内容（但至少保留头部标记，保证非空）
    room = max_tokens - estimate_history_tokens(result) - MESSAGE_OVERHEAD
    if room > 0:
        # 粗略按每字符 0.6 token 反推可容纳字符数（偏保守，保证不超）
        max_chars = int(room / 0.6)
        summary_text = _truncate(summary_text, max_chars)
    else:
        summary_text = _SUMMARY_MIN

    return [{"role": "assistant", "content": summary_text}] + result
