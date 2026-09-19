"""PBL 项目服务单元测试（reset_project / rewarded_levels 防刷奖逻辑）。

用标准库 unittest，不依赖 FastAPI / 网络 / LLM。覆盖规格 7.2.1 扩展：
- 项目「重新开始」reset_project：进度清空回到 Lv.1、状态回到可开始、
  已发奖励 ID（rewarded_levels）跨重置保留；
- 旧档案兜底：无 rewarded_levels 时按 completed_levels 继承，
  避免升级后重开刷奖；
- 重玩已领奖关卡只记星级，不重复发放 XP / 卡片 / 掌握度；
- 重玩未领奖关卡（先前未打到）正常发奖；
- 零进度记录状态为 available（而非 in_progress）。
"""

import unittest

from backend.models.student import Student
from backend.pbl.pbl_service import (
    complete_level,
    ensure_pbl,
    list_projects,
    reset_project,
)

PROJECT = "missile_trajectory"


def _student() -> Student:
    return Student(id="s1", name="小明")


def _complete(s, level_id, attempts=1):
    """通关一击命中；返回 result dict。"""
    return complete_level(s, PROJECT, level_id,
                          score=1.0, hit=True, attempts=attempts)


class ResetProjectTest(unittest.TestCase):
    def test_project_not_found(self):
        s = _student()
        r = reset_project(s, "no_such_project")
        self.assertFalse(r["success"])
        self.assertEqual(r["message"], "项目不存在")

    def test_not_started_cannot_reset(self):
        s = _student()
        r = reset_project(s, PROJECT)
        self.assertFalse(r["success"])
        self.assertEqual(r["message"], "项目尚未开始，无需重新开始")

    def test_reset_clears_progress_keeps_rewarded_levels(self):
        s = _student()
        _complete(s, 1)
        _complete(s, 2)
        record = s.pbl_projects["projects"][PROJECT]
        self.assertEqual(record["completed_levels"], [1, 2])
        self.assertEqual(record["rewarded_levels"], [1, 2])
        self.assertEqual(record["status"], "in_progress")

        r = reset_project(s, PROJECT)
        self.assertTrue(r["success"])
        self.assertTrue(r["restarted"])

        record = s.pbl_projects["projects"][PROJECT]
        # 进度字段回到初始
        self.assertEqual(record["current_level"], 1)
        self.assertEqual(record["unlocked_levels"], [1])
        self.assertEqual(record["completed_levels"], [])
        self.assertEqual(record["level_states"], {})
        self.assertEqual(record["choices_answered"], {})
        self.assertIsNone(record["completed_at"])
        # 已领奖关卡 ID 跨重置保留
        self.assertEqual(record["rewarded_levels"], [1, 2])

    def test_reset_zero_progress_shows_available(self):
        """零进度记录在列表/详情中显示可开始，而非进行中。"""
        s = _student()
        _complete(s, 1)
        reset_project(s, PROJECT)
        proj = next(p for p in list_projects(s)["projects"] if p["id"] == PROJECT)
        self.assertEqual(proj["status"], "available")
        self.assertEqual(proj["progress"]["completed_levels"], 0)

    def test_legacy_record_falls_back_to_completed_levels(self):
        """旧档案无 rewarded_levels 时按已完成关卡兜底，防重开刷奖。"""
        s = _student()
        s.pbl_projects = ensure_pbl(s.pbl_projects)
        legacy = {
            "project_id": PROJECT,
            "status": "in_progress",
            "current_level": 3,
            "unlocked_levels": [1, 2, 3],
            "completed_levels": [1, 2],
            "level_states": {"1": {"completed": True, "stars": 3, "best_score": 1.0, "attempts": 1},
                             "2": {"completed": True, "stars": 2, "best_score": 0.9, "attempts": 2}},
            "choices_answered": {},
            "total_time_spent": 100,
            "started_at": "2026-09-01T10:00:00",
            "completed_at": None,
        }  # 注意：无 rewarded_levels 键，模拟升级前存档
        s.pbl_projects["projects"][PROJECT] = legacy

        r = reset_project(s, PROJECT)
        self.assertTrue(r["success"])
        record = s.pbl_projects["projects"][PROJECT]
        self.assertEqual(record["rewarded_levels"], [1, 2])  # 从 completed_levels 继承

        # 重开后再打 Lv.1 → replayed，不重复发奖
        replay = _complete(s, 1)
        self.assertTrue(replay["replayed"])
        self.assertIsNone(replay["rewards"])


