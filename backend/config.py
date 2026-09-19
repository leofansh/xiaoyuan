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
# 架构优化 P3 项 H3：对话历史 token 管理
#   MAX_HISTORY_MESSAGES 保留（历史消息条数上限，兼容既有引用）
#   MAX_HISTORY_TURNS   对话历史最大保留轮数（1 轮 = user+assistant 或单条 user）
#   MAX_HISTORY_TOKENS  传入 LLM 的历史最大估算 token 预算
MAX_HISTORY_TURNS = 20
MAX_HISTORY_TOKENS = 6000
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


# ============================================================
# 架构优化 I2：配置化管理 —— prompts.yaml 加载
# 注意：不能用 backend/config/ 目录（会与 backend/config.py 模块名遮蔽冲突），
#       故使用 backend/configs/（复数）。
# ============================================================

_PROMPTS_FILE = Path(__file__).resolve().parent / "configs" / "prompts.yaml"
_PROMPTS_CACHE: dict = {}
_PROMPTS_CACHE_MTIME: float = -1.0

# prompts.yaml 中 strategy_params / wellbeing 的白名单键
# （仅保留这些键且值必须为数值；非法类型/未知键一律丢弃，由消费方用代码常量兜底默认值）
_PROMPTS_STRATEGY_PARAM_KEYS = (
    "max_consecutive_wrong_before_fallback",
    "max_turns_in_state",
    "consecutive_correct_threshold",
    "mastery_threshold",
    "mastery_threshold_low",
    "consecutive_wrong_analogy",
    "abstract_thinking_threshold",
    "anxiety_threshold",
    "step_count_threshold",
)

_PROMPTS_WELLBEING_KEYS = (
    "high_load_break_minutes",
    "normal_break_minutes",
    "max_daily_minutes",
)


def _normalize_prompt_params(raw, keys: tuple[str, ...]) -> dict:
    """对 strategy_params / wellbeing 做白名单规范化。

    仅保留白名单键、且值为 int/float（非 bool）的项；非法类型与未知键被丢弃，
    从而保证任意 YAML 内容都不会让下游崩坏（下游按 key 用代码常量兜底默认）。
    """
    if not isinstance(raw, dict):
        return {}
    normalized: dict = {}
    for key in keys:
        value = raw.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            normalized[key] = value
    return normalized


def load_prompts() -> dict:
    """读取 backend/configs/prompts.yaml 配置源。

    返回结构：
    - system_prompt / mode_a_prompt / mode_b_prompt / mode_weekend_prompt：str
      （缺失或非字符串时为空串 ""）
    - strategy_params / wellbeing：dict（白名单规范化后的数值映射）

    行为约定：
    - 文件不存在 / 损坏（YAML 解析失败或非 dict）时返回 {}，绝不抛异常。
    - 进程内缓存 + 文件 mtime 失效（文件改动后下一次调用自动重载）。
    - PyYAML 仅在本函数内惰性引入（配置层专用）。
    """
    global _PROMPTS_CACHE, _PROMPTS_CACHE_MTIME
    try:
        mtime = _PROMPTS_FILE.stat().st_mtime
    except OSError:
        _PROMPTS_CACHE = {}
        _PROMPTS_CACHE_MTIME = -1.0
        return {}

    if mtime == _PROMPTS_CACHE_MTIME:
        return _PROMPTS_CACHE

    try:
        import yaml

        data = yaml.safe_load(_PROMPTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = None
    if not isinstance(data, dict):
        # 文件损坏（解析失败或内容非 dict 映射）→ 与文件缺失一致返回 {}，绝不抛异常
        _PROMPTS_CACHE = {}
        _PROMPTS_CACHE_MTIME = mtime
        return {}

    def _text(key: str) -> str:
        value = data.get(key)
        return value if isinstance(value, str) else ""

    _PROMPTS_CACHE = {
        "system_prompt": _text("system_prompt"),
        "mode_a_prompt": _text("mode_a_prompt"),
        "mode_b_prompt": _text("mode_b_prompt"),
        "mode_weekend_prompt": _text("mode_weekend_prompt"),
        "strategy_params": _normalize_prompt_params(
            data.get("strategy_params"), _PROMPTS_STRATEGY_PARAM_KEYS
        ),
        "wellbeing": _normalize_prompt_params(
            data.get("wellbeing"), _PROMPTS_WELLBEING_KEYS
        ),
    }
    _PROMPTS_CACHE_MTIME = mtime
    return _PROMPTS_CACHE
