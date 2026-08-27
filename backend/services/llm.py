import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any

from openai import AsyncOpenAI

from backend.config import (
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    LLM_TIMEOUT,
    get_api_key,
)

logger = logging.getLogger(__name__)

EVAL_MARKER_START = "<<<XIAOYUAN_EVAL>>>"
EVAL_MARKER_END = "<<<END_EVAL>>>"

_client: AsyncOpenAI | None = None
_current_key: str = ""


def get_client() -> AsyncOpenAI:
    global _client, _current_key
    key = get_api_key()
    if _client is None or key != _current_key:
        _client = AsyncOpenAI(
            api_key=key, base_url=DEEPSEEK_BASE_URL, timeout=LLM_TIMEOUT
        )
        _current_key = key
    return _client


async def stream_chat(
    system_prompt: str,
    history: list[dict[str, str]],
    user_message: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """调用 DeepSeek 并以增量事件产出。

    实现说明：
    1. 第一轮非流式调用，允许 LLM 发起 tool_calls（数学计算）
    2. 如果有 tool_calls，执行计算并将结果反馈给 LLM
    3. 第二轮流式输出最终回复（含评估块）
    """
    from backend.services.calculator import TOOLS, _execute_tool

    messages = [{"role": "system", "content": system_prompt}, *history]
    if user_message:
        messages.append({"role": "user", "content": user_message})

    client = get_client()

    # 第一轮：非流式调用，检测是否需要工具
    try:
        first_response = await client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            tools=TOOLS,
            tool_choice="auto",
            stream=False,
        )
    except Exception as e:
        logger.error("LLM first call failed: %s", e)
        raise

    first_msg = first_response.choices[0].message

    # 如果 LLM 想调用工具
    if first_msg.tool_calls:
        # 将 assistant 消息加入历史
        messages.append({
            "role": "assistant",
            "content": first_msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in first_msg.tool_calls
            ],
        })

        # 执行所有工具调用
        for tc in first_msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            result = _execute_tool(tc.function.name, args)
            logger.info("Tool %s(%s) -> %s", tc.function.name, args, result.get("success"))
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

        # 第二轮：流式输出最终回复
        response = await client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            stream=True,
        )
    else:
        # 没有工具调用：第一轮已是完整结果，模拟逐字推送
        full_content = first_msg.content or ""
        reply, eval_data = parse_reply(full_content)
        i = 0
        while i < len(reply):
            n = min(3, len(reply) - i)
            yield {"type": "text", "content": reply[i : i + n]}
            i += n
        if eval_data is not None:
            yield {"type": "eval", "data": eval_data}
        return

    # 真流式：实时推送正文，检测评估块后缓冲
    accumulated: list[str] = []
    eval_started = False
    marker_buf = ""

    try:
        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            content = getattr(delta, "content", None) if delta else None
            if not content:
                continue

            accumulated.append(content)

            if eval_started:
                continue

            # 滑动窗口检测评估块标记起点
            marker_buf += content
            if EVAL_MARKER_START in marker_buf:
                eval_started = True
                continue

            # 真正的逐字流式输出
            yield {"type": "text", "content": content}
    finally:
        await response.close()

    # 流结束后解析评估块
    full_text = "".join(accumulated)
    _, eval_data = parse_reply(full_text)
    if eval_data is not None:
        yield {"type": "eval", "data": eval_data}


def parse_reply(full_text: str) -> tuple[str, dict[str, Any] | None]:
    """从完整回复中剥离评估块，带多级降级策略。"""
    pattern = re.compile(
        rf"{re.escape(EVAL_MARKER_START)}(.*?){re.escape(EVAL_MARKER_END)}",
        re.DOTALL,
    )
    match = pattern.search(full_text)
    visible = pattern.sub("", full_text).strip()
    eval_data = None

    if match:
        raw = match.group(1).strip()
        eval_data = _try_parse_eval_json(raw)

    return visible, eval_data


def _try_parse_eval_json(raw: str) -> dict[str, Any] | None:
    """多级尝试解析评估块 JSON。"""
    # 1) 直接解析
    try:
        data = json.loads(raw)
        return _validate_eval_fields(data)
    except json.JSONDecodeError:
        pass

    # 2) 清理常见问题后重试（中文逗号、尾逗号、注释）
    cleaned = raw
    cleaned = re.sub(r"//[^\n]*", "", cleaned)  # 去除行注释
    cleaned = cleaned.replace("，", ",").replace("：", ":")  # 中文标点
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)  # 尾逗号
    try:
        data = json.loads(cleaned)
        return _validate_eval_fields(data)
    except json.JSONDecodeError:
        pass

    # 3) 提取最大的 JSON 对象
    json_match = re.search(r"\{[\s\S]*\}", cleaned)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            return _validate_eval_fields(data)
        except json.JSONDecodeError:
            pass

    logger.warning("评估块解析全部失败，原始内容前200字: %s", raw[:200])
    return None


def _validate_eval_fields(data: dict) -> dict:
    """校验并补全评估块必填字段。"""
    defaults = {
        "reply": "",
        "state": "",
        "mastery_updates": {},
        "gaps_found": [],
        "gaps_cleared": [],
        "error_type": None,
        "emotion": "neutral",
        "badges_hint": [],
        "session_progress": 0.0,
    }
    for key, default in defaults.items():
        if key not in data:
            data[key] = default
    return data


async def simple_chat(system_prompt: str, user_message: str) -> str:
    """非流式简单调用（测试用）。"""
    resp = await get_client().chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
        stream=False,
    )
    return resp.choices[0].message.content or ""
