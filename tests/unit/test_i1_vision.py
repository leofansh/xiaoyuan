"""I1「多模态集成」缺口修复单元测试。

纯标准库 unittest，不发真实网络请求、不真实导入 rapidocr、不真实调用 OpenAI。
覆盖三项验收：
  1. vision.recognize_image_sync 无 key → 提前返回 {"available": False}，不实例化客户端
  2. ocr.is_any_available()：key 为空 + rapidocr 不可导入 → False；
     key 非空 → True；rapidocr 可导入 → True
  3. ocr.is_available() 语义保持（仅依赖 rapidocr，不依赖 API Key）
"""

import builtins
import types
import unittest
from unittest.mock import patch

from backend.services import ocr
from backend.services.vision import recognize_image_sync


def _fake_import(rapidocr_importable: bool):
    """构造 __import__ 的 side_effect，模拟 rapidocr_onnxruntime 可/不可导入。"""
    real_import = builtins.__import__

    def fake_import(name, globals_=None, locals_=None, fromlist=(), level=0):
        if name == "rapidocr_onnxruntime":
            if not rapidocr_importable:
                raise ImportError("No module named 'rapidocr_onnxruntime'")
            module = types.ModuleType(name)
            module.RapidOCR = object
            return module
        return real_import(name, globals_, locals_, fromlist, level)

    return fake_import


class VisionNoKeyTest(unittest.TestCase):
    def test_no_key_returns_unavailable_without_network(self):
        """key 为空 → 提前返回 {"available": False}，且不实例化 OpenAI 客户端。"""
        with patch("backend.config.get_api_key", return_value=""), \
             patch("openai.OpenAI") as mock_openai:
            result = recognize_image_sync(b"dummy-image-bytes", ".jpg")
        self.assertFalse(result.get("available"))
        self.assertEqual(result.get("error"), "API Key 未配置")
        mock_openai.assert_not_called()


class OcrIsAnyAvailableTest(unittest.TestCase):
    def test_no_key_and_no_rapidocr_returns_false(self):
        """key 为空且 rapidocr 不可导入 → is_any_available() 返回 False。"""
        with patch("backend.config.get_api_key", return_value=""), \
             patch("builtins.__import__", side_effect=_fake_import(False)):
            self.assertFalse(ocr.is_any_available())

    def test_key_present_returns_true(self):
        """key 非空 → is_any_available() 返回 True（无需 rapidocr）。"""
        with patch("backend.config.get_api_key", return_value="sk-test"):
            self.assertTrue(ocr.is_any_available())

    def test_rapidocr_importable_returns_true(self):
        """rapidocr 可导入 → is_any_available() 返回 True（无需 key）。"""
        with patch("backend.config.get_api_key", return_value=""), \
             patch("builtins.__import__", side_effect=_fake_import(True)):
            self.assertTrue(ocr.is_any_available())


class OcrIsAvailableSemanticsTest(unittest.TestCase):
    def test_is_available_ignores_key(self):
        """is_available() 只依赖 rapidocr：key 非空也不影响 rapidocr 检测结果。"""
        with patch("backend.config.get_api_key", return_value="sk-test"), \
             patch("builtins.__import__", side_effect=_fake_import(False)):
            self.assertFalse(ocr.is_available())

    def test_is_available_true_when_rapidocr_importable(self):
        """rapidocr 可导入 → is_available() 返回 True。"""
        with patch("builtins.__import__", side_effect=_fake_import(True)):
            self.assertTrue(ocr.is_available())


if __name__ == "__main__":
    unittest.main()
