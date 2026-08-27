"""数学公式 OCR：基于 pix2tex (LaTeX-OCR) 识别图片中的数学公式。

可选依赖：pix2tex。未安装时自动降级为纯文字 OCR。
"""

import asyncio
import logging
import tempfile
import os
from typing import Any

logger = logging.getLogger(__name__)

_formula_engine: Any = None
_init_failed = False


def is_available() -> bool:
    """检查 pix2tex 是否可用。"""
    try:
        from pix2tex.cli import LatexOCR  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _get_engine() -> Any:
    global _formula_engine, _init_failed
    if _formula_engine is not None or _init_failed:
        return _formula_engine
    try:
        from pix2tex.cli import LatexOCR
        _formula_engine = LatexOCR()
        logger.info("pix2tex formula OCR engine loaded")
    except Exception as e:  # noqa: BLE001
        _init_failed = True
        logger.warning("pix2tex not available: %s", e)
    return _formula_engine


def recognize_formula_sync(image_bytes: bytes, suffix: str = ".png") -> list[str]:
    """同步识别图片中的数学公式，返回 LaTeX 列表。"""
    engine = _get_engine()
    if engine is None:
        return []

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix or ".png")
    try:
        tmp.write(image_bytes)
        tmp.close()

        latex = engine(tmp.name)
        if latex and latex.strip():
            return [latex.strip()]
        return []
    except Exception as e:  # noqa: BLE001
        logger.warning("Formula recognition failed: %s", e)
        return []
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


async def recognize_formula(image_bytes: bytes, suffix: str = ".png") -> list[str]:
    """异步包装：公式识别在线程池跑。"""
    return await asyncio.to_thread(recognize_formula_sync, image_bytes, suffix)
