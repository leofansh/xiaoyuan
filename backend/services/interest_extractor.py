"""兴趣提取器 + 兴趣融入教学的规则（架构优化 C3）。

从学生对话中提取兴趣爱好，自动保存到档案；
兴趣 → 数学情境映射：把学生熟悉的兴趣融入数学教学，降低抽象概念门槛。
"""

# 兴趣关键词映射
INTEREST_KEYWORDS: dict[str, list[str]] = {
    "烘焙": ["烘焙", "烤蛋糕", "做饼干", "做面包", "做甜点", "下厨", "做饭", "做菜"],
    "游戏": ["游戏", "玩游戏", "王者荣耀", "原神", "我的世界", "迷你世界", "蛋仔派对", "光遇", "和平精英"],
    "阅读": ["看书", "阅读", "读书", "小说", "漫画", "绘本"],
    "音乐": ["唱歌", "跳舞", "钢琴", "吉他", "音乐", "听歌", "学乐器", "小提琴"],
    "运动": ["跑步", "游泳", "打球", "篮球", "足球", "羽毛球", "跳绳", "滑板", "骑行"],
    "画画": ["画画", "绘画", "素描", "水彩", "手绘", "涂鸦"],
    "动漫": ["动漫", "动画片", "看番", "二次元", "cosplay"],
    "宠物": ["养猫", "养狗", "宠物", "猫咪", "狗狗", "仓鼠", "兔子", "乌龟"],
    "旅行": ["旅行", "旅游", "出去玩", "度假", "露营", "爬山"],
    "电影": ["看电影", "电影", "追剧", "电视剧", "综艺"],
}

# C3：兴趣 → 数学情境映射
INTEREST_MATH_CONTEXTS: dict[str, dict] = {
    "烘焙": {
        "topics": ["分数", "比例", "百分比", "单位换算"],
        "contexts": [
            "做蛋糕需要按比例调配面粉和糖，面粉是糖的3倍，糖用了50g，面粉要多少克？",
            "配方是6寸的蛋糕，要改成8寸，所有材料按面积比例（4:9）放大，鸡蛋3个要几个？",
            "烤饼干配方要烤15分钟，已经烤了8分钟，还剩几分之几没烤完？",
        ],
    },
    "游戏": {
        "topics": ["概率", "统计", "四则运算", "逻辑"],
        "contexts": [
            "游戏抽卡概率是5%，抽10次至少中1次的概率是多少（用分数表示）？",
            "角色攻击力从100提升20%，提升后变成多少？",
            "游戏金币买了装备花掉3/5，还剩多少金币？",
        ],
    },
    "音乐": {
        "topics": ["分数", "比例", "数列", "周期"],
        "contexts": [
            "一首曲子4/4拍，每小节4拍，8小节一共有多少拍？",
            "音符时值：1个全音符 = 2个二分音符 = 4个四分音符，那8个八分音符呢？",
            "节拍器每分钟60拍，10分钟打多少拍？",
        ],
    },
    "运动": {
        "topics": ["速度", "距离", "时间", "统计", "平均"],
        "contexts": [
            "跑步100米用了15秒，平均每秒跑多少米？",
            "篮球比赛4节，每节10分钟，暂停5分钟，整场比赛多少分钟？",
            "进球率：投了20个中了12个，命中率是多少？",
        ],
    },
    "画画": {
        "topics": ["比例", "几何", "对称", "角度"],
        "contexts": [
            "画人像时头和身体的比例是1:7，头长3cm，身体要画多长？",
            "画一个正六边形，每个内角是多少度？",
            "调色：红色和白色按2:1混合得到粉色，要调120ml，红色要多少？",
        ],
    },
    "动漫": {
        "topics": ["比例", "速度", "逻辑", "数列"],
        "contexts": [
            "动漫角色身高是头长的7倍，头长20cm，身高是多少cm？",
            "动画片每集20分钟，看了5集，一共看了多少分钟？",
            "变身序列：第1集出现1个敌人，第2集2个，按这个规律第10集出现几个？",
        ],
    },
    "宠物": {
        "topics": ["四则运算", "比例", "百分比", "时间"],
        "contexts": [
            "猫粮每天喂3次，每次50g，一袋2kg的猫粮能吃几天？",
            "狗狗体重从5kg长到8kg，增长了百分之几？",
            "疫苗每隔21天打一次，打完第2次后，第3次要隔多少天？",
        ],
    },
    "旅行": {
        "topics": ["速度", "距离", "时间", "汇率", "预算"],
        "contexts": [
            "高铁时速300km，上海到北京约1318km，需要多少小时？",
            "旅行预算5000元，机票花了2/5，还剩多少元？",
            "汇率1美元=7.2人民币，100美元能换多少人民币？",
        ],
    },
    "电影": {
        "topics": ["时间", "百分比", "统计", "逻辑"],
        "contexts": [
            "电影120分钟，已经看了45分钟，还剩百分之几没看完？",
            "电影票原价80元，打8折后多少元？",
            "观影人数：上午50人，下午比上午多40%，下午有多少人？",
        ],
    },
    "阅读": {
        "topics": ["速度", "比例", "统计", "时间"],
        "contexts": [
            "一本书300页，每天读25页，几天能读完？",
            "已读了全书的3/5，还剩120页，全书一共多少页？",
            "阅读速度：5分钟读了2页，1小时能读多少页？",
        ],
    },
}


