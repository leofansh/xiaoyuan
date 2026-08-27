import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import config
from backend.agent import chat as agent_chat
from backend.agent.persona import CLOSING_MANIFESTO
from backend.knowledge import syllabus
from backend.models.student import Badge, Student
from backend.services.storage import get_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.STUDENTS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    yield


app = FastAPI(title="小圆助教", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def no_cache_frontend(request, call_next):
    """前端资源一律禁止缓存：个人本地应用，保证改动即时生效。"""
    response = await call_next(request)
    p = request.url.path
    if p == "/" or p.endswith((".html", ".js", ".css")):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class StudentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    grade: int = Field(default=6, ge=6, le=9)
    mood: str = ""


class SessionStart(BaseModel):
    student_id: str
    mood: str = "😐"


class ModeSelect(BaseModel):
    student_id: str
    mode: str  # A / B / weekend


class ChatMessage(BaseModel):
    student_id: str
    message: str = Field(max_length=2000)


class TopicSelect(BaseModel):
    student_id: str
    topic_id: str


class ErrorReviewSubmit(BaseModel):
    student_id: str
    q1_answer: str
    q2_answer: str
    error_type: str = "concept"
    topic_id: str = ""


def _load_student(student_id: str) -> Student:
    student = get_storage().load(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生档案不存在")
    return student


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.get("/api/students")
def list_students():
    return get_storage().list_all()


@app.post("/api/student")
def create_student(payload: StudentCreate):
    student = get_storage().create(payload.name.strip(), payload.grade)
    return {"student_id": student.id, "name": student.name}


@app.get("/api/student/{student_id}")
def get_student(student_id: str):
    s = _load_student(student_id)
    return s.model_dump()


@app.delete("/api/student/{student_id}")
def delete_student(student_id: str):
    storage = get_storage()
    path = storage._path(student_id)  # noqa: SLF001
    if not path.exists():
        raise HTTPException(status_code=404, detail="学生档案不存在")
    path.unlink()
    return {"deleted": True}


@app.get("/api/student/{student_id}/export")
def export_student(student_id: str):
    """导出学生完整数据为 JSON（用于备份/迁移）。"""
    from fastapi.responses import Response

    s = _load_student(student_id)
    data = s.model_dump_json(indent=2)
    return Response(
        content=data,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{s.name}_backup.json"'},
    )


@app.get("/api/student/{student_id}/progress")
def get_progress(student_id: str):
    s = _load_student(student_id)

    nodes = []
    for n in syllabus.all_nodes():
        nodes.append(
            {
                "id": n.id,
                "name": n.name,
                "chapter": n.chapter,
                "difficulty": n.difficulty,
                "is_core": n.is_core,
                "mastery": round(s.mastery_score(n.id), 2),
                "mastery_confidence": round(s.mastery_confidence(n.id), 2),
                "has_open_gap": any(g.topic_id == n.id and g.status == "open" for g in s.gaps),
            }
        )

    open_gaps = [
        {
            "topic_id": g.topic_id,
            "topic_name": g.topic_name,
            "type": g.type,
            "evidence": g.evidence,
            "found_at": g.found_at,
        }
        for g in s.open_gaps()
    ]

    confidence = [p["score"] for p in s.confidence_trend[-30:]]

    return {
        "name": s.name,
        "streak_chain": s.streak_chain,
        "week_baseline_count": s.week_baseline_count,
        "total_sessions": s.total_sessions,
        "badges_earned": s.badges,
        "badges_all": Badge.ALL,
        "confidence_trend": confidence,
        "avg_mastery": round(s.avg_mastery(), 2),
        "nodes": nodes,
        "open_gaps": open_gaps,
    }


@app.get("/api/student/{student_id}/weekly-report")
def get_weekly_report(student_id: str):
    """获取本周学习报告。"""
    from backend.services.weekly_report import generate_weekly_report
    s = _load_student(student_id)
    return generate_weekly_report(s)


@app.get("/api/student/{student_id}/notifications")
def get_notifications(student_id: str):
    """获取家长通知列表（F1）。"""
    s = _load_student(student_id)
    # 每次查询前检查是否需要生成新通知
    from backend.services.parent_notification import check_and_notify
    check_and_notify(s)
    return {"notifications": s.parent_notifications}


@app.get("/api/student/{student_id}/learning-plan")
def get_learning_plan(student_id: str):
    """获取本周学习计划（D2）。"""
    from backend.services.learning_path import generate_weekly_plan
    s = _load_student(student_id)
    plan = generate_weekly_plan(s)
    return plan.model_dump()


@app.get("/api/student/{student_id}/history")
def get_history(student_id: str):
    s = _load_student(student_id)
    MODE_LABELS = {"A": "🌟 深度成长", "B": "🛡 保底维稳", "weekend": "🧹 周末修复"}
    records = []
    for h in reversed(s.session_history):  # 最新在前
        records.append({
            "date": h.date,
            "mode": MODE_LABELS.get(h.mode, h.mode),
            "mood": h.mood,
            "topic_name": h.topic_name or "（未选主题）",
            "turns": h.turns,
            "blind_spots": h.blind_spots,
            "new_badges": h.new_badges,
            "duration_minutes": h.duration_minutes,
            "messages": h.messages,
        })
    return {"sessions": records, "total": len(records)}


class HistoryDelete(BaseModel):
    student_id: str
    index: int


class CognitiveAssessmentAnswer(BaseModel):
    student_id: str
    question_id: str
    answer: str = Field(max_length=500)  # 前端倒序列表中的位置（0=最新）


@app.post("/api/student/history/delete")
def delete_history_record(payload: HistoryDelete):
    s = _load_student(payload.student_id)
    total = len(s.session_history)
    if total == 0 or payload.index < 0 or payload.index >= total:
        raise HTTPException(status_code=400, detail="记录不存在")
    actual = total - 1 - payload.index
    removed = s.session_history.pop(actual)
    get_storage().save(s)
    return {"deleted": True, "date": removed.date, "remaining": total - 1}


class ApiKeyUpdate(BaseModel):
    api_key: str


@app.get("/api/config")
def get_config():
    key = config.get_api_key()
    masked = (key[:7] + "****" + key[-4:]) if len(key) > 12 else ("****" if key else "")
    return {"api_key_masked": masked, "has_key": bool(key)}


@app.post("/api/config")
def update_config(payload: ApiKeyUpdate):
    key = payload.api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API Key 不能为空")
    config.set_api_key(key)
    return {"ok": True, "message": "API Key 已保存，下次调用立即生效"}


@app.post("/api/session/start")
async def session_start(payload: SessionStart):
    storage = get_storage()
    lock = storage.get_lock(payload.student_id)
    async with lock:
        s = _load_student(payload.student_id)
        info = agent_chat.start_session(s, payload.mood)
        storage.save(s)
        return info


@app.post("/api/session/mode")
def session_mode(payload: ModeSelect):
    s = _load_student(payload.student_id)
    if payload.mode not in ("A", "B", "weekend"):
        raise HTTPException(status_code=400, detail="无效模式")
    agent_chat.select_mode(s, payload.mode)
    get_storage().save(s)
    prompts = {
        "A": "好呀，那我们开始今天的深度探索吧🌸 先说说看——今天上课哪里听得心里不太踏实呀？",
        "B": "没问题，守住底线就是胜利💪 今天哪里觉得有点模糊？我们快速过一遍就好。",
        "weekend": "周末修复时间到🌟 我们把这一周的漏洞逐个拆掉！准备好了吗？",
    }
    return {"mode": payload.mode, "prompt": prompts[payload.mode]}


@app.post("/api/session/topic")
def session_topic(payload: TopicSelect):
    s = _load_student(payload.student_id)
    ok = agent_chat.set_topic(s, payload.topic_id)
    if not ok:
        raise HTTPException(status_code=404, detail="知识点不存在")
    return {"topic_id": payload.topic_id}


_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _sse_response(gen):
    async def wrap():
        try:
            async for ev in gen:
                kind = ev.pop("type")
                yield f"event: {kind}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield f"event: error\ndata: {json.dumps({'message': f'哎呀出了点小状况：{type(e).__name__}'}, ensure_ascii=False)}\n\n"
    return StreamingResponse(wrap(), media_type="text/event-stream", headers=_SSE_HEADERS)


@app.post("/api/chat")
async def chat(payload: ChatMessage):
    storage = get_storage()
    lock = storage.get_lock(payload.student_id)
    async with lock:
        s = _load_student(payload.student_id)
        if not s.current_session.started_at:
            raise HTTPException(status_code=400, detail="请先打卡心情开始今天的会话")
        return _sse_response(agent_chat.process_message(s, payload.message))


@app.post("/api/chat/image")
async def chat_image(
    student_id: str = Form(...),
    note: str = Form(""),
    file: UploadFile = File(...),
):
    """拍照/选图上传：先 OCR，再送入对话。"""
    from backend.services import ocr as ocr_service

    storage = get_storage()
    lock = storage.get_lock(student_id)
    async with lock:
        s = _load_student(student_id)
        if not s.current_session.started_at:
            raise HTTPException(status_code=400, detail="请先打卡心情开始今天的会话")

        data = await file.read()
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="图片不能超过10MB哦")
        if not data:
            raise HTTPException(status_code=400, detail="照片是空的")

        if not ocr_service.is_available():
            raise HTTPException(status_code=501, detail="OCR模块未安装，请联系管理员安装paddleocr")

        try:
            suffix = ocr_service.safe_suffix(file.filename, file.content_type)
            ocr_result = await ocr_service.recognize(data, suffix)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"图片识别失败：{type(e).__name__}")

        message = ocr_service.describe_for_llm(ocr_result, note)
        from backend.agent.persona import PHOTO_GUIDE

        return _sse_response(agent_chat.process_message(s, message, external_extra=PHOTO_GUIDE))


