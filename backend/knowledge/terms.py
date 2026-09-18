"""术语管理库（模块 L.6）：术语名 → 学段 → 通俗解释。

规格：docs/V3.0开发规格说明书.md L.6

纪律（注入 persona system prompt）：
- 新术语第一次出现必须带解释
- 同一术语被解释过 2 次以上才可自由使用
- 禁止连续 2 句话都含未解释术语

术语按学段分级：LEVEL 1 禁止使用（只许生活语言），LEVEL 2+ 首次必解释。
"""

# ===== 术语库：term → 释义（含最低可用学段） =====
TERMS: dict[str, dict] = {
    # ---- 数与代数 ----
    "移项": {
        "levels": [2, 3, 4],
        "explanation": "把一项从等号的一边移到另一边，符号要反过来",
    },
    "合并同类项": {
        "levels": [2, 3, 4],
        "explanation": "把含相同字母和次数的项合在一起，像把相同的积木归堆",
    },
    "系数": {
        "levels": [2, 3, 4],
        "explanation": "字母前面的数字，比如 3x 里的 3",
    },
    "未知数": {
        "levels": [2, 3, 4],
        "explanation": "还不知道的数，先用字母（比如 x）占个位置",
    },
    "方程": {
        "levels": [1, 2, 3, 4],
        "explanation": "含有未知数的等式，就像一台天平：两边必须一样重",
    },
    "等式性质": {
        "levels": [2, 3, 4],
        "explanation": "天平两边同时加/减/乘/除同一个数，还是平衡的",
    },
    "通分": {
        "levels": [2, 3, 4],
        "explanation": "把不同分母的分数变成同分母，方便加减",
    },
    "约分": {
        "levels": [1, 2, 3, 4],
        "explanation": "把分数的分子分母同时缩小（除以公因数），让分数更简洁",
    },
    "倒数": {
        "levels": [2, 3, 4],
        "explanation": "乘积为 1 的两个数互为倒数，比如 3/4 的倒数是 4/3",
    },
    "因数": {
        "levels": [1, 2, 3, 4],
        "explanation": "能整除一个数的数，比如 12 的因数是 1、2、3、4、6、12",
    },
    "倍数": {
        "levels": [1, 2, 3, 4],
        "explanation": "一个数乘以整数得到的结果，比如 12 是 3 的倍数",
    },
    "素数": {
        "levels": [2, 3, 4],
        "explanation": "只有 1 和它自己两个因数的数，比如 2、3、5、7",
    },
    "绝对值": {
        "levels": [2, 3, 4],
        "explanation": "一个数到 0 的距离（只看远近不看方向），比如 |-3|=3",
    },
    "数轴": {
        "levels": [2, 3, 4],
        "explanation": "一条标了方向和刻度的直线，数字从小到大排在上面",
    },
    "代数式": {
        "levels": [2, 3, 4],
        "explanation": "用字母和数字组成的式子，比如 3a+2b",
    },
    "一次式": {
        "levels": [2, 3, 4],
        "explanation": "字母的最高次数是 1 的式子，像 x+3",
    },
    "多项式": {
        "levels": [2, 3, 4],
        "explanation": "好几个项相加组成的式子，比如 x²+2x+1",
    },
    "因式分解": {
        "levels": [3, 4],
        "explanation": "把一个式子拆成几个式子相乘，像把积木拆回零件",
    },
    "比例": {
        "levels": [1, 2, 3, 4],
        "explanation": "两个比相等的式子，表示两个量之间固定的倍数关系",
    },
    "百分数": {
        "levels": [1, 2, 3, 4],
        "explanation": "表示一个数是另一个数的百分之几，比如 50% 就是一半",
    },
    "坐标系": {
        "levels": [3, 4],
        "explanation": "用横竖两条线给平面位置编号，像地图上的经线和纬线",
    },
    "函数": {
        "levels": [3, 4],
        "explanation": "一种对应关系：一个数定了，另一个数就跟着定了",
    },
    "斜率": {
        "levels": [3, 4],
        "explanation": "直线的倾斜程度，表示 x 每变 1，y 变多少",
    },
    "增根": {
        "levels": [3, 4],
        "explanation": "解方程时混进来的假答案，代回去会发现分母变成 0，所以要检验",
    },
    "判别式": {
        "levels": [3, 4],
        "explanation": "判断一元二次方程有几个根的一个表达式（b²−4ac）",
    },
    # ---- 图形与几何 ----
    "对顶角": {
        "levels": [2, 3, 4],
        "explanation": "两条线相交形成的、面对面的一对角，它们大小相等",
    },
    "邻补角": {
        "levels": [2, 3, 4],
        "explanation": "相邻且互补的两个角，加起来正好 180°",
    },
    "余角": {
        "levels": [2, 3, 4],
        "explanation": "加起来等于 90° 的两个角，互称余角",
    },
    "互补": {
        "levels": [2, 3, 4],
        "explanation": "两个角加起来等于 180°，就说它们互补",
    },
    "全等": {
        "levels": [3, 4],
        "explanation": "两个图形完全一样，可以完全重合",
    },
    "相似": {
        "levels": [3, 4],
        "explanation": "形状一样、大小不同，像照片放大缩小",
    },
    "轴对称": {
        "levels": [2, 3, 4],
        "explanation": "图形沿一条线对折，两边完全重合",
    },
    "垂直平分线": {
        "levels": [3, 4],
        "explanation": "过线段中点且与它垂直的直线，线上每点到两端距离一样",
    },
    "圆周角": {
        "levels": [3, 4],
        "explanation": "顶点在圆上、两边都与圆相交的角",
    },
    "三角函数": {
        "levels": [3, 4],
        "explanation": "用直角三角形的边长比来描述角度，比如 sin、cos、tan",
    },
    "辅助线": {
        "levels": [3, 4],
        "explanation": "自己加上去的线，帮我们发现图形里藏着的相等关系",
    },
    # ---- 统计与概率 ----
    "平均数": {
        "levels": [1, 2, 3, 4],
        "explanation": "把所有数加起来除以个数，得到的一个『代表值』",
    },
    "中位数": {
        "levels": [2, 3, 4],
        "explanation": "把数据从小到大排好，最中间的那个数",
    },
    "概率": {
        "levels": [2, 3, 4],
        "explanation": "一件事发生的可能性大小，用 0 到 1 之间的数表示",
    },
}


