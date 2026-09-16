import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime

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


app = FastAPI(title="小圆助教", version="2.0.0", lifespan=lifespan)


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
    api_key: str = ""
    pure_mode: bool | None = None  # V3.0 P0：纯学习模式开关（可单独提交）


# ---------------------------------------------------------------------------
# LLM 配置 Schemas（V3.0 多 LLM 支持）
# ---------------------------------------------------------------------------

class LLMConfigGetResponse(BaseModel):
    current_provider: str
    current_model: str
    providers: list[dict]
    custom_base_url: str = ""
    custom_model: str = ""


class LLMConfigUpdate(BaseModel):
    provider: str
    model: str
    api_key: str = ""
    base_url: str = ""


class LLMTestRequest(BaseModel):
    provider: str
    model: str
    api_key: str
    base_url: str = ""


class LLMTestResponse(BaseModel):
    success: bool
    response: str = ""
    error: str = ""


@app.get("/api/llm/config")
def get_llm_config():
    """获取当前 LLM 配置。"""
    from backend.config import LLM_PROVIDERS, get_current_provider, get_current_model, get_current_provider_id, get_custom_config

    provider_id = get_current_provider_id()
    provider = get_current_provider()
    api_key = config.get_provider_api_key(provider_id)

    providers_list = []
    for pid, pdata in LLM_PROVIDERS.items():
        has_key = bool(config.get_provider_api_key(pid))
        providers_list.append({
            "id": pid,
            "name": pdata["name"],
            "models": pdata["models"],
            "free": pdata["free"],
            "free_note": pdata.get("free_note", ""),
            "supports_tools": pdata["supports_tools"],
            "api_key_set": has_key,
        })

    custom = get_custom_config()
    return LLMConfigGetResponse(
        current_provider=provider_id,
        current_model=get_current_model(),
        providers=providers_list,
        custom_base_url=custom["base_url"],
        custom_model=custom["model"],
    )


@app.post("/api/llm/config")
def update_llm_config(payload: LLMConfigUpdate):
    """更新 LLM 配置（提供商、模型、API Key）。"""
    from backend.config import set_llm_config, set_custom_config, LLM_PROVIDERS

    provider_id = payload.provider
    model = payload.model
    api_key = payload.api_key
    base_url = payload.base_url

    if provider_id == "custom":
        # 自定义提供商：保存 base_url 和 model
        set_custom_config(base_url, model)
        # 同时保存 API Key（如果有）
        if api_key:
            set_llm_config(provider_id, model, api_key)
    else:
        set_llm_config(provider_id, model, api_key)

    return {"success": True, "current_provider": provider_id, "current_model": model}


@app.post("/api/llm/test")
async def test_llm_connection(payload: LLMTestRequest):
    """测试 LLM 连接是否正常工作。"""
    from backend.config import LLM_PROVIDERS

    provider = payload.provider
    model = payload.model
    api_key = payload.api_key
    base_url = payload.base_url

    # 获取提供商的 base_url
    if provider == "custom" and base_url:
        target_base_url = base_url
    elif provider in LLM_PROVIDERS:
        target_base_url = LLM_PROVIDERS[provider]["base_url"]
    else:
        return LLMTestResponse(success=False, error="未知提供商")

    if not target_base_url:
        return LLMTestResponse(success=False, error="缺少 base_url")

    try:
        import uuid as _uuid

        from openai import AsyncOpenAI

        # OpenCode 免费网关要求：x-opencode-session（稳定会话 ID）+ 自有 User-Agent
        default_headers: dict[str, str] = {}
        if provider == "opencode_free":
            default_headers = {
                "x-opencode-session": _uuid.uuid4().hex,
                "User-Agent": "xiaoyuan-tutor/1.0",
            }
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=target_base_url,
            timeout=15,
            default_headers=default_headers or None,
        )
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "你好，请简短回复确认连接正常。"}],
            max_tokens=50,
            stream=False,
        )
        text = response.choices[0].message.content or ""
        return LLMTestResponse(success=True, response=text[:100])
    except Exception as e:
        err_msg = str(e)
        if "401" in err_msg or "Unauthorized" in err_msg or "api_key" in err_msg.lower():
            return LLMTestResponse(success=False, error="API Key 无效，请检查")
        elif "429" in err_msg or "Rate limit" in err_msg:
            return LLMTestResponse(success=False, error="当前模型使用人数较多，请稍后再试")
        elif "connection" in err_msg.lower() or "network" in err_msg.lower() or "timeout" in err_msg.lower():
            return LLMTestResponse(success=False, error="网络连接失败，请检查 URL 和网络设置")
        return LLMTestResponse(success=False, error=f"连接失败：{type(e).__name__}: {err_msg[:100]}")


