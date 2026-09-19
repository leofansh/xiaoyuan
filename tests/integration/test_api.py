"""FastAPI 核心 HTTP 端点集成测试。

用 fastapi.testclient.TestClient 对核心 API 做真实 HTTP 层验证（状态码 + 关键字段），
不依赖网络、不调用 LLM。所有存储与配置路径（backend.config.STUDENTS_DIR、
backend.services.storage.STUDENTS_DIR、backend.config.CONFIG_FILE）均重定向到临时目录，
绝不触碰真实 data/ 目录。
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend.main import app


class ApiIntegrationBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._students_dir = Path(self._tmp.name) / "students"
        self._config_file = Path(self._tmp.name) / "config.json"
        self._patches = [
            mock.patch("backend.config.STUDENTS_DIR", self._students_dir),
            mock.patch("backend.services.storage.STUDENTS_DIR", self._students_dir),
            mock.patch("backend.config.CONFIG_FILE", self._config_file),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()


class StudentEndpointTest(ApiIntegrationBase):
    def test_create_list_get_student(self):
        with TestClient(app) as client:
            resp = client.post("/api/student", json={"name": "小明", "grade": 6})
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(data["student_id"].startswith("stu_"))
            self.assertEqual(data["name"], "小明")

            sid = data["student_id"]
            listing = client.get("/api/students")
            self.assertEqual(listing.status_code, 200)
            ids = [s["id"] for s in listing.json()]
            self.assertIn(sid, ids)

            detail = client.get(f"/api/student/{sid}")
            self.assertEqual(detail.status_code, 200)
            d = detail.json()
            self.assertEqual(d["id"], sid)
            self.assertEqual(d["name"], "小明")
            self.assertEqual(d["grade"], 6)

    def test_student_not_found(self):
        with TestClient(app) as client:
            resp = client.get("/api/student/stu_nonexistent")
            self.assertEqual(resp.status_code, 404)


class KnowledgeAndGameEndpointTest(ApiIntegrationBase):
    def test_knowledge_tree(self):
        with TestClient(app) as client:
            resp = client.get("/api/knowledge/tree")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("chapters", data)
            self.assertTrue(data["chapters"])
            first_chapter = next(iter(data["chapters"].values()))
            self.assertTrue(first_chapter)
            self.assertIn("id", first_chapter[0])
            self.assertIn("name", first_chapter[0])

    def test_twenty_four_round(self):
        with TestClient(app) as client:
            resp = client.get("/api/games/twenty-four/round")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(len(data["cards"]), 4)
            self.assertGreaterEqual(data["solution_count"], 1)

    def test_twenty_four_check(self):
        with TestClient(app) as client:
            sid = client.post("/api/student", json={"name": "小明", "grade": 6}).json()["student_id"]
            ok = client.post("/api/games/twenty-four/check", json={
                "student_id": sid,
                "cards": [4, 4, 4, 4],
                "expression": "4*4+4+4",
            })
            self.assertEqual(ok.status_code, 200)
            data = ok.json()
            self.assertTrue(data["valid"])
            self.assertTrue(data["correct"])
            self.assertEqual(data["reason"], "太棒了！")

            wrong = client.post("/api/games/twenty-four/check", json={
                "student_id": sid,
                "cards": [4, 4, 4, 4],
                "expression": "4+4+4+4",
            })
            self.assertEqual(wrong.status_code, 200)
            wd = wrong.json()
            self.assertTrue(wd["valid"])
            self.assertFalse(wd["correct"])

    def test_cards_library(self):
        with TestClient(app) as client:
            resp = client.get("/api/cards/library")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("cards", data)
            self.assertGreater(data["total"], 0)
            self.assertEqual(data["total"], len(data["cards"]))


class ProgressAndConfigEndpointTest(ApiIntegrationBase):
    def test_student_progress(self):
        with TestClient(app) as client:
            sid = client.post("/api/student", json={"name": "小明", "grade": 6}).json()["student_id"]
            resp = client.get(f"/api/student/{sid}/progress")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["name"], "小明")
            self.assertIn("nodes", data)
            self.assertTrue(data["nodes"])
            self.assertIn("open_gaps", data)
            self.assertIn("avg_mastery", data)
            self.assertIn("badges_earned", data)
            self.assertIn("badges_all", data)
            self.assertIn("streak_chain", data)

    def test_config_get(self):
        with TestClient(app) as client:
            resp = client.get("/api/config")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("has_key", data)
            self.assertIn("api_key_masked", data)
            self.assertIn("pure_mode", data)
            self.assertFalse(data["pure_mode"])
            self.assertIn("card_drop_rates", data)
            self.assertIn("ab_test", data)


class PblResetEndpointTest(ApiIntegrationBase):
    """PBL 项目「重新开始」：重置进度、重玩不重复发奖（规格 7.2.1 扩展）。"""

    PROJECT = "missile_trajectory"

    def _complete(self, client, sid, level_id):
        enter = client.post(f"/api/pbl/projects/{self.PROJECT}/enter",
                            json={"level_id": level_id, "student_id": sid})
        self.assertEqual(enter.status_code, 200)
        comp = client.post(f"/api/pbl/projects/{self.PROJECT}/complete",
                           json={"level_id": level_id, "student_id": sid,
                                 "score": 1.0, "hit": True, "attempts": 1})
        self.assertEqual(comp.status_code, 200)
        return comp.json()

    def test_pbl_reset_flow(self):
        with TestClient(app) as client:
            sid = client.post("/api/student", json={"name": "小圆", "grade": 6}).json()["student_id"]

            # 先通关 Lv.1 + Lv.2
            r1 = self._complete(client, sid, 1)
            self.assertTrue(r1["completed"])
            self.assertEqual(r1["rewards"]["xp"], 30)
            self.assertFalse(r1["replayed"])
            self.assertTrue(self._complete(client, sid, 2)["completed"])

            detail = client.get(f"/api/pbl/projects/{self.PROJECT}?student_id=" + sid).json()
            self.assertEqual(detail["progress"]["completed_levels"], 2)

            # 重新开始：进度清空、回到"可开始"
            reset = client.post(f"/api/pbl/projects/{self.PROJECT}/reset", json={"student_id": sid})
            self.assertEqual(reset.status_code, 200)
            self.assertTrue(reset.json()["success"])

            detail2 = client.get(f"/api/pbl/projects/{self.PROJECT}?student_id=" + sid).json()
            self.assertEqual(detail2["progress"]["completed_levels"], 0)

            listing = client.get("/api/pbl/projects?student_id=" + sid).json()
            proj = next(p for p in listing["projects"] if p["id"] == self.PROJECT)
            self.assertEqual(proj["status"], "available")

            # 重玩 Lv.1：通关但不再重复发奖
            r2 = self._complete(client, sid, 1)
            self.assertTrue(r2["completed"])
            self.assertTrue(r2["replayed"])
            self.assertIsNone(r2["rewards"])

    def test_pbl_reset_guard(self):
        with TestClient(app) as client:
            sid = client.post("/api/student", json={"name": "小红", "grade": 6}).json()["student_id"]

            # 未开始的项目无法重置
            never = client.post("/api/pbl/projects/music_math/reset", json={"student_id": sid})
            self.assertEqual(never.status_code, 200)
            self.assertFalse(never.json()["success"])

            # 缺 student_id → 400
            missing = client.post(f"/api/pbl/projects/{self.PROJECT}/reset", json={})
            self.assertEqual(missing.status_code, 400)


if __name__ == "__main__":
    unittest.main()
