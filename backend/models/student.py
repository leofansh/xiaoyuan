from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class Gap(BaseModel):
    topic_id: str
    topic_name: str = ""
    type: Literal["concept", "careless"] = "concept"
    # B2：精细分类
    category: str = "unknown"        # 见 GAP_CATEGORIES（error_patterns.py）
    root_cause: str = ""             # 根因描述
    repair_strategy: str = ""        # 修复策略
    evidence: str = ""
    status: Literal["open", "cleared", "recurring"] = "open"
    first_detected: str = ""
    last_occurred: str = ""
    occurrence_count: int = 1
    found_at: str = ""
    cleared_at: str | None = None


class ErrorReview(BaseModel):
    date: str
    q1_answer: str  # 卡壳在哪一步
    q2_answer: str  # 思维漏洞是什么
    error_type: Literal["concept", "careless"] = "concept"
    topic_id: str = ""


class SessionState(BaseModel):
    mode: Literal["A", "B", "weekend"] | None = None
    state: str = "GREETING"  # 状态机当前节点
    started_at: str = ""
    topic_id: str = ""
    history: list[dict[str, str]] = Field(default_factory=list)  # [{role, content}]
    turn_count: int = 0
    blind_spots_today: list[str] = Field(default_factory=list)
    errors_reviewed: int = 0
    # 确定性状态引擎追踪字段（A1）
    consecutive_correct: int = 0        # 当前状态内连续正确数
    consecutive_wrong: int = 0          # 当前状态内连续错误数
    turns_in_current_state: int = 0     # 当前状态停留轮数（熔断用）
    last_error_type: str = ""           # 最近一轮错误类型（careless/concept/formula/steps/reading）


class SessionSummary(BaseModel):
    date: str  # 会话结束日期 ISO
    mode: str = ""  # A/B/weekend
    mood: str = ""  # 开场心情
    topic_id: str = ""
    topic_name: str = ""  # 从 syllabus 解析的名称
    turns: int = 0
    blind_spots: list[str] = Field(default_factory=list)
    new_badges: list[str] = Field(default_factory=list)
    duration_minutes: int = 0
    messages: list[dict[str, str]] = Field(default_factory=list)  # [{role, content}]


class StudentProfile(BaseModel):
    """跨会话记忆：从历史数据自动提取的学生画像。"""
    historical_blind_spots: list[str] = Field(default_factory=list)  # 历史盲区（去重）
    mastered_topics: list[str] = Field(default_factory=list)         # 已掌握知识点名
    pending_blind_spots: list[str] = Field(default_factory=list)     # 待修复盲区
    mood_pattern: str = ""        # 情绪模式摘要，如"多数时候😊，偶尔😣"
    preferred_mode: str = ""      # 常用模式，如"深度成长"
    last_session_topic: str = ""  # 上次话题
    last_session_date: str = ""   # 上次日期
    updated_at: str = ""          # 画像更新时间
    metacognition_level: float = 0.0          # 元认知能力评分（0~1）
    strategy_use: dict[str, int] = Field(default_factory=dict)  # 各元认知策略使用次数
    independent_success_rate: float = 0.0     # 独立做对比例
    anxiety_pattern: str = ""                 # 焦虑模式描述


class CognitiveProfile(BaseModel):
    """认知发展画像：动态评估学生的认知水平，驱动教学策略适配。"""
    # 1. 认知阶段
    cognitive_stage: Literal["concrete", "transitional", "formal"] = "concrete"

    # 2. 工作记忆容量
    working_memory_capacity: Literal["low", "medium", "high"] = "medium"

    # 3. 抽象思维能力（0-1）
    abstract_thinking: float = 0.3

    # 4. 元认知能力（0-1）
    metacognition_level: float = 0.2

    # 5. 执行功能
    executive_function: dict[str, float] = Field(default_factory=lambda: {
        "inhibition": 0.5,   # 抑制控制（忍住不跳步/粗心）
        "flexibility": 0.4,  # 认知灵活性（换方法解题）
    })

    # 6. 数学焦虑（0-1）
    math_anxiety: float = 0.2
    anxiety_triggers: list[str] = Field(default_factory=list)  # 触发场景

    # 7. 学习偏好
    learning_preference: Literal["visual", "verbal", "kinesthetic"] = "visual"

    # 8. 分领域认知水平（代数/几何/数论/统计...）
    domain_levels: dict[str, float] = Field(default_factory=dict)

    # 9. 评估元信息
    assessed_at: str = ""          # 初始评估时间
    last_updated: str = ""         # 动态更新时间
    last_assessed: str = ""        # 最后评估/更新认知画像时间（B3 衰减依据）
    assessment_confidence: float = 0.0  # 画像置信度（随数据积累提升）


