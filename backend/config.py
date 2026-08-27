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
    """运行时配置优先，.env 兜底。"""
    rc = _load_runtime_config()
    return rc.get("api_key") or DEEPSEEK_API_KEY


def set_api_key(key: str) -> None:
    rc = _load_runtime_config()
    rc["api_key"] = key.strip()
    _save_runtime_config(rc)
