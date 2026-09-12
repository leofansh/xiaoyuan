"""V3.0 P3 模块 G：兴趣共创机制。

通过对话了解孩子的兴趣，和孩子一起设计一个属于她自己的 PBL 项目。
共创五步法：兴趣唤醒(SELECT) → 兴趣聚焦(FOCUS) → 数学转化(MATH) →
项目规划(PLAN) → 逐步实现(DO)。

本模块包含三部分：
1. 五步法话术库（规格 9.3）+ 兴趣→数学映射库（规格 9.7）
2. 解释性流程状态机（规格 9.3）：孩子任何回答都能落到某一步，绝不抛异常
3. 共创项目 CRUD 核心逻辑（规格 9.4）：创建/列表/步骤更新/状态更新

纯业务逻辑，不引入数据库、不读写磁盘；所有项目写入学生档案的
``student.custom_projects`` 字段（规格 9.2）。磁盘写入由调用方
（backend/main.py）通过 ``storage.save(student)`` 完成。
"""

from __future__ import annotations

import random
import re
from datetime import datetime


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# 五步法状态机（规格 9.3）：SELECT → FOCUS → MATH → PLAN → DO
# ---------------------------------------------------------------------------

CO_CREATION_STEPS: list[str] = ["SELECT", "FOCUS", "MATH", "PLAN", "DO"]

CO_CREATION_STATE_PREFIX = "CO_CREATION_"


def state_name(step: str) -> str:
    """返回会话状态机中表示共创流程的 state 字符串。"""
    return f"{CO_CREATION_STATE_PREFIX}{step}"


def step_from_state(state: str | None) -> str:
    """从 state 字符串反解共创步骤；非共创状态返回空串。"""
    if state and state.startswith(CO_CREATION_STATE_PREFIX):
        return state[len(CO_CREATION_STATE_PREFIX):]
    return ""


def is_co_creation_state(state: str | None) -> bool:
    """判断当前会话是否处于共创流程中。"""
    return bool(step_from_state(state))


# ---------------------------------------------------------------------------
# 第 1 步：兴趣唤醒（SELECT）话术库（规格 9.3）
# ---------------------------------------------------------------------------

STEP1_OPENERS: list[str] = [
    "你最近对什么感兴趣呀？有没有什么想搞明白的问题？",
    "今天不想学课本上的东西？没关系，我们来玩点别的。你平时最喜欢做什么？",
    "小圆最近在想一个问题：数学到底能用来干嘛？你有没有遇到过什么事，觉得'要是会数学就好了'？",
]

# (关键词列表, 应对话术, 是否进入第 2 步, 强制兴趣)
STEP1_RESPONSES: list[tuple[list[str], str, bool, str | None]] = [
    (
        ["不知道", "想不出", "没想过", "我也不", "不清楚", "想不到"],
        "没关系，我们慢慢想。你可以想想：游戏、运动、音乐、美食、科学、动物……哪个你最想多了解？",
        False,
        None,
    ),
    (
        ["没什么", "没特别", "没意思", "一般般", "还行", "无所谓", "没有吧"],
        "那你昨天或周末做了什么？有没有什么觉得有意思的事？",
        False,
        None,
    ),
    (
        ["都不喜欢", "什么都不喜欢", "没兴趣", "不喜欢", "都讨厌", "烦死了"],
        "那我们来研究一个终极问题：怎么用最少的时间完成作业，剩下的时间都用来玩？",
        True,
        "睡觉/摆烂",
    ),
]

# ---------------------------------------------------------------------------
# 第 2 步：兴趣聚焦（FOCUS）话术库（规格 9.3）
# ---------------------------------------------------------------------------

STEP2_SCRIPTS: list[str] = [
    "{interest}里你最喜欢哪部分？是打怪升级？建房子？还是赚钱买装备？",
    "你有没有在{interest}里遇到过什么算不明白的事？比如不知道该买哪个更划算？",
    "如果让你用数学解决{interest}里的一个问题，你最想解决什么？",
]

# ---------------------------------------------------------------------------
# 第 3 步：数学转化（MATH）话术库（规格 9.3）
# ---------------------------------------------------------------------------

STEP3_SCRIPTS: list[str] = [
    "那我们来算一算，怎么解决你刚才说的这个问题？",
    "这个问题需要知道：每种方案需要多少？花多少时间？有没有更优的组合？",
    "你觉得，要解决这个问题，我们需要先知道什么？",
]

# ---------------------------------------------------------------------------
# 第 4 步：项目规划（PLAN）话术（规格 9.3）
# ---------------------------------------------------------------------------