class ReviewSchedule(BaseModel):
    """间隔复习调度：追踪每个知识点的复习时间线。"""
    topic_id: str
    topic_name: str = ""
    next_review: str = ""       # 下次复习日期 ISO
    interval_days: int = 1      # 当前间隔天数
    review_count: int = 0       # 已复习次数
    last_reviewed: str = ""     # 上次复习日期 ISO
    mastery_at_schedule: float = 0.0  # 调度时的掌握度


class TeachingInsight(BaseModel):
    """教学洞察：从每次对话中提取的经验教训。"""
    date: str = ""              # 洞察生成日期
    category: str = ""          # trust/strategy/emotion/communication
    insight: str = ""           # 具体洞察内容
    what_worked: str = ""       # 什么方法有效
    what_failed: str = ""       # 什么方法无效
    student_style: str = ""     # 学生的学习风格观察


class MasteryRecord(BaseModel):
    """贝叶斯掌握度记录（架构优化 B1）。

    用"观测样本"而非"单一分数"描述掌握度：
    - score: 后验掌握度估计 0~1（由正确率与先验融合）
    - confidence: 置信度 0~1（随观测次数增长，越少数据越不可信）
    - attempts_correct/total: 累计答题样本（用于贝叶斯更新与遗忘衰减）
    - last_interaction: 最近一次与该知识点交互日期 ISO（遗忘衰减依据）
    """

    score: float = 0.0
    confidence: float = 0.0
    attempts_correct: int = 0
    attempts_total: int = 0
    last_interaction: str = ""


class Student(BaseModel):
    id: str
    name: str
    grade: int = 6
    textbook: str = "沪教版五四制2024"
    created_at: str = ""
    last_active: str = ""

    mastery: dict[str, MasteryRecord] = Field(default_factory=dict)  # {知识点id: MasteryRecord}
    gaps: list[Gap] = Field(default_factory=list)
    error_reviews: list[ErrorReview] = Field(default_factory=list)

    streak_chain: int = 0
    streak_last_date: str | None = None
    week_baseline_count: int = 0
    mode_history: list[dict[str, str]] = Field(default_factory=list)

    mood_checkins: list[dict[str, str]] = Field(default_factory=list)
    confidence_trend: list[dict[str, Any]] = Field(default_factory=list)

    badges: list[str] = Field(default_factory=list)
    total_sessions: int = 0
    session_history: list[SessionSummary] = Field(default_factory=list)
    student_profile: StudentProfile = Field(default_factory=StudentProfile)
    cognitive_profile: CognitiveProfile = Field(default_factory=CognitiveProfile)
    review_schedules: list[ReviewSchedule] = Field(default_factory=list)
    teaching_journal: list[TeachingInsight] = Field(default_factory=list)
    cognitive_assessment_answers: list[dict[str, Any]] = Field(default_factory=list)  # 认知评估答题记录
    thinking_model_mastery: dict[str, float] = Field(default_factory=dict)  # 思维模型掌握度 {模型ID: 0.0~1.0}
    crisis_events: list[dict[str, Any]] = Field(default_factory=list)  # 心理危机事件记录
    interests: list[str] = Field(default_factory=list)          # 兴趣爱好列表，如 ["烘焙", "游戏"]
    preferences: dict[str, str] = Field(default_factory=dict)   # 偏好设置，如 {"favorite_metaphor": "烘焙"}

    current_session: SessionState = Field(default_factory=SessionState)

    def open_gaps(self) -> list[Gap]:
        return [g for g in self.gaps if g.status in ("open", "recurring")]

    def concept_gaps_open(self) -> list[Gap]:
        return [g for g in self.gaps if g.status in ("open", "recurring") and g.type == "concept"]

    def avg_mastery(self) -> float:
        if not self.mastery:
            return 0.0
        return sum(rec.score for rec in self.mastery.values()) / len(self.mastery)

    def mastery_score(self, topic_id: str, default: float = 0.0) -> float:
        """取某知识点掌握度分数（对 float 字典调用点友好的辅助方法，B1）。"""
        rec = self.mastery.get(topic_id)
        return rec.score if rec else default

    def mastery_confidence(self, topic_id: str, default: float = 0.0) -> float:
        """取某知识点置信度（B1）。"""
        rec = self.mastery.get(topic_id)
        return rec.confidence if rec else default

    def today_iso(self) -> str:
        return date.today().isoformat()

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_mastery(cls, data: Any) -> Any:
        """把旧格式数据迁移为新格式（B1 掌握度 + B2 漏洞分类）。"""
        if isinstance(data, dict):
            # B1：mastery {tid: float} → {tid: MasteryRecord}
            mastery = data.get("mastery")
            if isinstance(mastery, dict) and mastery and all(isinstance(v, (int, float)) for v in mastery.values()):
                today = date.today().isoformat()
                data["mastery"] = {
                    tid: {
                        "score": float(v),
                        "confidence": 0.5,
                        "attempts_correct": 1,
                        "attempts_total": 1,
                        "last_interaction": today,
                    }
                    for tid, v in mastery.items()
                }
            # B2：旧 Gap 补全 category/root_cause/repair_strategy
            gaps = data.get("gaps")
            if isinstance(gaps, list):
                legacy_map = {"concept": "concept_misunderstanding", "careless": "careless_general"}
                for g in gaps:
                    if isinstance(g, dict) and not g.get("category"):
                        gtype = g.get("type", "concept")
                        g["category"] = legacy_map.get(gtype, "unknown")
                        g.setdefault("root_cause", "")
                        g.setdefault("repair_strategy", "")
                        g.setdefault("first_detected", g.get("found_at", ""))
                        g.setdefault("last_occurred", g.get("found_at", ""))
                        g.setdefault("occurrence_count", 1)
        return data