@app.get("/api/config")
def get_config():
    key = config.get_api_key()
    masked = (key[:7] + "****" + key[-4:]) if len(key) > 12 else ("****" if key else "")
    return {"api_key_masked": masked, "has_key": bool(key), "pure_mode": config.get_pure_mode()}


@app.post("/api/config")
def update_config(payload: ApiKeyUpdate):
    # V3.0 P0：纯学习模式开关（可不带 API Key 单独提交）
    if payload.pure_mode is not None:
        config.set_pure_mode(payload.pure_mode)
        return {"ok": True, "message": "纯学习模式已更新"}
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
# V3.0 P1：宠物 / 卡片 / Combo / 输出>输入 API（规格 §3/§4/§5/§11.3）
# ---------------------------------------------------------------------------

class PetFeedRequest(BaseModel):
    xp_amount: int = 20
    source: str = "session_complete"
    message: str = ""


class PetSkinRequest(BaseModel):
    skin_id: str


class PetRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=10)


class CardDropRequest(BaseModel):
    source: str = "mastery"
    knowledge_node: str = ""
    guaranteed: bool = False


class CardExchangeRequest(BaseModel):
    skin_id: str
    cost: int | None = None


class TeachRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    topic_id: str = ""


class ProblemCreateRequest(BaseModel):
    problem: str = Field(min_length=1, max_length=1000)
    answer: str = ""
    judge: bool = True  # 孩子自己判：小圆答得对不对


def _pet_view(student: Student) -> dict:
    """宠物视图：实时心情 + 心情话术（规格 3.3.1）。"""
    from backend.services.pet import compute_mood, ensure_pet

    pet = ensure_pet(student.pet)
    mood, mood_message = compute_mood(pet)
    level_up_available = pet.get("exp", 0) >= pet.get("exp_to_next", 1)
    return {
        "pet": pet,
        "level_up_available": level_up_available,
        "mood_message": mood_message,
    }


@app.get("/api/pet/{student_id}")
def pet_get(student_id: str):
    """3.3.1 获取宠物状态。"""
    s = _load_student(student_id)
    return _pet_view(s)


@app.post("/api/pet/{student_id}/feed")
async def pet_feed(student_id: str, payload: PetFeedRequest):
    """3.3.2 喂养宠物（学习后自动调用，也可手动）。"""
    from backend.services.pet import add_xp, ensure_pet

    storage = get_storage()
    lock = storage.get_lock(student_id)
    async with lock:
        s = _load_student(student_id)
        s.pet = ensure_pet(s.pet)
        res = add_xp(s.pet, payload.xp_amount, source=payload.source, message=payload.message)
        storage.save(s)
        return res