def get_terms_for_level(level: int) -> list[dict]:
    """按学段筛选可用的术语（含释义），用于注入 persona。

    Args:
        level: 学段语言层级 1~4（L.5）

    Returns:
        [{"term": str, "explanation": str}, ...]，按术语名排序。
    """
    result = []
    for term, info in TERMS.items():
        if level in info["levels"]:
            result.append({"term": term, "explanation": info["explanation"]})
    result.sort(key=lambda x: x["term"])
    return result


def terms_instruction(level: int) -> str:
    """构造术语管理纪律指令（L.6，注入 persona system prompt）。"""
    rules = [
        "## 术语管理纪律（必须遵守）",
        "- 新术语第一次出现必须带一句通俗解释（例：「移项，就是把项移到等号另一边，要变号」）",
        "- 同一术语在对话中被解释过 2 次以上后，才可以自由使用不再解释",
        "- 禁止连续 2 句话都含未解释的术语；宁可拆成两轮也不要堆术语",
    ]
    if level == 1:
        rules.append("- 学生处于低年级语言层级：尽量用生活语言和实物比喻，避免使用任何数学术语")
    if level >= 2:
        terms = get_terms_for_level(level)
        if terms:
            lines = "；".join(f"「{t['term']}」= {t['explanation']}" for t in terms[:18])
            rules.append(f"- 本学段可能用到这些术语（首次使用时必须按此解释）：{lines}")
    return "\n".join(rules)