"""间隔复习调度：基于遗忘曲线安排复习时间，检索练习出题。"""

from datetime import datetime, timedelta

from backend.knowledge import syllabus
from backend.models.student import ReviewSchedule, Student


# 复习间隔规则：掌握度 → 间隔天数
REVIEW_INTERVALS = [
    (0.3, 1),   # 掌握度 < 0.3: 1天后复习
    (0.5, 2),   # 掌握度 < 0.5: 2天后复习
    (0.7, 5),   # 掌握度 < 0.7: 5天后复习
    (0.85, 10), # 掌握度 < 0.85: 10天后复习
    (1.0, 20),  # 掌握度 >= 0.85: 20天后复习
]


def schedule_review(student: Student, topic_id: str, mastery: float) -> None:
    """为知识点安排或更新复习计划。"""
    from backend.knowledge import syllabus as _syl
    node = _syl.get_node(topic_id)
    if not node:
        return

    # 找到对应的复习间隔
    interval = 1
    for threshold, days in REVIEW_INTERVALS:
        if mastery < threshold:
            interval = days
            break

    # 检查是否已有该知识点的复习计划
    existing = None
    for rs in student.review_schedules:
        if rs.topic_id == topic_id:
            existing = rs
            break

    today = datetime.now().date()
    next_review = today + timedelta(days=interval)

    if existing:
        # 如果已有计划，只在掌握度提升时延长间隔
        if mastery > existing.mastery_at_schedule + 0.1:
            existing.interval_days = interval
            existing.next_review = next_review.isoformat()
            existing.mastery_at_schedule = mastery
    else:
        # 创建新计划
        student.review_schedules.append(
            ReviewSchedule(
                topic_id=topic_id,
                topic_name=node.name,
                next_review=next_review.isoformat(),
                interval_days=interval,
                review_count=0,
                last_reviewed="",
                mastery_at_schedule=mastery,
            )
        )


def get_due_reviews(student: Student) -> list[ReviewSchedule]:
    """获取今天到期的复习任务。"""
    today = datetime.now().date().isoformat()
    return [
        rs for rs in student.review_schedules
        if rs.next_review and rs.next_review <= today
    ]