class Badge:
    BLIND_HUNTER = "🔍 盲区猎手"
    DERIVE_BRAVE = "🧗 推导小勇士"
    ERROR_DETECTIVE = "🕵️ 错题侦探"
    TRANSFER = "💎 举一反三"
    STREAK_7 = "🔗 不断链7天"
    WEEKEND_CLEAR = "🌟 清零大师"
    BASELINE_HERO = "💪 保底英雄"
    THINKING_REVERSE = "🔄 逆向思维达人"
    THINKING_VISUAL = "📐 图形化思维达人"
    THINKING_DECOMPOSE = "🧩 问题拆分达人"
    THINKING_ANALOGY = "🔗 类比思维达人"
    THINKING_TRANSFORM = "✨ 转化思维达人"
    THINKING_CASE = "📋 分类讨论达人"
    THINKING_EXTREME = "🎯 极端思维达人"
    THINKING_HOLISTIC = "🧩 整体思维达人"
    THINKING_MODELING = "📊 建模思维达人"
    THINKING_VERIFY = "✅ 检验思维达人"

    ALL: dict[str, dict[str, str]] = {
        BLIND_HUNTER: {"desc": "第一次自己说出哪里没学踏实", "icon": "🔍"},
        DERIVE_BRAVE: {"desc": "第一次独立推导出核心公式", "icon": "🧗"},
        ERROR_DETECTIVE: {"desc": "完整完成错题两问：卡壳在哪+漏洞是什么", "icon": "🕵️"},
        TRANSFER: {"desc": "第一次独立解出变式题", "icon": "💎"},
        STREAK_7: {"desc": "学习链连续7天（保底日也算哦）", "icon": "🔗"},
        WEEKEND_CLEAR: {"desc": "周末修复清零全部概念漏洞", "icon": "🌟"},
        BASELINE_HERO: {"desc": "第一次用保底模式守住底线", "icon": "💪"},
        THINKING_REVERSE: {"desc": "逆向思维掌握度达0.7", "icon": "🔄"},
        THINKING_VISUAL: {"desc": "图形化思维掌握度达0.7", "icon": "📐"},
        THINKING_DECOMPOSE: {"desc": "问题拆分掌握度达0.7", "icon": "🧩"},
        THINKING_ANALOGY: {"desc": "类比思维掌握度达0.7", "icon": "🔗"},
        THINKING_TRANSFORM: {"desc": "转化思维掌握度达0.7", "icon": "✨"},
        THINKING_CASE: {"desc": "分类讨论掌握度达0.7", "icon": "📋"},
        THINKING_EXTREME: {"desc": "极端思维掌握度达0.7", "icon": "🎯"},
        THINKING_HOLISTIC: {"desc": "整体思维掌握度达0.7", "icon": "🧩"},
        THINKING_MODELING: {"desc": "建模思维掌握度达0.7", "icon": "📊"},
        THINKING_VERIFY: {"desc": "检验思维掌握度达0.7", "icon": "✅"},
    }