@app.post("/api/error-review")
def submit_error_review(payload: ErrorReviewSubmit):
    s = _load_student(payload.student_id)
    result = agent_chat.submit_error_review(
        s, payload.q1_answer, payload.q2_answer, payload.error_type, payload.topic_id
    )
    return result


class ReviewComplete(BaseModel):
    student_id: str
    topic_id: str
    success: bool  # 是否答对


@app.post("/api/review/complete")
def review_complete(payload: ReviewComplete):
    """记录复习完成，更新下次复习时间。"""
    from backend.services.repetition import record_review
    s = _load_student(payload.student_id)
    record_review(s, payload.topic_id, payload.success)
    get_storage().save(s)
    return {"ok": True}


@app.post("/api/session/end")
async def session_end(payload: SessionStart):
    storage = get_storage()
    lock = storage.get_lock(payload.student_id)
    async with lock:
        s = _load_student(payload.student_id)
        summary = agent_chat.end_session(s)
        summary["manifesto"] = CLOSING_MANIFESTO
        return summary


@app.post("/api/session/end-beacon")
async def session_end_beacon(student_id: str = ""):
    """页面关闭时 sendBeacon 兜底保存。"""
    if not student_id:
        return {"ok": True}
    storage = get_storage()
    lock = storage.get_lock(student_id)
    async with lock:
        try:
            s = _load_student(student_id)
            agent_chat.end_session(s)
        except HTTPException:
            pass
        return {"ok": True}