@app.post("/api/pet/{student_id}/skin")
async def pet_skin(student_id: str, payload: PetSkinRequest):
    """3.3.3 更换皮肤。"""
    from backend.services.pet import ensure_pet, set_skin

    storage = get_storage()
    lock = storage.get_lock(student_id)
    async with lock:
        s = _load_student(student_id)
        s.pet = ensure_pet(s.pet)
        try:
            result = set_skin(s.pet, payload.skin_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        storage.save(s)
        return result


@app.post("/api/pet/{student_id}/rename")
async def pet_rename(student_id: str, payload: PetRenameRequest):
    """3.3.4 重命名宠物。"""
    from backend.services.pet import ensure_pet, rename

    storage = get_storage()
    lock = storage.get_lock(student_id)
    async with lock:
        s = _load_student(student_id)
        s.pet = ensure_pet(s.pet)
        result = rename(s.pet, payload.name)
        storage.save(s)
        return result


@app.get("/api/pet/{student_id}/interact")
def pet_interact(student_id: str):
    """3.3.5 宠物互动（点击触发随机语音）。"""
    from backend.services.pet import compute_mood, ensure_pet, interact_message

    s = _load_student(student_id)
    pet = ensure_pet(s.pet)
    compute_mood(pet)
    message, animation = interact_message(pet)
    return {"message": message, "animation": animation}


@app.get("/api/cards/library")
def cards_library():
    """4.3.1 获取卡片库（全部卡片定义）。"""
    from backend.knowledge.cards import all_cards

    cards = all_cards()
    return {"cards": cards, "total": len(cards)}


@app.get("/api/cards/{student_id}")
def cards_get(student_id: str):
    """4.3.2 获取学生已收集卡片。"""
    from backend.knowledge.cards import completion_rate, ensure_cards

    s = _load_student(student_id)
    cards = ensure_cards(s.cards)
    return {**cards, "completion_rate": completion_rate(cards)}


@app.post("/api/cards/{student_id}/drop")
async def cards_drop(student_id: str, payload: CardDropRequest):
    """4.3.3 卡片掉落（后端内部调用为主，也提供手动测试接口）。"""
    from backend.knowledge.cards import drop_card, ensure_cards

    storage = get_storage()
    lock = storage.get_lock(student_id)
    async with lock:
        s = _load_student(student_id)
        cards = ensure_cards(s.cards)
        result = drop_card(
            cards,
            source=payload.source,
            knowledge_node=payload.knowledge_node,
            guaranteed=payload.guaranteed,
        )
        s.cards = cards
        storage.save(s)
        return result


@app.post("/api/cards/{student_id}/exchange")
async def cards_exchange(student_id: str, payload: CardExchangeRequest):
    """4.3.4 星光值兑换皮肤。"""
    from backend.knowledge.cards import ensure_cards, exchange_skin

    storage = get_storage()
    lock = storage.get_lock(student_id)
    async with lock:
        s = _load_student(student_id)
        cards = ensure_cards(s.cards)
        try:
            result = exchange_skin(cards, payload.skin_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        s.cards = cards
        # 兑换成功的皮肤写入宠物
        from backend.services.pet import ensure_pet
        pet = ensure_pet(s.pet)
        if payload.skin_id not in pet["unlocked_skins"]:
            pet["unlocked_skins"].append(payload.skin_id)
        s.pet = pet
        storage.save(s)
        return result


@app.get("/api/combo/{student_id}")
def combo_get(student_id: str):
    """5.4 获取 Combo 状态。"""
    s = _load_student(student_id)
    combo = s.combo or {}
    return {
        "current": combo.get("current", 0),
        "best_all_time": combo.get("best_all_time", 0),
        "best_this_week": combo.get("best_this_week", 0),
        "total_combos_5": combo.get("total_combos_5", 0),
        "total_combos_10": combo.get("total_combos_10", 0),
    }


@app.post("/api/teach/{student_id}")
async def teach_submit(student_id: str, payload: TeachRequest):
    """11.3 教宠物/小圆：提交讲解内容，评价 + 讲对宠物+50XP。"""
    from backend.services.pet import add_xp, ensure_pet

    storage = get_storage()
    lock = storage.get_lock(student_id)
    async with lock:
        s = _load_student(student_id)
        content = payload.content.strip()

        # 启发式质量评价：讲解有长度且有数学痕迹即视为"用心讲对"
        math_hits = sum(kw in content for kw in ("因为", "所以", "先", "然后", "等于", "=", "步", "分", "公式", "定义"))
        quality = min(1.0, 0.4 + len(content) / 300 + math_hits * 0.1)

        now = datetime.now().isoformat(timespec="seconds")
        s.creations.append({
            "type": "teach",
            "content": content[:500],
            "topic_id": payload.topic_id,
            "quality": round(quality, 2),
            "created_at": now,
        })

        pet_feed_result = None
        if quality >= 0.5:
            s.pet = ensure_pet(s.pet)
            pet_feed_result = add_xp(s.pet, 50, source="teach_pet")

        storage.save(s)
        feedback = (
            "讲得真清楚！你是小老师的料～"
            if quality >= 0.7 else
            "嗯，思路有了！再试试把'为什么'也说出来？"
        )
        return {
            "success": True,
            "quality": round(quality, 2),
            "feedback": feedback,
            "pet_feed": {
                k: pet_feed_result[k]
                for k in ("xp_gained", "new_exp", "leveled_up", "new_level", "unlocked_skin")
            } if pet_feed_result else None,
        }


@app.post("/api/problems/{student_id}/create")
async def problem_create(student_id: str, payload: ProblemCreateRequest):
    """11.3 孩子出题：入'我的题库'，奖励XP+卡片。"""
    from backend.knowledge.cards import drop_card, ensure_cards
    from backend.services.pet import add_xp, ensure_pet

    storage = get_storage()
    lock = storage.get_lock(student_id)
    async with lock:
        s = _load_student(student_id)
        now = datetime.now().isoformat(timespec="seconds")
        s.creations.append({
            "type": "problem",
            "problem": payload.problem[:500],
            "answer": payload.answer[:200],
            "judged_correct": payload.judge,
            "created_at": now,
        })

        # 出题 +10 XP + 概率掉卡
        s.pet = ensure_pet(s.pet)
        pet_feed = add_xp(s.pet, 10, source="problem_create")
        card_drop = None
        cards = ensure_cards(s.cards)
        dc = drop_card(cards, source="problem_create")
        s.cards = cards
        if dc["dropped"]:
            card_drop = dc

        storage.save(s)
        return {
            "success": True,
            "pet_feed": {
                k: pet_feed[k]
                for k in ("xp_gained", "new_exp", "leveled_up", "new_level", "unlocked_skin")
            },
            "card_drop": card_drop,
            "creations_count": len(s.creations),
        }


@app.get("/api/creations/{student_id}")
def creations_get(student_id: str):
    """11.3 作品展示墙：获取创造产物列表。"""
    s = _load_student(student_id)
    return {"creations": list(reversed(s.creations or []))}


# ---------------------------------------------------------------------------
# V3.0 P2：模块 D 闯关冒险地图 + 模块 E/F PBL（规格 6 / 7 / 8）
# ---------------------------------------------------------------------------

class AdventureEnter(BaseModel):
    level_id: str = ""


class AdventureComplete(BaseModel):
    level_id: str = ""


class PblEnter(BaseModel):
    student_id: str = ""
    level_id: int = 1


class PblComplete(BaseModel):
    student_id: str = ""
    level_id: int = 1
    score: float = 0.0
    hit: bool = False
    attempts: int = 1
    simulator_data: dict = {}


class PblChoice(BaseModel):
    student_id: str = ""
    choice_id: str = ""
    option_id: str = ""


class CustomProjectCreate(BaseModel):
    name: str = ""
    origin_interest: str = ""
    steps: list[dict] = []
    notes: str = ""


class CustomProjectStepUpdate(BaseModel):
    status: str = "done"


class CustomProjectStatusUpdate(BaseModel):
    status: str = "in_progress"


@app.get("/api/adventure/{student_id}")
def adventure_get(student_id: str):
    """6.3.1 冒险大地图：大陆分组 + 关卡状态 + 进度。"""
    from backend.knowledge.adventure_levels import ADVENTURE_LEVELS, CONTINENT_ORDER
    from backend.knowledge.cards import CARD_LIBRARY
    from backend.services.adventure_service import ensure_adventure, is_level_unlocked

    s = _load_student(student_id)
    adv = ensure_adventure(s.adventure_map)
    completed = set(adv.get("completed_levels", []))
    stars_map = adv.get("stars", {})

    continents = []
    for cname in CONTINENT_ORDER:
        levels = sorted(
            (lv for lv in ADVENTURE_LEVELS.values() if lv["continent"] == cname),
            key=lambda lv: lv["order"],
        )
        if not levels:
            continue
        c_completed = 0
        c_stars = 0
        c_stars_max = 0
        items = []
        for lv in levels:
            lid = lv["id"]
            rw = lv.get("rewards", {}) or {}
            card_id = rw.get("card")
            rarity = CARD_LIBRARY[card_id]["rarity"] if card_id and card_id in CARD_LIBRARY else None
            stars = stars_map.get(lid, 0)
            stars_max = rw.get("stars_max", 3)
            if lid in completed:
                status = "completed"
                c_completed += 1
                c_stars += stars
            elif is_level_unlocked(lv, adv):
                status = "available"
            else:
                status = "locked"
            c_stars_max += stars_max
            items.append({
                "id": lid,
                "name": lv["name"],
                "order": lv["order"],
                "type": lv["type"],
                "status": status,
                "stars": stars,
                "stars_max": stars_max,
                "rewards_preview": {
                    "xp": rw.get("xp", 0),
                    "card_rarity": rarity,
                    "badge": rw.get("badge"),
                },
            })
        continents.append({
            "name": cname,
            "levels": items,
            "progress": {
                "completed": c_completed,
                "total": len(items),
                "stars": c_stars,
                "stars_max": c_stars_max,
            },
        })

    return {
        "continents": continents,
        "current_continent": adv.get("current_continent", CONTINENT_ORDER[0]),
        "total_stars": adv.get("total_stars", 0),
    }


@app.post("/api/adventure/{student_id}/enter")
def adventure_enter(student_id: str, payload: AdventureEnter):
    """6.3.2 进入关卡（校验解锁，返回关卡定义 + 开场白）。"""
    from backend.knowledge.adventure_levels import get_level
    from backend.knowledge.syllabus import BY_ID
    from backend.services.adventure_service import ensure_adventure, is_level_unlocked

    s = _load_student(student_id)
    adv = ensure_adventure(s.adventure_map)
    level = get_level(payload.level_id)
    if level is None:
        return {"success": False, "can_enter": False, "reason": f"关卡 {payload.level_id} 不存在"}
    if not is_level_unlocked(level, adv):
        return {"success": False, "can_enter": False, "reason": "这关还没解锁，先完成前面的关卡收集星星吧～"}
    node = BY_ID.get(level["knowledge_node"])
    node_name = node.name if node else level["knowledge_node"]
    return {
        "success": True,
        "can_enter": True,
        "level": level,
        "intro_message": f"欢迎来到「{level['name']}」！这一关我们要攻克「{node_name}」，准备好了吗？",
    }


@app.post("/api/adventure/{student_id}/complete")
async def adventure_complete(student_id: str, payload: AdventureComplete):
    """6.3.3 完成关卡（掌握度达标判定 → 星级 → 奖励 → 解锁传播）。"""
    from backend.services.adventure_service import try_complete_level

    storage = get_storage()
    lock = storage.get_lock(student_id)
    async with lock:
        s = _load_student(student_id)
        result = try_complete_level(s, payload.level_id)
        if result.get("success"):
            storage.save(s)
        return result


@app.get("/api/pbl/projects")
def pbl_projects_list(student_id: str = ""):
    """7.3.1 PBL 项目列表 + 兴趣推荐。"""
    from backend.pbl.pbl_service import ensure_pbl, list_projects

    s = _load_student(student_id)
    s.pbl_projects = ensure_pbl(s.pbl_projects)
    return list_projects(s)


@app.get("/api/pbl/projects/{project_id}")
def pbl_project_detail(project_id: str, student_id: str = ""):
    """7.3.2 项目详情 + 进度。"""
    from backend.pbl.pbl_service import ensure_pbl, get_project_detail

    s = _load_student(student_id)
    s.pbl_projects = ensure_pbl(s.pbl_projects)
    detail = get_project_detail(s, project_id)
    if not detail:
        raise HTTPException(status_code=404, detail="项目不存在")
    return detail


@app.post("/api/pbl/projects/{project_id}/enter")
async def pbl_enter(project_id: str, payload: PblEnter):
    """7.3.3 进入项目关卡。"""
    from backend.pbl.pbl_service import ensure_pbl, enter_level

    sid = payload.student_id or ""
    if not sid:
        raise HTTPException(status_code=400, detail="缺少 student_id")
    storage = get_storage()
    lock = storage.get_lock(sid)
    async with lock:
        s = _load_student(sid)
        s.pbl_projects = ensure_pbl(s.pbl_projects)
        result = enter_level(s, project_id, payload.level_id)
        if result.get("success"):
            storage.save(s)
        return result


@app.post("/api/pbl/projects/{project_id}/complete")
async def pbl_complete(project_id: str, payload: PblComplete):
    """7.3.4 完成关卡（命中判定 → 星级 → 奖励 → 知识回溯）。"""
    from backend.pbl.pbl_service import complete_level, ensure_pbl

    sid = payload.student_id or ""
    if not sid:
        raise HTTPException(status_code=400, detail="缺少 student_id")
    storage = get_storage()
    lock = storage.get_lock(sid)
    async with lock:
        s = _load_student(sid)
        s.pbl_projects = ensure_pbl(s.pbl_projects)
        result = complete_level(s, project_id, payload.level_id, payload.score, payload.hit, payload.attempts)
        if result.get("success"):
            storage.save(s)
        return result


@app.get("/api/pbl/projects/{project_id}/levels/{level_id}/knowledge")
def pbl_knowledge(project_id: str, level_id: int, student_id: str = ""):
    """8.6 知识回溯：知识点 + 掌握度前后对比。"""
    from backend.pbl.pbl_service import project_knowledge

    s = _load_student(student_id)
    return project_knowledge(s, project_id, level_id)


@app.get("/api/pbl/projects/{project_id}/pending-choice")
def pbl_pending_choice(project_id: str, student_id: str = ""):
    """11.7 剧情选择：查询当前待处理的选择点。"""
    from backend.pbl.pbl_service import ensure_pbl, get_pending_choice

    s = _load_student(student_id)
    s.pbl_projects = ensure_pbl(s.pbl_projects)
    return {"pending_choice": get_pending_choice(s, project_id)}


@app.post("/api/pbl/projects/{project_id}/choice")
async def pbl_answer_choice(project_id: str, payload: PblChoice):
    """11.7 剧情选择：记录选择并返回引导话术。"""
    from backend.pbl.pbl_service import answer_choice, ensure_pbl

    sid = payload.student_id or ""
    if not sid:
        raise HTTPException(status_code=400, detail="缺少 student_id")
    storage = get_storage()
    lock = storage.get_lock(sid)
    async with lock:
        s = _load_student(sid)
        s.pbl_projects = ensure_pbl(s.pbl_projects)
        result = answer_choice(s, project_id, payload.choice_id, payload.option_id)
        if result.get("success"):
            storage.save(s)
        return result


@app.post("/api/custom-projects/{student_id}")
async def custom_project_create(student_id: str, payload: CustomProjectCreate):
    """9.4.1 创建共创项目（第 4 步完成后调用）。"""
    from backend.pbl.co_creation import create_custom_project

    storage = get_storage()
    lock = storage.get_lock(student_id)
    async with lock:
        s = _load_student(student_id)
        result = create_custom_project(s, payload.name, payload.origin_interest, payload.steps, payload.notes)
        if result.get("success"):
            storage.save(s)
        return result


@app.get("/api/custom-projects/{student_id}")
def custom_projects_list(student_id: str):
    """9.4.2 获取共创项目列表。"""
    from backend.pbl.co_creation import list_custom_projects

    s = _load_student(student_id)
    return list_custom_projects(s)


@app.post("/api/custom-projects/{student_id}/{project_id}/steps/{step_id}")
async def custom_project_step_update(student_id: str, project_id: str, step_id: int, payload: CustomProjectStepUpdate):
    """9.4.3 更新共创项目步骤状态（标记 done 后解锁下一步）。"""
    from backend.pbl.co_creation import update_step_status

    storage = get_storage()
    lock = storage.get_lock(student_id)
    async with lock:
        s = _load_student(student_id)
        result = update_step_status(s, project_id, step_id, payload.status)
        if result.get("success"):
            storage.save(s)
        return result


@app.post("/api/custom-projects/{student_id}/{project_id}/status")
async def custom_project_status_update(student_id: str, project_id: str, payload: CustomProjectStatusUpdate):
    """9.4.4 更新共创项目状态（完成/放弃/进行中）。"""
    from backend.pbl.co_creation import update_project_status

    storage = get_storage()
    lock = storage.get_lock(student_id)
    async with lock:
        s = _load_student(student_id)
        result = update_project_status(s, project_id, payload.status)
        if result.get("success"):
            storage.save(s)
        return result


# ---------------------------------------------------------------------------
# 静态前端（挂载在最后，避免拦截 /api）
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIR), html=True), name="frontend")