def record_review(student: Student, topic_id: str, success: bool) -> None:
    """记录一次复习完成，更新下次复习时间。"""
    for rs in student.review_schedules:
        if rs.topic_id == topic_id:
            rs.review_count += 1
            rs.last_reviewed = datetime.now().date().isoformat()

            if success:
                # 复习成功：间隔翻倍（最长30天）
                new_interval = min(rs.interval_days * 2, 30)
            else:
                # 复习失败：间隔减半（最短1天）
                new_interval = max(rs.interval_days // 2, 1)

            rs.interval_days = new_interval
            rs.next_review = (datetime.now().date() + timedelta(days=new_interval)).isoformat()
            break


def generate_retrieval_question(student: Student, topic_id: str) -> str:
    """生成检索练习题：不给提示，直接出题考。"""
    node = syllabus.get_node(topic_id)
    if not node:
        return ""

    # 根据知识点类型生成不同题目
    questions = {
        # 小学回顾
        "elem_fenshu": "用你自己的话说说，分数除法怎么算？为什么要颠倒相乘？",
        "elem_yunsuanlv": "乘法分配律是什么？能举个生活中的例子吗？",
        "elem_fangcheng": "方程和算式有什么区别？什么是方程的解？",
        "elem_yinshu": "什么是因数和倍数？12的因数有哪些？",
        "elem_sushu": "什么是素数？100以内的素数有哪些？",
        "elem_sifasuan": "四则混合运算的顺序是什么？先乘除后加减，有括号先算什么？",
        "elem_fenshu_jiafa": "同分母分数加法怎么算？异分母呢？",
        "elem_fenshu_chengfa": "分数乘法的法则是什么？和整数乘法有什么关系？",
        "elem_bili": "比和比例有什么区别？比例的基本性质是什么？",
        "elem_tuoxiao": "什么是倒数？1的倒数是多少？0有没有倒数？",
        # 有理数（六年级上）
        "6a_yinru": "为什么要引入负数？温度计上零下5度怎么表示？",
        "6a_jueduizhi": "绝对值是什么意思？|-3|等于多少？绝对值有什么几何意义？",
        "6a_shuzhou": "数轴的三要素是什么？-2在数轴上怎么找？",
        "6a_jiafa": "有理数加法的法则是怎样的？同号和异号分别怎么算？",
        "6a_jianfa": "有理数减法怎么转化成加法？-3-(-5)等于多少？",
        "6a_chengfa": "有理数乘法的符号法则是什么？负负为什么得正？",
        "6a_chufa": "有理数除法和乘法有什么关系？",
        "6a_chengfang": "(-3)²和-3²有什么区别？分别是多少？",
        "6a_hunhe": "混合运算的顺序是什么？先算什么后算什么？",
        # 代数（六年级上）
        "6a_zimu": "用字母表示数有什么好处？a×b可以怎么简写？",
        "6a_daishushi": "代数式3a+2b中，如果a=2，b=3，值是多少？",
        "6a_yicishi": "什么是一次式？它和方程有什么关系？",
        # 方程（六年级上）
        "6a_fangcheng_gn": "什么是方程？列方程解应用题的关键步骤是什么？",
        "6a_fangcheng_jie": "解一元一次方程的基本步骤有哪些？移项要注意什么？",
        "6a_fangcheng_yy": "列方程解应用题时，怎么找等量关系？",
        # 几何（六年级上）
        "6a_xianduan": "线段、射线、直线有什么区别？",
        "6a_jiao_gn": "角的度量单位有哪些？1度等于多少分？",
        "6a_yubujiao": "什么是余角和补角？同角的余角有什么关系？",
        # 六年级下
        "6b_kexuejinshu": "什么是科学记数法？怎么把一个大数写成科学记数法？",
        "6b_eryuan": "二元一次方程组的基本解法有哪些？代入法和加减法分别什么时候用？",
        "6b_xiaoyuan": "什么是二元一次方程组的解？怎么检验一组数是不是方程组的解？",
        "6b_fangchengzu_yy": "列方程组解应用题时，怎么找两个等量关系？",
        "6b_dengshi_xz": "等式有什么性质？在等式两边同时加减乘除同一个数，等式还成立吗？",
        "6b_jiebudengshi": "解一元一次不等式的步骤和解方程有什么相同和不同？",
        "6b_huaxianduan": "画线段的和与差是什么意思？怎么用圆规截取等长线段？",
        "6b_huajiao": "用量角器画角的步骤是什么？怎么画一个角的和与差？",
        "6b_changfangti": "长方体有几个面、几条棱、几个顶点？表面积和体积公式是什么？",
        # 七年级上
        "7a_zhengshi": "整式的加减怎么算？合并同类项的法则是什么？",
        "7a_zhengshi_chufa": "整式除法和整式乘法有什么关系？",
        "7a_yiyuanyici": "一元一次方程的解法步骤：去分母、去括号、移项、合并、系数化1",
        "7a_xiangjiao": "相交线和平行线各有什么性质？对顶角有什么关系？",
        "7a_sanjiao": "三角形的内角和是多少？怎么证明？",
        "7a_quandeng": "全等三角形的判定条件有哪些？SSS、SAS、ASA、AAS分别是什么意思？",
        # 七年级下
        "7b_xiangliang": "什么是向量？向量的加法和减法怎么算？",
        "7b_pingmianzhijiao": "平面直角坐标系中，点的坐标怎么表示？象限是怎么划分的？",
        "7b_erweiyici": "二元一次方程组的图像是什么？两条直线的交点就是方程组的解吗？",
        # 八年级上
        "8a_yiciganshu": "一次函数的图像是什么形状？k和b分别决定了什么？",
        "8a_yingbian": "因式分解和整式乘法有什么关系？提公因式法的步骤是什么？",
        # 八年级下
        "8b_fenishi": "分式有意义的条件是什么？分式的基本性质是什么？",
        "8b_fenishifangcheng": "解分式方程为什么要检验？增根是怎么产生的？",
        "8b_fuhanshu": "什么是反比例函数？它的图像是什么样的？",
        "8b_sanjiao_bj": "证明三角形全等或相似时，常用的辅助线有哪些？",
        # 九年级上
        "9a_yuan": "圆的周长和面积公式是什么？π的近似值是多少？",
        "9a_yuan_jie": "垂径定理说的是什么？怎么用它求弦长？",
        "9a_wuyuanfangcheng": "一元二次方程的求根公式是什么？判别式Δ怎么用？",
        "9aercijishu": "二次函数的图像是什么形状？顶点式和一般式怎么转换？",
        # 九年级下
        "9b_xiangsi": "相似三角形的判定条件有哪些？相似比和面积比有什么关系？",
        "9b_juyuan": "什么是三角函数？sin、cos、tan分别代表什么比值？",
    }

    return questions.get(topic_id, f"关于{node.name}，你能用自己的话讲讲核心内容吗？")