STEP4_PLAN_TEMPLATE = (
    "我们把这个项目分成几步：\n"
    "第一步：先搞清楚现在的情况（数据收集+统计）\n"
    "第二步：算一算关键的比较（比和比例）\n"
    "第三步：找出最优的方案（方程+优化）\n"
    "第四步：验证一下，按这个方案真的更好吗？（实验验证）\n\n"
    "你觉得这个计划怎么样？要不要调整？"
)

# ---------------------------------------------------------------------------
# 第 5 步：逐步实现（DO）规则（规格 9.3）
# ---------------------------------------------------------------------------

STEP5_RULES: list[str] = [
    "每一步相当于一个关卡，完成后标记完成，进入下一步",
    "我在每一步提供你需要的数学支持，按需讲解，不系统灌输",
    "完成一步就庆祝、记录，然后进入下一步",
    "项目可以暂停、放弃，我不会批评你",
]

STEP5_VARIANTS: list[str] = [
    "我们一步一步来，不着急。你觉得现在这一步可以开始了吗？还是想先聊聊？",
    "这一步是你想出来的，我们来把它做完，做不完也没关系，随时可以暂停。",
    "有问题就问我，需要哪个知识点我帮你补哪个，不用一次性全学。",
]


def _select_opener() -> str:
    return random.choice(STEP1_OPENERS)


def _focus_opener(interest: str | None) -> str:
    """第 2 步开场：聚焦兴趣，附上该兴趣可转化的数学问题启发。"""
    interest = interest or "这个"
    base = random.choice(STEP2_SCRIPTS).format(interest=interest)
    examples = _interest_examples(interest)
    if examples:
        base += "\n比如：" + "、".join(examples[:3]) + "。"
    return base


def _math_opener(interest: str | None) -> str:
    return random.choice(STEP3_SCRIPTS)


def _plan_opener(interest: str | None) -> str:
    return STEP4_PLAN_TEMPLATE


def _do_opener(interest: str | None) -> str:
    return (
        "太棒了！这个项目是你自己想出来的🌟 我们现在开始第一步，"
        "一步一步来，每完成一步就庆祝一次！\n" + random.choice(STEP5_VARIANTS)
    )


# ---------------------------------------------------------------------------
# 兴趣 → 数学映射库（规格 9.7）：≥11 类兴趣，每类 ≥3 个问题示例
# ---------------------------------------------------------------------------

INTEREST_MATH_MAP: dict[str, dict] = {
    "游戏/电竞": {
        "keywords": ["游戏", "电竞", "王者", "吃鸡", "原神", "我的世界", "打游戏", "手游"],
        "examples": ["最快赚金币", "装备性价比", "暴击率计算", "段位胜率", "抽卡概率"],
        "math_knowledge": ["统计", "比和比例", "概率", "方程"],
    },
    "动漫/追番": {
        "keywords": ["动漫", "动画", "追番", "漫画", "番剧", "二次元", "cos"],
        "examples": ["追完一部要多久", "更新频率", "播放时长统计", "人物身高比例", "追番时间表"],
        "math_knowledge": ["统计", "平均数", "比例", "时间计算"],
    },
    "篮球/体育": {
        "keywords": ["篮球", "足球", "体育", "运动", "打球", "跑步", "游泳", "羽毛球", "乒乓球"],
        "examples": ["命中率", "场均得分", "罚球命中率", "赛程积分", "球员效率"],
        "math_knowledge": ["统计", "百分比", "平均数", "比和比例"],
    },
    "音乐/乐器": {
        "keywords": ["音乐", "乐器", "钢琴", "吉他", "唱歌", "歌", "跳舞", "舞蹈", "节拍"],
        "examples": ["节拍计算", "音高频率", "和弦数学", "练习时间规划", "歌单时长"],
        "math_knowledge": ["分数", "比例", "统计", "时间计算"],
    },
    "美食/烘焙": {
        "keywords": ["美食", "烘焙", "做饭", "做菜", "蛋糕", "甜品", "吃", "奶茶", "点心"],
        "examples": ["配方换算", "烘焙时间", "成本计算", "营养比例", "温度转换"],
        "math_knowledge": ["比和比例", "分数", "四则运算", "单位换算"],
    },
    "宠物/动物": {
        "keywords": ["宠物", "动物", "猫", "狗", "仓鼠", "兔子", "养"],
        "examples": ["喂养量", "年龄换算", "成长曲线", "用品预算", "食量统计"],
        "math_knowledge": ["统计", "比例", "函数", "四则运算"],
    },
    "旅行/出门": {
        "keywords": ["旅行", "旅游", "出门", "出去玩", "度假", "露营", "景点"],
        "examples": ["路程时间速度", "汇率", "酒店预算", "行程规划", "门票性价比"],
        "math_knowledge": ["速度时间路程", "比和比例", "统计", "四则运算"],
    },
    "数码/科技": {
        "keywords": ["数码", "科技", "手机", "电脑", "平板", "无人机", "机器人", "编程"],
        "examples": ["电池续航", "像素", "存储容量", "网速", "性价比对比"],
        "math_knowledge": ["单位换算", "比例", "百分比", "四则运算"],
    },
    "睡觉/摆烂": {
        "keywords": ["睡觉", "摆烂", "躺平", "摸鱼", "偷懒", "不想动", "发呆"],
        "examples": ["睡眠周期", "最佳入睡时间", "时间管理", "如何最少时间完成作业", "休息规划"],
        "math_knowledge": ["统计", "时间计算", "优化", "比例"],
    },
    "赚钱/零花钱": {
        "keywords": ["赚钱", "零花钱", "钱", "攒钱", "存钱", "省钱", "打工"],
        "examples": ["攒钱计划", "折扣计算", "理财收益", "预算分配", "比价"],
        "math_knowledge": ["百分数", "比和比例", "统计", "方程"],
    },
    "画画/美术": {
        "keywords": ["画画", "美术", "绘画", "素描", "涂鸦", "手工", "设计"],
        "examples": ["画面比例", "对称构图", "颜料配比", "画纸缩放", "透视角度"],
        "math_knowledge": ["比例", "几何", "对称", "分数"],
    },
}