class ReplayRewardTest(unittest.TestCase):
    def test_first_completion_grants_rewards(self):
        s = _student()
        r = _complete(s, 1)
        self.assertTrue(r["completed"])
        self.assertFalse(r["replayed"])
        self.assertIsNotNone(r["rewards"])
        self.assertEqual(r["rewards"]["xp"], 30)          # missile Lv.1 奖励 30 XP
        self.assertTrue(r["rewards"]["card_dropped"]["is_new"])
        # pet 获得 XP；卡片入库；知识回溯 +0.02（0.1 LLM 弱观测 × 0.2 权重）
        self.assertEqual(s.pet["exp"], 30)
        self.assertIn("card_elem_fangcheng", s.cards["collected"])
        self.assertAlmostEqual(s.mastery["elem_fangcheng"].score, 0.02, places=4)
        self.assertEqual(s.pbl_projects["projects"][PROJECT]["rewarded_levels"], [1])

    def test_replay_after_reset_no_double_rewards(self):
        s = _student()
        _complete(s, 1)
        _complete(s, 2)
        reset_project(s, PROJECT)

        xp_before = s.pet["exp"]
        cards_before = s.cards["total_cards"]
        mastery_before = s.mastery["elem_fangcheng"].score

        replay = _complete(s, 1)
        self.assertTrue(replay["completed"])
        self.assertTrue(replay["replayed"])
        self.assertIsNone(replay["rewards"])               # 不重复发奖
        self.assertEqual(replay["stars_earned"], 3)        # 但星级照记

        # XP / 卡片 / 掌握度均未二次发放
        self.assertEqual(s.pet["exp"], xp_before)
        self.assertEqual(s.cards["total_cards"], cards_before)
        self.assertEqual(s.mastery["elem_fangcheng"].score, mastery_before)
        # 进度正常推进（Lv.1 重打后完成）
        record = s.pbl_projects["projects"][PROJECT]
        self.assertEqual(record["completed_levels"], [1])

    def test_unrewarded_level_after_reset_grants_normally(self):
        """重开前只打到 Lv.2；Lv.3 重开后首通 → 正常发奖（不在 rewarded_levels）。"""
        s = _student()
        _complete(s, 1)
        _complete(s, 2)
        reset_project(s, PROJECT)

        _complete(s, 1)    # replayed（已领奖）
        _complete(s, 2)    # replayed（已领奖）
        r3 = _complete(s, 3)
        self.assertTrue(r3["completed"])
        self.assertFalse(r3["replayed"])
        self.assertIsNotNone(r3["rewards"])
        self.assertEqual(r3["rewards"]["xp"], 50)          # missile Lv.3 奖励 50 XP
        self.assertEqual(s.pbl_projects["projects"][PROJECT]["rewarded_levels"], [1, 2, 3])

    def test_enter_level_locked_after_reset_until_replayed(self):
        """重置后 Lv.2 重新锁定，需先重打 Lv.1。"""
        from backend.pbl.pbl_service import enter_level

        s = _student()
        _complete(s, 1)
        _complete(s, 2)
        reset_project(s, PROJECT)

        r = enter_level(s, PROJECT, 2)
        self.assertFalse(r["can_enter"])
        self.assertIn("需先通关 Lv.1", r["reason"])


class ProjectStatusTest(unittest.TestCase):
    def test_zero_progress_available(self):
        """零进度记录 → available：reset 后能正确显示，不会被误判进进行中。"""
        from backend.pbl.pbl_service import _project_status

        record = {"current_level": 1, "unlocked_levels": [1],
                  "completed_levels": [], "level_states": {}}
        self.assertEqual(_project_status(record, 6), "available")
        self.assertEqual(_project_status(None, 6), "available")

    def test_partial_and_completed(self):
        from backend.pbl.pbl_service import _project_status

        partial = {"level_states": {"1": {"completed": True}}}
        self.assertEqual(_project_status(partial, 6), "in_progress")
        done = {"level_states": {str(i): {"completed": True} for i in range(1, 7)}}
        self.assertEqual(_project_status(done, 6), "completed")


if __name__ == "__main__":
    unittest.main()