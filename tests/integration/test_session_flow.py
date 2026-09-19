"""会话完整流程集成测试（HTTP 层，LLM 已 Mock）。

通过 HTTP 接口走完确定性会话流程：创建学生 → 开场心情打卡 → 选择学习模式 →
选择知识点 → 聊天（Mock 掉 backend.services.llm.stream_chat / simple_chat，返回
固定文本）→ 结束会话归档。验证 SSE 响应体包含被 Mock 的事件类型，以及结束后
学生档案被写入临时存储并含会话摘要。全程无网络、无真实 LLM 调用、不触碰 data/。
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.storage import get_storage


async def _fake_stream_chat(system_prompt, history, user_message):
    yield {"type": "text", "content": "小圆的测试回复"}


async def _fake_simple_chat(system_prompt, user_message):
    return "测试"


class SessionFlowTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._students_dir = Path(self._tmp.name) / "students"
        self._config_file = Path(self._tmp.name) / "config.json"
        self._patches = [
            mock.patch("backend.config.STUDENTS_DIR", self._students_dir),
            mock.patch("backend.services.storage.STUDENTS_DIR", self._students_dir),
            mock.patch("backend.config.CONFIG_FILE", self._config_file),
            mock.patch("backend.services.llm.stream_chat", new=_fake_stream_chat),
            mock.patch("backend.services.llm.simple_chat", new=_fake_simple_chat),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()


class FullSessionFlowTest(SessionFlowTestBase):
    def test_full_session_flow(self):
        with TestClient(app) as client:
            # 1. 创建学生
            created = client.post("/api/student", json={"name": "小明", "grade": 6})
            self.assertEqual(created.status_code, 200)
            sid = created.json()["student_id"]

            # 2. 开场心情打卡
            start = client.post("/api/session/start", json={"student_id": sid, "mood": "😊"})
            self.assertEqual(start.status_code, 200)
            start_data = start.json()
            self.assertIn("opening", start_data)
            self.assertIn("mode_suggestion", start_data)

            # 3. 选择学习模式 A
            mode = client.post("/api/session/mode", json={"student_id": sid, "mode": "A"})
            self.assertEqual(mode.status_code, 200)
            self.assertEqual(mode.json()["mode"], "A")

            # 4. 选择知识点
            topic = client.post("/api/session/topic", json={"student_id": sid, "topic_id": "elem_sifasuan"})
            self.assertEqual(topic.status_code, 200)
            self.assertEqual(topic.json()["topic_id"], "elem_sifasuan")

            # 5. 聊天（LLM 已 Mock）
            chat = client.post("/api/chat", json={"student_id": sid, "message": "我们开始吧"})
            self.assertEqual(chat.status_code, 200)
            body = chat.text
            self.assertIn("event: text", body)
            self.assertIn("event: eval", body)
            self.assertIn("state", body)

            # 6. 结束会话
            end = client.post("/api/session/end", json={"student_id": sid})
            self.assertEqual(end.status_code, 200)
            summary = end.json()
            self.assertEqual(summary["topic"], "elem_sifasuan")
            self.assertGreaterEqual(summary["turns"], 1)
            self.assertIn("manifesto", summary)

            # 学生已保存到临时存储，含会话摘要
            saved = get_storage().load(sid)
            self.assertIsNotNone(saved)
            self.assertEqual(len(saved.session_history), 1)
            self.assertEqual(saved.session_history[0].mode, "A")
            self.assertGreaterEqual(saved.session_history[0].turns, 1)
            self.assertEqual(saved.total_sessions, 1)


if __name__ == "__main__":
    unittest.main()