@app.get("/api/knowledge/tree")
def knowledge_tree(student_id: str = ""):
    by_chapter: dict[str, list[dict]] = {}
    mastery: dict[str, float] = {}
    open_gap_ids: set[str] = set()

    if student_id:
        try:
            s = get_storage().load(student_id)
            if s:
                mastery = {tid: rec.score for tid, rec in s.mastery.items()}
                open_gap_ids = {g.topic_id for g in s.open_gaps()}
        except Exception:
            pass

    for n in syllabus.all_nodes():
        by_chapter.setdefault(n.chapter, []).append(
            {
                "id": n.id,
                "name": n.name,
                "chapter": n.chapter,
                "difficulty": n.difficulty,
                "is_core": n.is_core,
                "prerequisites": n.prerequisites,
                "common_mistakes": n.common_mistakes,
                "life_examples": n.life_examples,
                "mastery": round(mastery.get(n.id, 0.0), 2),
                "has_open_gap": n.id in open_gap_ids,
            }
        )
    return {"chapters": by_chapter}


# ---------------------------------------------------------------------------
# 认知发展评估（EP-P1-4）
# ---------------------------------------------------------------------------

@app.get("/api/cognitive-assessment/next")
def cognitive_assessment_next(student_id: str = ""):
    """获取下一道诊断题。"""
    from backend.agent.cognitive_assessment import get_next_question

    answered_ids: list[str] = []
    if student_id:
        s = get_storage().load(student_id)
        if s:
            answered_ids = [
                r.get("question_id", "")
                for r in getattr(s, "_cognitive_assessment_answers", [])
            ]
    q = get_next_question(answered_ids)
    if not q:
        return {"completed": True, "message": "评估已完成"}
    return {
        "completed": False,
        "question_id": q.id,
        "question": q.question,
        "order": q.order,
        "total": 6,
    }