def _interest_examples(interest: str | None) -> list[str]:
    info = INTEREST_MATH_MAP.get(interest or "")
    return list(info["examples"]) if info else []


def detect_interest(message: str | None) -> str | None:
    """从孩子的话里识别兴趣类别；识别不到返回 None。"""
    if not message:
        return None
    for name, info in INTEREST_MATH_MAP.items():
        if any(kw in message for kw in info["keywords"]):
            return name
    return None


# ---------------------------------------------------------------------------
# 共创意图识别（规格 9.6 集成点：chat.py 在 MODE_SELECT 状态调用）
# ---------------------------------------------------------------------------

# 共创"创作对象"名词：用于约束"做/一起做/我想做"等模糊动词，避免把
# "我想做数学题""一起做作业"误判为共创意图（规格 9.6）。
_CO_CREATION_OBJECT = r"(游戏|项目|东西|小游戏|小程序|玩具|作品|手工|机器人|玩意儿)"

CO_CREATION_INTENT_PATTERNS: list[str] = [
    r"自己设计",
    r"一起设计",
    r"我想设计",
    r"设计个",
    r"设计一个.*" + _CO_CREATION_OBJECT,
    r"创造",
    r"创作",
    r"做(一?个?|点)?" + _CO_CREATION_OBJECT,
    r"一起做(一?个?|点)?" + _CO_CREATION_OBJECT,
    r"我想做(一?个?|点)?" + _CO_CREATION_OBJECT,
]

_CO_CREATION_INTENT_RE = [re.compile(p) for p in CO_CREATION_INTENT_PATTERNS]

# 无兴趣/不知道该学什么的表达（规格 9.6 + 验收 1319-1320）：
# 这类孩子从 MODE_SELECT 直接进入共创 SELECT 步，由 STEP1_RESPONSES 提供
# 选项启发；若说"什么都不喜欢"，由 start_co_creation 直接转化为
# "最少时间完成作业"项目。
DISINTEREST_PHRASES: list[str] = [
    "没兴趣",
    "没什么兴趣",
    "提不起兴趣",
    "不知道学什么",
    "不知道喜欢什么",
    "不知道干嘛",
    "什么都不喜欢",
    "都不喜欢",
    "不喜欢学习",
    "不喜欢学",
    "不想学",
    "不太想学",
]


def detect_co_creation_intent(message: str | None) -> bool:
    """识别孩子是否想自己动手共创一个项目，或正处于"没兴趣"状态需要引导。

    两类触发：
    1. 主动创作动词（设计/创造/创作/做…东西）
    2. 无兴趣表达（没兴趣/不知道学什么/什么都不喜欢）——路由到共创流程的
       SELECT 步，由话术库提供选项启发或转化为项目（规格 9.6、9.3）。
    """
    if not message:
        return False
    if any(p.search(message) for p in _CO_CREATION_INTENT_RE):
        return True
    return any(k in message for k in DISINTEREST_PHRASES)