def get_math_context_for_interest(interest: str, topic: str = "") -> str | None:
    """根据兴趣和知识点获取数学情境。

    Returns: 情境描述，或 None（该兴趣不适合这个知识点，不强行关联）。
    """
    if interest not in INTEREST_MATH_CONTEXTS:
        return None
    info = INTEREST_MATH_CONTEXTS[interest]
    if topic and topic not in info["topics"]:
        return None
    return info["contexts"][0] if info["contexts"] else None


def should_use_interest_context(student, topic: str) -> str | None:
    """判断是否应该用兴趣情境引入知识点（C3）。

    规则：
    - 学生有记录的兴趣
    - 该兴趣与当前知识点匹配（返回情境而非强凑）
    - 学生当前不挫败（连续错≥2时先解决情绪，不用兴趣）

    Returns: 兴趣名称，或 None。
    """
    if not student.interests:
        return None
    # 挫败时先解决情绪，不用兴趣情境
    if student.current_session.consecutive_wrong >= 2:
        return None
    for interest in student.interests:
        if get_math_context_for_interest(interest, topic):
            return interest
    return None


def extract_interests(message: str, existing: list[str]) -> list[str]:
    """从学生消息中提取新兴趣，返回新增的兴趣列表（不包含已记录的）。"""
    if not message:
        return []
    new_interests = []
    for interest, keywords in INTEREST_KEYWORDS.items():
        if interest in existing:
            continue  # 已记录的跳过
        if any(kw in message for kw in keywords):
            new_interests.append(interest)
    return new_interests


def personalized_opening(mood: str, student) -> str:
    """根据学生兴趣生成个性化开场白。"""
    from backend.agent.persona import OPENING_BY_MOOD
    base = OPENING_BY_MOOD.get(mood, OPENING_BY_MOOD["😐"])
    if not student.interests:
        return base

    interest = student.interests[0]
    interest_lines = {
        "烘焙": "对了，最近有做什么好吃的吗？🌸",
        "游戏": "对了，最近游戏玩得怎么样？有没有通关什么新关卡？🎮",
        "阅读": "对了，最近在看什么书呀？📚",
        "音乐": "对了，最近在听什么歌？🎵",
        "画画": "对了，最近有画什么新作品吗？🎨",
        "运动": "对了，最近有运动吗？⚽",
        "宠物": "对了，家里的小可爱最近怎么样？🐱",
        "动漫": "对了，最近在追什么番呀？📺",
        "旅行": "对了，最近有去哪里玩吗？✈️",
        "电影": "对了，最近看了什么电影呀？🎬",
    }
    line = interest_lines.get(interest)
    if line:
        # 在第一个"～"后插入兴趣引用
        base = base.replace("～", f"～{line}", 1)
    return base