@app.post("/api/cognitive-assessment/submit")
def cognitive_assessment_submit(payload: CognitiveAssessmentAnswer):
    """提交单题答案，返回评分和下一道题。"""
    from backend.agent.cognitive_assessment import (
        DIAGNOSTIC_QUESTIONS,
        compute_final_result,
        get_assessment_summary,
        get_next_question,
        score_answer,
    )

    storage = get_storage()
    s = _load_student(payload.student_id)

    # 获取题目
    question = next((q for q in DIAGNOSTIC_QUESTIONS if q.id == payload.question_id), None)
    if not question:
        raise HTTPException(status_code=400, detail="无效的题目ID")

    # 评分
    scores = score_answer(question, payload.answer)

    # 记录答案（临时存储在 student 上）
    s.cognitive_assessment_answers.append({
        "question_id": payload.question_id,
        "answer": payload.answer[:500],
        "scores": scores,
    })

    # 检查是否完成
    answered_ids = [a["question_id"] for a in s.cognitive_assessment_answers]
    next_q = get_next_question(answered_ids)

    if not next_q:
        # 汇总评分
        all_scores: dict[str, list[float]] = {}
        for entry in s.cognitive_assessment_answers:
            for dim, val in entry.get("scores", {}).items():
                all_scores.setdefault(dim, []).append(val)
        result = compute_final_result(all_scores)

        # 写入认知画像
        from datetime import datetime
        cp = s.cognitive_profile
        cp.cognitive_stage = result.cognitive_stage
        cp.working_memory_capacity = result.working_memory_capacity
        cp.abstract_thinking = round(result.abstract_thinking, 2)
        cp.metacognition_level = round(result.metacognition_level, 2)
        cp.executive_function = result.executive_function
        cp.math_anxiety = round(result.math_anxiety, 2)
        cp.learning_preference = result.learning_preference
        cp.assessed_at = datetime.now().isoformat(timespec="seconds")
        cp.last_updated = cp.assessed_at
        cp.assessment_confidence = round(result.confidence, 2)

        # 清理临时答题记录
        s.cognitive_assessment_answers.clear()
        storage.save(s)
        return {
            "completed": True,
            "summary": get_assessment_summary(result),
            "profile": {
                "cognitive_stage": result.cognitive_stage,
                "working_memory_capacity": result.working_memory_capacity,
                "abstract_thinking": round(result.abstract_thinking, 2),
                "metacognition_level": round(result.metacognition_level, 2),
                "math_anxiety": round(result.math_anxiety, 2),
                "learning_preference": result.learning_preference,
            },
        }

    storage.save(s)
    return {
        "completed": False,
        "next_question_id": next_q.id,
        "next_question": next_q.question,
        "order": next_q.order,
    }


@app.get("/api/cognitive-profile")
def get_cognitive_profile(student_id: str = ""):
    """获取学生的认知发展画像。"""
    if not student_id:
        return {"has_profile": False}
    s = get_storage().load(student_id)
    if not s:
        return {"has_profile": False}
    cp = s.cognitive_profile
    return {
        "has_profile": bool(cp.assessed_at),
        "cognitive_stage": cp.cognitive_stage,
        "working_memory_capacity": cp.working_memory_capacity,
        "abstract_thinking": cp.abstract_thinking,
        "metacognition_level": cp.metacognition_level,
        "executive_function": cp.executive_function,
        "math_anxiety": cp.math_anxiety,
        "learning_preference": cp.learning_preference,
        "domain_levels": cp.domain_levels,
        "assessed_at": cp.assessed_at,
        "assessment_confidence": cp.assessment_confidence,
    }


# ---------------------------------------------------------------------------
# 静态前端（挂载在最后，避免拦截 /api）
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIR), html=True), name="frontend")
