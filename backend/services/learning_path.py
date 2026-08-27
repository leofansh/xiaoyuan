"""长期学习路径规划器（架构优化 D2）。

根据学生的掌握度、漏洞、认知阶段生成周学习计划：
- 漏洞修复优先级最高
- ZPD（最近发展区）内的知识点优先级中等
- 已掌握知识点的变式提升优先级低
- 每周最多 5 个知识点，避免过载
"""

from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from backend.knowledge.syllabus import all_nodes, get_node


class LearningPlanItem(BaseModel):
    topic_id: str
    topic_name: str
    chapter: str = ""
    priority: str = "low"          # "high" / "medium" / "low"
    reason: str = ""               # 为什么学这个
    estimated_sessions: int = 1    # 预计需要几次课
    prerequisites: list[str] = Field(default_factory=list)


class LearningPlan(BaseModel):
    period: str = "weekly"
    start_date: str = ""
    end_date: str = ""
    items: list[LearningPlanItem] = Field(default_factory=list)
    total_estimated_sessions: int = 0


def _zpd_status(score: float) -> str:
    """根据掌握度判断 ZPD 状态（适配 MasteryRecord 无 zpd_status 字段）。"""
    if score < 0.25:
        return "too_hard"      # 远低于现有水平
    if score < 0.75:
        return "ready"         # 最近发展区，适合学习
    return "too_easy"          # 已掌握


def generate_weekly_plan(student) -> LearningPlan:
    """生成周学习计划。"""
    items: list[LearningPlanItem] = []
    seen: set[str] = set()

    # 1. 高优先级：修复 open 的漏洞
    for gap in student.open_gaps():
        if gap.topic_id in seen:
            continue
        node = get_node(gap.topic_id)
        if not node:
            continue
        seen.add(gap.topic_id)
        items.append(LearningPlanItem(
            topic_id=gap.topic_id,
            topic_name=node.name,
            chapter=node.chapter,
            priority="high",
            reason=f"存在知识漏洞（{gap.category}），需要修复",
            estimated_sessions=2,
            prerequisites=list(node.prerequisites),
        ))

    # 2. 中优先级：ZPD 内的知识点（掌握度 0.25-0.75）
    for node in all_nodes():
        if node.id in seen:
            continue
        rec = student.mastery.get(node.id)
        score = rec.score if rec else 0.0
        if rec and _zpd_status(score) == "ready":
            seen.add(node.id)
            items.append(LearningPlanItem(
                topic_id=node.id,
                topic_name=node.name,
                chapter=node.chapter,
                priority="medium",
                reason=f"在最近发展区内（掌握度 {score:.2f}），适合学习",
                estimated_sessions=1,
                prerequisites=list(node.prerequisites),
            ))

    # 3. 低优先级：已掌握知识点的变式提升（仅当应用不足时）
    for node in all_nodes():
        if node.id in seen:
            continue
        rec = student.mastery.get(node.id)
        if rec and _zpd_status(rec.score) == "too_easy" and rec.confidence < 0.9:
            seen.add(node.id)
            items.append(LearningPlanItem(
                topic_id=node.id,
                topic_name=node.name,
                chapter=node.chapter,
                priority="low",
                reason="基础已掌握，可做变式巩固提升",
                estimated_sessions=1,
                prerequisites=list(node.prerequisites),
            ))

    # 按优先级排序，限制本周最多 5 个知识点
    priority_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda x: priority_order.get(x.priority, 3))
    items = items[:5]

    total = sum(item.estimated_sessions for item in items)
    today = datetime.now().date()

    return LearningPlan(
        period="weekly",
        start_date=today.isoformat(),
        end_date=(today + timedelta(days=7)).isoformat(),
        items=items,
        total_estimated_sessions=total,
    )