# ---------------------------------------------------------------------------
# 解释性流程状态机（规格 9.3）：任何输入都落到某一步，绝不抛异常
# ---------------------------------------------------------------------------


def start_co_creation(message: str | None = None) -> dict:
    """进入共创流程：返回初始状态 + 开场话术。

    根据触发语三态分流（规格 9.6/9.3）：
    1. 已带可识别兴趣（"我就想打游戏"）→ 直接进 FOCUS，不重复问兴趣；
    2. 说"什么都不喜欢/都不喜欢" → 直接转化为"最少时间完成作业"项目；
    3. 说"不知道/没意思" → 留在 SELECT，直接给选项启发话术；
    4. 其余（主动创作动词）→ SELECT 开场话术。
    """
    msg = message or ""

    detected = detect_interest(msg)
    if detected:
        return {
            "step": "FOCUS",
            "state": state_name("FOCUS"),
            "reply": _focus_opener(detected),
            "phase_changed": True,
            "interest": detected,
        }
    for keywords, reply, advance, forced_interest in STEP1_RESPONSES:
        if any(k in msg for k in keywords):
            if advance:
                return {
                    "step": "FOCUS",
                    "state": state_name("FOCUS"),
                    "reply": reply,
                    "phase_changed": True,
                    "interest": forced_interest or "睡觉/摆烂",
                }
            # "不知道/没意思"类：留在 SELECT，直接给选项启发，不批评不催促
            return {
                "step": "SELECT",
                "state": state_name("SELECT"),
                "reply": reply,
                "phase_changed": False,
                "interest": None,
            }
    return {
        "step": "SELECT",
        "state": state_name("SELECT"),
        "reply": _select_opener(),
        "phase_changed": False,
        "interest": None,
    }


def advance_co_creation(step: str | None, message: str | None,
                        interest: str | None = None) -> dict:
    """推进共创流程：根据当前步骤和孩子回答返回下一步 + 应说的话术。

    解释性设计：任何回答都会被落到某一步，未匹配时重复话术变体，绝不抛异常。
    返回字典：{step, state, reply, phase_changed, interest}
    """
    step = step or "SELECT"
    if step not in CO_CREATION_STEPS:
        step = "SELECT"
    msg = message or ""

    if step == "SELECT":
        detected = detect_interest(msg)
        if detected:
            return {
                "step": "FOCUS",
                "state": state_name("FOCUS"),
                "reply": _focus_opener(detected),
                "phase_changed": True,
                "interest": detected,
            }
        for keywords, reply, advance, forced_interest in STEP1_RESPONSES:
            if any(k in msg for k in keywords):
                if advance:
                    nxt_interest = forced_interest or interest
                    return {
                        "step": "FOCUS",
                        "state": state_name("FOCUS"),
                        "reply": _focus_opener(nxt_interest),
                        "phase_changed": True,
                        "interest": nxt_interest,
                    }
                return {
                    "step": "SELECT",
                    "state": state_name("SELECT"),
                    "reply": reply,
                    "phase_changed": False,
                    "interest": interest,
                }
        # 未匹配 → 重复话术变体，继续唤醒兴趣
        return {
            "step": "SELECT",
            "state": state_name("SELECT"),
            "reply": _select_opener(),
            "phase_changed": False,
            "interest": interest,
        }

    if step == "FOCUS":
        return {
            "step": "MATH",
            "state": state_name("MATH"),
            "reply": _math_opener(interest),
            "phase_changed": True,
            "interest": interest,
        }

    if step == "MATH":
        return {
            "step": "PLAN",
            "state": state_name("PLAN"),
            "reply": _plan_opener(interest),
            "phase_changed": True,
            "interest": interest,
        }

    if step == "PLAN":
        return {
            "step": "DO",
            "state": state_name("DO"),
            "reply": _do_opener(interest),
            "phase_changed": True,
            "interest": interest,
        }

    # DO：逐步实现（复用 PBL 框架），保持解释性
    return {
        "step": "DO",
        "state": state_name("DO"),
        "reply": random.choice(STEP5_VARIANTS),
        "phase_changed": False,
        "interest": interest,
    }


# ---------------------------------------------------------------------------
# 共创项目 CRUD 核心逻辑（规格 9.4）
# ---------------------------------------------------------------------------


def ensure_custom_projects(raw) -> list[dict]:
    """确保 custom_projects 为 list。原地返回同一对象（懒初始化）。"""
    if not isinstance(raw, list):
        return []
    return raw


