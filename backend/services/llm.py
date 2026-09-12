import asyncio
import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from openai import AsyncOpenAI

from backend.config import (
    LLM_PROVIDERS,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    LLM_TIMEOUT,
    get_current_provider,
    get_current_model,
    get_current_provider_id,
    get_provider_api_key,
    get_custom_config,
)

logger = logging.getLogger(__name__)

EVAL_MARKER_START = "<<<XIAOYUAN_EVAL>>>"
EVAL_MARKER_END = "<<<END_EVAL>>>"

_clients: dict[str, AsyncOpenAI] = {}
_client_keys: dict[str, str] = {}
_client_sessions: dict[str, str] = {}  # provider_id -> 稳定会话 ID（OpenCode 网关要求）

# OpenCode Zen/Go 网关要求客户端自报身份（非通用 SDK 名）
_XIAOYUAN_UA = "xiaoyuan-tutor/1.0"


def get_client() -> AsyncOpenAI:
    """获取当前提供商的 AsyncOpenAI 客户端，支持多提供商缓存。"""
    provider = get_current_provider()
    provider_id = get_current_provider_id()
    api_key = get_provider_api_key(provider_id)

    # 自定义提供商使用自定义 base_url
    base_url = provider["base_url"]
    if provider_id == "custom":
        custom = get_custom_config()
        base_url = custom["base_url"] or base_url

    # 缓存检查
    if provider_id in _clients and _client_keys.get(provider_id) == api_key:
        return _clients[provider_id]

    # OpenCode 免费网关要求：x-opencode-session（稳定会话 ID）+ 自有 User-Agent
    default_headers: dict[str, str] = {}
    if provider_id == "opencode_free":
        if provider_id not in _client_sessions:
            _client_sessions[provider_id] = uuid.uuid4().hex
        default_headers = {
            "x-opencode-session": _client_sessions[provider_id],
            "User-Agent": _XIAOYUAN_UA,
        }

    _clients[provider_id] = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=LLM_TIMEOUT,
        default_headers=default_headers or None,
    )
    _client_keys[provider_id] = api_key
    return _clients[provider_id]


def get_current_provider_id() -> str:
    """获取当前提供商 ID。"""
    try:
        from backend.config import _load_llm_config
        rc = _load_llm_config()
        return rc.get("llm_provider", "deepseek")
    except Exception:
        return "deepseek"


async def _rate_limit_retry(coro, max_retries: int = 3):
    """带指数退避的速率限制重试。遇到 429 自动重试。"""
    for attempt in range(max_retries):
        try:
            return await coro
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "Rate limit" in err_msg or "rate_limit" in err_msg:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning("速率限制 (429)，%ds 后重试...", wait)
                    await asyncio.sleep(wait)
                    continue
                raise
            raise
    return await coro


async def stream_chat(
    system_prompt: str,
    history: list[dict[str, str]],
    user_message: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """调用当前提供商的 LLM 并以增量事件产出。

    实现说明：
    1. 根据提供商是否支持 tools 选择调用策略
    2. 支持 tools：原有逻辑（第一轮非流式检测工具，第二轮流式输出）
    3. 不支持 tools：降级为提示词引导 + 直接流式 + 后端 SymPy 校验
    """
    from backend.services.calculator import TOOLS, _execute_tool
    from backend.services.calc_verifier import verify_and_fix

    provider = get_current_provider()
    model = get_current_model()
    provider_id = get_current_provider_id()
    supports_tools = provider["supports_tools"]

    messages = [{"role": "system", "content": system_prompt}, *history]
    if user_message:
        messages.append({"role": "user", "content": user_message})

    client = get_client()

    if not supports_tools:
        # 降级：不调用 tools，直接流式输出
        system_prompt_with_rules = system_prompt + (
            "\n\n【计算规则】涉及数学计算时，必须先写出计算过程，再给出结果，不要心算。"
            "计算完成后，用 SymPy 风格写出最终答案。"
        )
        messages[0]["content"] = system_prompt_with_rules

        response = await _rate_limit_retry(
            client.chat.completions.create(
                model=model, messages=messages,
                temperature=LLM_TEMPERATURE, max_tokens=LLM_MAX_TOKENS,
                stream=True,
            )
        )

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
                marker_buf += content
                if EVAL_MARKER_START in marker_buf:
                    eval_started = True
                    continue
                yield {"type": "text", "content": content}
        finally:
            await response.close()

        # 流结束后解析评估块
        full_text = "".join(accumulated)
        visible, eval_data = parse_reply(full_text)

        # SymPy 后端校验：对输出中的数学计算进行验证
        fixed_text, fixes = verify_and_fix(visible)
        if fixes:
            logger.warning("calc_verifier 修正了 %d 处计算错误", len(fixes))
            yield {"type": "text", "content": fixed_text}
        else:
            if eval_data is not None:
                yield {"type": "eval", "data": eval_data}
        return

    # ---- 支持 tools 的提供商（原有逻辑）----

    # 第一轮：非流式调用，检测是否需要工具
    try:
        first_response = await _rate_limit_retry(
            client.chat.completions.create(
                model=model, messages=messages,
                temperature=LLM_TEMPERATURE, max_tokens=LLM_MAX_TOKENS,
                tools=TOOLS, tool_choice="auto", stream=False,
            )
        )
    except Exception as e:
        logger.error("LLM first call failed: %s", e)
        raise

    first_msg = first_response.choices[0].message

    # 如果 LLM 想调用工具
    if first_msg.tool_calls:
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
        response = await _rate_limit_retry(
            client.chat.completions.create(
                model=model, messages=messages,
                temperature=LLM_TEMPERATURE, max_tokens=LLM_MAX_TOKENS,
                stream=True,
            )
        )
    else:
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
            marker_buf += content
            if EVAL_MARKER_START in marker_buf:
                eval_started = True
                continue
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
    try:
        data = json.loads(raw)
        return _validate_eval_fields(data)
    except json.JSONDecodeError:
        pass

    cleaned = raw
    cleaned = re.sub(r"//[^\n]*", "", cleaned)
    cleaned = cleaned.replace("，", ",").replace("：", ":")
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    try:
        data = json.loads(cleaned)
        return _validate_eval_fields(data)
    except json.JSONDecodeError:
        pass

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
        "reply": "", "state": "", "mastery_updates": {},
        "gaps_found": [], "gaps_cleared": [], "error_type": None,
        "emotion": "neutral", "badges_hint": [], "session_progress": 0.0,
    }
    for key, default in defaults.items():
        if key not in data:
            data[key] = default
    return data


async def simple_chat(system_prompt: str, user_message: str) -> str:
    """非流式简单调用（测试用）。"""
    resp = await get_client().chat.completions.create(
        model=get_current_model(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=LLM_TEMPERATURE, max_tokens=LLM_MAX_TOKENS, stream=False,
    )
    return resp.choices[0].message.content or ""
