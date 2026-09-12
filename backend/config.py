import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

STUDENTS_DIR = BASE_DIR / "data" / "students"
FRONTEND_DIR = BASE_DIR / "frontend"
CONFIG_FILE = BASE_DIR / "data" / "config.json"

MAX_HISTORY_MESSAGES = 10
SESSION_DEEP_MINUTES = 15
SESSION_BASELINE_MINUTES = 5

LLM_TEMPERATURE = 0.4
LLM_MAX_TOKENS = 1500
LLM_TIMEOUT = 60

# LLM 提供商预设（V3.0 多 LLM 支持）
LLM_PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "supports_tools": True,
        "free": False,
        "free_note": "",
    },
    "opencode_free": {
        "name": "OpenCode Free（免费）",
        "base_url": "https://opencode.ai/zen/v1",
        "models": ["mimo-v2.5-free", "ling-3.0-flash-fin-free", "nemotron-3-ultra-free", "big-pickle"],
        "supports_tools": False,
        "free": True,
        "free_note": "需 OpenCode 账号 API Key，免费层有速率限制",
    },
    "gemini": {
        "name": "Google Gemini（免费层）",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "models": ["gemini-2.0-flash", "gemini-2.5-pro"],
        "supports_tools": True,
        "free": True,
        "free_note": "免费层每分钟 15 次请求",
    },
    "groq": {
        "name": "Groq（免费，超快）",
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
        "supports_tools": True,
        "free": True,
        "free_note": "免费层有速率限制，推理速度极快",
    },
    "custom": {
        "name": "自定义（OpenAI 兼容）",
        "base_url": "",
        "models": [],
        "supports_tools": True,
        "free": None,
        "free_note": "",
    },
}


def _load_llm_config() -> dict:
    """读取 config.json 中的 LLM 相关配置。"""
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_llm_config(data: dict) -> None:
    """保存 LLM 相关配置到 config.json。"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_current_provider() -> dict:
    """返回当前选中的提供商完整配置。"""
    rc = _load_llm_config()
    provider_id = rc.get("llm_provider", "deepseek")
    provider = LLM_PROVIDERS.get(provider_id, LLM_PROVIDERS["deepseek"])
    # 自定义提供商使用自定义 base_url 和 model
    if provider_id == "custom":
        provider = dict(provider)
        provider["base_url"] = rc.get("custom_base_url", "")
        provider["models"] = [rc.get("custom_model", "")] if rc.get("custom_model") else []
    return provider


def get_current_model() -> str:
    """返回当前模型名。"""
    rc = _load_llm_config()
    provider_id = rc.get("llm_provider", "deepseek")
    if provider_id == "custom":
        return rc.get("custom_model", "gpt-4")
    provider = LLM_PROVIDERS.get(provider_id, LLM_PROVIDERS["deepseek"])
    return rc.get("llm_model", provider["models"][0] if provider["models"] else "deepseek-chat")


def get_current_provider_id() -> str:
    """返回当前提供商 ID。"""
    rc = _load_llm_config()
    return rc.get("llm_provider", "deepseek")


def get_provider_api_key(provider_id: str) -> str:
    """获取指定提供商的 API Key。"""
    rc = _load_llm_config()
    return rc.get("api_keys", {}).get(provider_id, "")


def set_llm_config(provider_id: str, model: str, api_key: str) -> None:
    """保存 LLM 配置（提供商、模型、API Key）。"""
    rc = _load_llm_config()
    if "api_keys" not in rc:
        rc["api_keys"] = {}
    rc["llm_provider"] = provider_id
    rc["llm_model"] = model
    rc["api_keys"][provider_id] = api_key.strip()
    _save_llm_config(rc)


def get_custom_config() -> dict:
    """获取自定义提供商的 base_url 和 model。"""
    rc = _load_llm_config()
    return {"base_url": rc.get("custom_base_url", ""), "model": rc.get("custom_model", "")}


def set_custom_config(base_url: str, model: str) -> None:
    """保存自定义提供商配置。"""
    rc = _load_llm_config()
    rc["custom_base_url"] = base_url.strip()
    rc["custom_model"] = model.strip()
    _save_llm_config(rc)

OCR_ENABLE_FORMULA = os.getenv("OCR_ENABLE_FORMULA", "true").lower() in ("1", "true", "yes")


def _load_runtime_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_runtime_config(data: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_api_key() -> str:
    """运行时配置优先（旧格式），.env 兜底。兼容旧配置格式。"""
    rc = _load_runtime_config()
    # 新格式：优先从 api_keys 字典中获取当前提供商的 key
    if "api_keys" in rc and rc.get("llm_provider"):
        provider_id = rc["llm_provider"]
        key = rc["api_keys"].get(provider_id, "")
        if key:
            return key
    return rc.get("api_key") or DEEPSEEK_API_KEY


def set_api_key(key: str) -> None:
    rc = _load_runtime_config()
    rc["api_key"] = key.strip()
    _save_runtime_config(rc)


def get_pure_mode() -> bool:
    """V3.0 P0：纯学习模式开关（关闭所有游戏化/娱乐化新功能）。"""
    rc = _load_runtime_config()
    return bool(rc.get("pure_mode", False))


def set_pure_mode(value: bool) -> None:
    """V3.0 P0：保存纯学习模式开关状态。"""
    rc = _load_runtime_config()
    rc["pure_mode"] = bool(value)
    _save_runtime_config(rc)