def _new_project_id(existing: list[dict]) -> str:
    """生成项目 id：custom_ 前缀 + 时间戳 + 序号（避免碰撞）。"""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    seq = 1
    existing_ids = {p.get("id") for p in existing if isinstance(p, dict)}
    while f"custom_{stamp}_{seq}" in existing_ids:
        seq += 1
    return f"custom_{stamp}_{seq}"


def _build_steps(raw_steps) -> list[dict]:
    """把前端传入的 steps[{name, description, math_knowledge}] 转为带 id/status 的步骤。

    第一步置为 in_progress，其余 pending（规格 9.3：保存后第一步为 in_progress）。
    """
    steps: list[dict] = []
    for idx, raw in enumerate(raw_steps or [], start=1):
        if not isinstance(raw, dict):
            continue
        steps.append({
            "id": idx,
            "name": raw.get("name") or f"第{idx}步",
            "description": raw.get("description") or "",
            "math_knowledge": list(raw.get("math_knowledge") or []),
            "status": "in_progress" if idx == 1 else "pending",
            "completed_at": None,
        })
    return steps


def _find_project(projects: list[dict], project_id: str) -> dict | None:
    for p in projects:
        if isinstance(p, dict) and p.get("id") == project_id:
            return p
    return None


def _find_step(project: dict, step_id: int) -> dict | None:
    for s in project.get("steps", []):
        if isinstance(s, dict) and s.get("id") == step_id:
            return s
    return None


def _all_steps_done(project: dict) -> bool:
    steps = project.get("steps", [])
    return bool(steps) and all(s.get("status") == "done" for s in steps)


def create_custom_project(student, name: str, origin_interest: str,
                          steps, notes: str = "") -> dict:
    """创建共创项目（规格 9.4.1）。"""
    projects = ensure_custom_projects(getattr(student, "custom_projects", None))
    student.custom_projects = projects

    pid = _new_project_id(projects)
    project = {
        "id": pid,
        "name": name or "我的共创项目",
        "origin_interest": origin_interest or "",
        "created_at": _now(),
        "status": "in_progress",
        "steps": _build_steps(steps),
        "notes": notes or "",
        "completed_at": None,
    }
    projects.append(project)
    return {"success": True, "project_id": pid, "project": project}


def list_custom_projects(student) -> dict:
    """获取共创项目列表（规格 9.4.2）。

    响应带 success 包装，与 9.4.1/9.4.3/9.4.4 一致；前端读取
    ``data.projects``（见 frontend/js/co-creation.js loadProjects）。
    """
    projects = ensure_custom_projects(getattr(student, "custom_projects", None))
    student.custom_projects = projects
    return {"success": True, "projects": projects, "custom_projects": projects}


def update_step_status(student, project_id: str, step_id: int, status: str) -> dict:
    """更新共创项目步骤状态（规格 9.4.3）：标记 done 后解锁下一步。"""
    projects = ensure_custom_projects(getattr(student, "custom_projects", None))
    student.custom_projects = projects

    project = _find_project(projects, project_id)
    if project is None:
        return {"success": False, "message": "项目不存在"}
    step = _find_step(project, step_id)
    if step is None:
        return {"success": False, "message": "步骤不存在"}

    step["status"] = status
    next_step_unlocked = False
    if status == "done":
        step["completed_at"] = _now()
        nxt = _find_step(project, step_id + 1)
        if nxt is not None and nxt.get("status") == "pending":
            nxt["status"] = "in_progress"
            next_step_unlocked = True
        if _all_steps_done(project):
            project["status"] = "completed"
            project["completed_at"] = _now()

    return {
        "success": True,
        "step": step,
        "next_step_unlocked": next_step_unlocked,
    }


def update_project_status(student, project_id: str, status: str) -> dict:
    """更新共创项目状态（规格 9.4.4）：completed/abandoned/in_progress。"""
    projects = ensure_custom_projects(getattr(student, "custom_projects", None))
    student.custom_projects = projects

    project = _find_project(projects, project_id)
    if project is None:
        return {"success": False, "message": "项目不存在"}
    if status not in ("completed", "abandoned", "in_progress"):
        return {"success": False, "message": "无效状态"}

    project["status"] = status
    if status == "completed":
        project["completed_at"] = _now()
        for s in project.get("steps", []):
            s["status"] = "done"
            if not s.get("completed_at"):
                s["completed_at"] = _now()
    elif status == "abandoned":
        # 放弃不批评、不扣分（规格 9.3/9.8）
        pass
    elif status == "in_progress":
        project["completed_at"] = None

    return {"success": True, "project": project}
