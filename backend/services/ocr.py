"""题目照片识别服务：DeepSeek-V4-Flash-Vision 图片理解 + rapidocr 文字识别。

底层引擎：
- 图片理解：DeepSeek-V4-Flash-Vision-Exp（文字+公式+图形）
- 文字识别：rapidocr-onnxruntime（备选，纯文字场景）
- 公式识别：pix2tex (LaTeX-OCR)，可选依赖，未安装时自动降级
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any

from backend.config import OCR_ENABLE_FORMULA

_engine: Any = None
_init_failed = False


def is_available() -> bool:
    try:
        from rapidocr_onnxruntime import RapidOCR  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _get_engine() -> Any:
    global _engine, _init_failed
    if _engine is not None or _init_failed:
        return _engine
    try:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    except Exception:  # noqa: BLE001
        _init_failed = True
        raise
    return _engine


def recognize_sync(image_bytes: bytes, suffix: str = ".png") -> dict:
    """同步识别：DeepSeek-V4-Flash-Vision 图片理解 + rapidocr 文字识别。"""
    # 优先使用 DeepSeek-Vision 做图片理解
    try:
        from backend.services.vision import recognize_image_sync
        vision_result = recognize_image_sync(image_bytes, suffix)
        if vision_result.get("available"):
            return vision_result
    except Exception:
        pass

    # 降级：使用 rapidocr + pix2tex
    engine = _get_engine()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix or ".png")
    try:
        tmp.write(image_bytes)
        tmp.close()

        lines: list[str] = []
        if engine is not None:
            result, _ = engine(tmp.name)
            if result:
                lines = [text.strip() for _, text, _ in result if text and text.strip()]

        # 公式识别（可选模块）
        formulas: list[str] = []
        if OCR_ENABLE_FORMULA:
            try:
                from backend.services.formula_ocr import recognize_formula_sync
                formulas = recognize_formula_sync(image_bytes, suffix)
            except ImportError:
                pass

        return {
            "available": True,
            "lines": lines,
            "text": "\n".join(lines),
            "formulas": formulas,
        }
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


async def recognize(image_bytes: bytes, suffix: str = ".png") -> dict:
    """异步包装：OCR 在线程池跑，不阻塞事件循环。"""
    return await asyncio.to_thread(recognize_sync, image_bytes, suffix)


def describe_for_llm(result: dict, note: str) -> str:
    """把识别结果拼成给小圆看的消息正文（含 LaTeX 公式）。"""
    # 如果是 Vision 模块返回的结果，使用 vision 的 describe_for_llm
    if result.get("diagram") is not None or result.get("raw"):
        from backend.services.vision import describe_for_llm as vision_describe
        return vision_describe(result, note)

    parts = ["[学生发来一张题目照片]"]
    if result.get("text"):
        parts.append(f"照片上的文字（OCR）：\n{result['text']}")
    if result.get("formulas"):
        parts.append("识别到的数学公式（LaTeX）：")
        for i, f in enumerate(result["formulas"], 1):
            parts.append(f"  公式{i}: ${f}$")
    if not result.get("text") and not result.get("formulas"):
        parts.append("（注意：这张照片没能识别出清晰内容，请她口头描述题目）")
    if note.strip():
        parts.append(f"学生的附言：{note.strip()}")
    return "\n".join(parts)


def safe_suffix(filename: str | None, content_type: str | None) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
        return ".jpg" if ext == ".jpeg" else ext
    if content_type and "png" in content_type:
        return ".png"
    return ".jpg"
