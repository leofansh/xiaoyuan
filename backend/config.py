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


DEFAULT_CARD_DROP_RATES = {"common": 0.60, "rare": 0.30, "epic": 0.09, "legendary": 0.01}


def _normalize_card_drop_rates(rates) -> dict[str, float]:
    """对 4 个稀有度逐 key 白名单规范化：数值非负才接受，缺 key 用默认。"""
    if not isinstance(rates, dict):
        rates = {}
    normalized = {}
    for key, default in DEFAULT_CARD_DROP_RATES.items():
        v = rates.get(key, default)
        normalized[key] = float(v) if isinstance(v, (int, float)) and v >= 0 else default
    return normalized


def get_card_drop_rates() -> dict[str, float]:
    """V3.0 13.9.4：读取卡片掉落概率（运行时配置优先，缺省用默认值）。"""
    rc = _load_runtime_config()
    raw = rc.get("card_drop_rates")
    if not isinstance(raw, dict):
        return dict(DEFAULT_CARD_DROP_RATES)
    return _normalize_card_drop_rates(raw)


def set_card_drop_rates(rates: dict) -> dict[str, float]:
    """V3.0 13.9.4：保存卡片掉落概率，返回规范化后的 dict。"""
    normalized = _normalize_card_drop_rates(rates)
    rc = _load_runtime_config()
    rc["card_drop_rates"] = normalized
    _save_runtime_config(rc)
    return normalized


DEFAULT_AB_TEST = {"enabled": False, "variant_a_ratio": 0.5}


def _normalize_ab_test(raw) -> dict:
    """对 A/B 测试配置逐 key 白名单规范化：非法/越界回退默认，缺 key 用默认。"""
    if not isinstance(raw, dict):
        raw = {}
    enabled = bool(raw.get("enabled", DEFAULT_AB_TEST["enabled"]))
    ratio = raw.get("variant_a_ratio", DEFAULT_AB_TEST["variant_a_ratio"])
    if not isinstance(ratio, (int, float)) or not (0.0 < ratio < 1.0):
        ratio = DEFAULT_AB_TEST["variant_a_ratio"]
    return {"enabled": enabled, "variant_a_ratio": float(ratio)}


def get_ab_test_config() -> dict:
    """设计方案 98：读取 A/B 测试配置（运行时配置优先，缺省用默认值）。"""
    rc = _load_runtime_config()
    raw = rc.get("ab_test")
    if not isinstance(raw, dict):
        return dict(DEFAULT_AB_TEST)
    return _normalize_ab_test(raw)


def set_ab_test_config(value: dict) -> dict:
    """设计方案 98：保存 A/B 测试配置，返回规范化后的 dict。"""
    normalized = _normalize_ab_test(value)
    rc = _load_runtime_config()
    rc["ab_test"] = normalized
    _save_runtime_config(rc)
    return normalized


DEFAULT_VARIABLE_REWARDS = {
    "pet_event_prob": 0.05,
    "pet_event_daily_max": 1,
    "pet_event_xp_range": [3, 8],
    "combo_crit_threshold": 5,
    "combo_crit_prob": 0.25,
    "combo_crit_xp_multiplier": 2,
    "combo_crit_guarantee_rarity": "epic",
}

_VALID_RARITIES = ("common", "rare", "epic", "legendary")


def _normalize_variable_rewards(vr) -> dict:
    """对可变奖励逐 key 白名单规范化：非法/越界回退默认，缺 key 用默认。"""
    if not isinstance(vr, dict):
        vr = {}
    d = DEFAULT_VARIABLE_REWARDS

    def _prob(key: str):
        v = vr.get(key, d[key])
        return float(v) if isinstance(v, (int, float)) and 0.0 <= v <= 1.0 else d[key]

    def _pos_num(key: str):
        v = vr.get(key, d[key])
        return v if isinstance(v, (int, float)) and v > 0 else d[key]

    def _pos_int(key: str):
        v = vr.get(key, d[key])
        return int(v) if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else d[key]

    rng = vr.get("pet_event_xp_range", d["pet_event_xp_range"])
    if (isinstance(rng, (list, tuple)) and len(rng) == 2
            and all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in rng)
            and rng[0] <= rng[1]):
        xp_range = [rng[0], rng[1]]
    else:
        xp_range = list(d["pet_event_xp_range"])

    rarity = vr.get("combo_crit_guarantee_rarity", d["combo_crit_guarantee_rarity"])
    if rarity not in _VALID_RARITIES:
        rarity = d["combo_crit_guarantee_rarity"]

    return {
        "pet_event_prob": _prob("pet_event_prob"),
        "pet_event_daily_max": _pos_int("pet_event_daily_max"),
        "pet_event_xp_range": xp_range,
        "combo_crit_threshold": _pos_int("combo_crit_threshold"),
        "combo_crit_prob": _prob("combo_crit_prob"),
        "combo_crit_xp_multiplier": _pos_num("combo_crit_xp_multiplier"),
        "combo_crit_guarantee_rarity": rarity,
    }


def get_variable_rewards() -> dict:
    """V3.0 13.9.4：读取可变奖励配置（运行时配置优先，缺省用默认值）。"""
    rc = _load_runtime_config()
    raw = rc.get("variable_rewards")
    if not isinstance(raw, dict):
        return dict(DEFAULT_VARIABLE_REWARDS)
    return _normalize_variable_rewards(raw)


def set_variable_rewards(vr: dict) -> dict:
    """V3.0 13.9.4：保存可变奖励配置，返回规范化后的 dict。"""
    normalized = _normalize_variable_rewards(vr)
    rc = _load_runtime_config()
    rc["variable_rewards"] = normalized
    _save_runtime_config(rc)
    return normalized
