"""兴趣提取器：从学生对话中提取兴趣爱好，自动保存到档案。

支持的兴趣类别：烘焙、游戏、阅读、音乐、运动、画画、动漫、宠物、旅行、电影。
提取逻辑：关键词匹配，已记录的不重复添加。
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
