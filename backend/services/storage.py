import asyncio
import json
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.config import STUDENTS_DIR
from backend.models.student import Badge, Student


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_student_id() -> str:
    return f"stu_{uuid4().hex[:10]}"


class StudentStorage:
    def __init__(self) -> None:
        STUDENTS_DIR.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, asyncio.Lock] = {}

    def get_lock(self, student_id: str) -> asyncio.Lock:
        """获取 per-student 锁，防止并发写入冲突。"""
        if student_id not in self._locks:
            self._locks[student_id] = asyncio.Lock()
        return self._locks[student_id]

    def _path(self, student_id: str) -> Path:
        safe = student_id.replace("/", "_").replace("\\", "_")
        return STUDENTS_DIR / f"{safe}.json"

    def save(self, student: Student) -> None:
        student.last_active = _now()
        path = self._path(student.id)
        # 自动备份：保留最近3个版本
        if path.exists():
            backup_dir = STUDENTS_DIR / "backups"
            backup_dir.mkdir(exist_ok=True)
            backup_name = f"{student.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_path = backup_dir / backup_name
            try:
                backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            except OSError:
                pass
            # 清理超过3个的旧备份
            backups = sorted(backup_dir.glob(f"{student.id}_*.json"))
            for old in backups[:-3]:
                try:
                    old.unlink()
                except OSError:
                    pass
        fd, tmp_path = tempfile.mkstemp(dir=str(STUDENTS_DIR), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(student.model_dump_json(indent=2))
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def load(self, student_id: str) -> Student | None:
        path = self._path(student_id)
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return Student.model_validate_json(f.read())

    def create(self, name: str, grade: int = 6) -> Student:
        student = Student(
            id=new_student_id(),
            name=name,
            grade=grade,
            created_at=_now(),
            last_active=_now(),
        )
        self.save(student)
        return student

    def list_all(self) -> list[dict[str, Any]]:
        students = []
        for p in STUDENTS_DIR.glob("stu_*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                students.append(
                    {"id": data["id"], "name": data["name"], "grade": data["grade"]}
                )
            except (json.JSONDecodeError, KeyError):
                continue
        return students

    @staticmethod
    def touch_streak(student: Student) -> bool:
        """更新学习链。保底日也算不断链。返回是否触发不断链徽章。"""
        today = date.today().isoformat()
        last = student.streak_last_date
        if last == today:
            return False
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        if last == yesterday:
            student.streak_chain += 1
        else:
            student.streak_chain = 1
        student.streak_last_date = today

        triggered = False
        if student.streak_chain == 7 and Badge.STREAK_7 not in student.badges:
            student.badges.append(Badge.STREAK_7)
            triggered = True
        return triggered

    @staticmethod
    def record_mode(student: Student, mode: str) -> None:
        student.mode_history.append({"date": _now(), "mode": mode})
        this_week = [m for m in student.mode_history if m["date"] >= (date.today() - timedelta(days=6)).isoformat()]
        student.week_baseline_count = sum(1 for m in this_week if m["mode"] == "B")

    @staticmethod
    def add_mood(student: Student, mood: str) -> None:
        student.mood_checkins.append({"date": _now(), "mood": mood})


_storage: StudentStorage | None = None


def get_storage() -> StudentStorage:
    global _storage
    if _storage is None:
        _storage = StudentStorage()
    return _storage
