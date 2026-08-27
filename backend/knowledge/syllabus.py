"""沪教版（五四制·2024）初中数学知识图谱。

V1 覆盖六年级上下册；七年级起结构预留。
每个知识点包含前置依赖、难度、是否核心推导点、常见误区、生活化情境素材。
"""

from dataclasses import dataclass, field


@dataclass
class KnowledgeNode:
    id: str
    name: str
    chapter: str
    prerequisites: list[str] = field(default_factory=list)
    difficulty: int = 2  # 1-5
    is_core: bool = False  # 核心推导点（每次会话只挑1个）
    common_mistakes: list[str] = field(default_factory=list)
    life_examples: list[str] = field(default_factory=list)
    # 认知门槛标注（EP-P0-3）
    required_cognitive_stage: str = "concrete"  # concrete/transitional/formal
    abstract_demand: int = 1   # 抽象思维需求 1-5
    working_memory_demand: int = 1  # 工作记忆需求 1-5
    domain: str = "general"   # algebra/geometry/number_theory/stats/general
    common_thinking_models: list[str] = field(default_factory=list)  # 常用思维模型ID
    # E2：掌握度判定标准（可观察可验证）+ 典型错误模式
    mastery_criteria: list[str] = field(default_factory=list)
    typical_errors: list[str] = field(default_factory=list)  # ERROR_PATTERN_LIBRARY ID


# ---------------------------------------------------------------------------
# 六年级上册
# ---------------------------------------------------------------------------

NODES: list[KnowledgeNode] = [
    # ==========================================================================
    # 小学回顾（前置基础）
    # ==========================================================================
    KnowledgeNode(
        id="elem_sifasuan",
        name="四则运算",
        chapter="小学回顾",
        difficulty=1,
        common_mistakes=["运算顺序搞混", "括号优先级不清"],
        life_examples=["超市算账", "分糖果"],
        required_cognitive_stage="concrete",
        abstract_demand=1,
        working_memory_demand=1,
        domain="number_theory",
    ),
    KnowledgeNode(
        id="elem_yunsuanlv",
        name="运算律",
        chapter="小学回顾",
        prerequisites=["elem_sifasuan"],
        difficulty=1,
        common_mistakes=["分配律漏乘", "交换律只在加法用"],
        life_examples=["凑整简便计算"],
    ),
    KnowledgeNode(
        id="elem_fenshu",
        name="分数运算",
        chapter="小学回顾",
        prerequisites=["elem_sifasuan"],
        difficulty=2,
        is_core=True,
        common_mistakes=["通分找错最小公倍数", "约分不彻底", "分数除法没颠倒"],
        life_examples=["披萨切分", "做蛋糕配料比例"],
    ),
    KnowledgeNode(
        id="elem_xiaoshu",
        name="小数运算",
        chapter="小学回顾",
        prerequisites=["elem_sifasuan"],
        difficulty=1,
        common_mistakes=["小数点对齐出错", "补0遗漏"],
        life_examples=["超市价格比较", "身高体重记录"],
    ),
    KnowledgeNode(
        id="elem_yinshu",
        name="因数与倍数",
        chapter="小学回顾",
        difficulty=2,
        common_mistakes=["因数倍数概念混淆", "漏找因数"],
        life_examples=["分组问题：24人分几排"],
    ),
    KnowledgeNode(
        id="elem_sushu",
        name="素数与合数",
        chapter="小学回顾",
        prerequisites=["elem_yinshu"],
        difficulty=2,
        common_mistakes=["1既不是素数也不是合数", "2是唯一的偶素数"],
        life_examples=["密码学基础"],
    ),
    KnowledgeNode(
        id="elem_fensujiayin",
        name="分解素因数",
        chapter="小学回顾",
        prerequisites=["elem_sushu"],
        difficulty=2,
        common_mistakes=["分解不彻底", "漏掉素因数"],
        life_examples=["找最大公因数简化分数"],
    ),
    KnowledgeNode(
        id="elem_fangcheng",
        name="简易方程",
        chapter="小学回顾",
        prerequisites=["elem_sifasuan"],
        difficulty=2,
        common_mistakes=["等式性质理解不透", "天平模型建立不起来"],
        life_examples=["猜数游戏：心里想一个数加5等于12"],
    ),
    KnowledgeNode(
        id="elem_mianji",
        name="面积公式",
        chapter="小学回顾",
        prerequisites=["elem_sifasuan"],
        difficulty=2,
        common_mistakes=["三角形面积忘了除以2", "梯形面积公式记反"],
        life_examples=["房间铺地砖", "操场跑道面积"],
    ),
    KnowledgeNode(
        id="elem_tiji",
        name="体积公式",
        chapter="小学回顾",
        prerequisites=["elem_mianji"],
        difficulty=2,
        common_mistakes=["棱长总和与表面积混淆", "体积单位换算出错"],
        life_examples=["鱼缸能装多少水", "快递纸箱装东西"],
    ),
    # ==========================================================================
    # 六年级上册
    # ==========================================================================
    # 第一章 有理数
    KnowledgeNode(
        id="6a_yinru",
        name="有理数的引入",
        chapter="六上·第一章",
        difficulty=1,
        common_mistakes=["把0既当正数又当负数", "分类时漏掉0"],
        life_examples=["气温零上零下", "游戏金币收支", "电梯上下的楼层"],
    ),
    KnowledgeNode(
        id="6a_shuzhou",
        name="数轴",
        chapter="六上·第一章",
        prerequisites=["6a_yinru"],
        difficulty=1,
        is_core=True,
        common_mistakes=["负数方向搞反", "单位长度不统一"],
        life_examples=["温度计", "地铁站台刻度"],
        common_thinking_models=["visualization"],
    ),
    KnowledgeNode(
        id="6a_jueduizhi",
        name="绝对值",
        chapter="六上·第一章",
        prerequisites=["6a_shuzhou"],
        difficulty=2,
        common_mistakes=["认为|-3|=-3", "混淆绝对值与相反数"],
        life_examples=["距离没有负数：离家3米就是3米"],
        common_thinking_models=["case_analysis", "visualization"],
    ),
    KnowledgeNode(
        id="6a_jiafa",
        name="有理数加法",
        chapter="六上·第一章",
        prerequisites=["6a_shuzhou", "6a_jueduizhi", "elem_fenshu"],
        difficulty=2,
        is_core=True,
        common_mistakes=["异号相加直接相加忘了取大号符号", "漏掉符号"],
        life_examples=["收红包再发红包", "气温先升后降"],
    ),
    KnowledgeNode(
        id="6a_jianfa",
        name="有理数减法",
        chapter="六上·第一章",
        prerequisites=["6a_jiafa"],
        difficulty=2,
        common_mistakes=["减一个负数忘了变加", "变号只变一个"],
        life_examples=["温差计算：最高温-最低温"],
    ),
    KnowledgeNode(
        id="6a_chengfa",
        name="有理数乘法",
        chapter="六上·第一章",
        prerequisites=["6a_jiafa", "elem_fenshu"],
        difficulty=2,
        is_core=True,
        common_mistakes=["负负得正记错", "多个因数时符号判断错"],
        life_examples=["每天亏2元，3天前比今天多多少（-2×-3）"],
        common_thinking_models=["case_analysis"],
    ),
    KnowledgeNode(
        id="6a_chufa",
        name="有理数除法",
        chapter="六上·第一章",
        prerequisites=["6a_chengfa"],
        difficulty=2,
        common_mistakes=["除以分数没颠倒", "符号错误"],
        life_examples=["平均分配欠款"],
    ),
    KnowledgeNode(
        id="6a_chengfang",
        name="有理数乘方",
        chapter="六上·第一章",
        prerequisites=["6a_chengfa"],
        difficulty=3,
        is_core=True,
        common_mistakes=["(-2)²与-2²混淆", "负数的奇次偶次幂符号弄错"],
        life_examples=["折纸厚度翻倍", "细胞分裂"],
    ),
    KnowledgeNode(
        id="6a_hunhe",
        name="有理数混合运算",
        chapter="六上·第一章",
        prerequisites=["6a_jiafa", "6a_jianfa", "6a_chengfa", "6a_chufa", "6a_chengfang", "elem_yunsuanlv"],
        difficulty=3,
        common_mistakes=["先算加减后算乘除", "跳步导致符号错"],
        life_examples=["超市购物小票核对"],
        common_thinking_models=["decomposition", "verification"],
    ),
    # 第二章 简单的代数式
    KnowledgeNode(
        id="6a_zimu",
        name="用字母表示数",
        chapter="六上·第二章",
        prerequisites=["6a_hunhe"],
        difficulty=1,
        common_mistakes=["省略乘号规则不熟", "带单位忘加括号"],
        life_examples=["年龄差不变：a岁和a+25岁"],
    ),
    KnowledgeNode(
        id="6a_daishushi",
        name="代数式与代数式的值",
        chapter="六上·第二章",
        prerequisites=["6a_zimu"],
        difficulty=2,
        common_mistakes=["代入负数不加括号", "书写格式不规范"],
        life_examples=["话费套餐：月租+超出部分单价"],
    ),
    KnowledgeNode(
        id="6a_yicishi",
        name="一次式",
        chapter="六上·第二章",
        prerequisites=["6a_daishushi"],
        difficulty=2,
        common_mistakes=["同类项判断错"],
        life_examples=["打车费：起步价+每公里费用"],
    ),
    # 第三章 一元一次方程
    KnowledgeNode(
        id="6a_fangcheng_gn",
        name="方程与列方程",
        chapter="六上·第三章",
        prerequisites=["6a_yicishi", "elem_fangcheng"],
        difficulty=2,
        common_mistakes=["等量关系找错", "设未知数表述不清"],
        life_examples=["压岁钱规划", "班级分组"],
    ),
    KnowledgeNode(
        id="6a_fangcheng_jie",
        name="一元一次方程及其解法",
        chapter="六上·第三章",
        prerequisites=["6a_fangcheng_gn"],
        difficulty=3,
        is_core=True,
        common_mistakes=["移项不变号", "去分母时漏乘常数项", "去括号漏分配"],
        life_examples=["天平两边同时增减保持平衡"],
        required_cognitive_stage="transitional",
        abstract_demand=3,
        working_memory_demand=3,
        domain="algebra",
        common_thinking_models=["transformation", "reverse"],
        mastery_criteria=[
            "能正确识别一元一次方程（只含一个未知数，次数为1）",
            "能熟练运用等式性质进行移项、合并同类项，正确率≥80%",
            "能正确解出形如 ax+b=c 的方程",
            "能将简单应用题转化为一元一次方程并求解",
            "能解释每一步变形的依据（等式性质）",
        ],
        typical_errors=["calc_sign_error", "concept_condition_unclear", "read_miss_condition"],
    ),
    KnowledgeNode(
        id="6a_fangcheng_yy",
        name="一元一次方程的应用",
        chapter="六上·第三章",
        prerequisites=["6a_fangcheng_jie"],
        difficulty=4,
        common_mistakes=["行程问题速度时间对应错", "配套问题比例关系列反"],
        life_examples=["相遇追及问题", "打折促销比价"],
        common_thinking_models=["modeling", "reverse"],
    ),
    # 第四章 线段与角
    KnowledgeNode(
        id="6a_xianduan",
        name="线段、射线与直线",
        chapter="六上·第四章",
        difficulty=1,
        common_mistakes=["延长线段与反向延长混淆", "表示方法不规范"],
        life_examples=["斑马线是线段", "手电筒光是射线"],
    ),
    KnowledgeNode(
        id="6a_xianduan_bj",
        name="线段的比较与和差倍",
        chapter="六上·第四章",
        prerequisites=["6a_xianduan"],
        difficulty=2,
        common_mistakes=["中点概念不清"],
        life_examples=["量身高比较", "对折绳子"],
    ),
    KnowledgeNode(
        id="6a_jiao_gn",
        name="角的概念与度量",
        chapter="六上·第四章",
        prerequisites=["6a_xianduan"],
        difficulty=2,
        common_mistakes=["度分秒进制按100算", "角的表示方法混乱"],
        life_examples=["时钟指针夹角", "剪刀开合角度"],
    ),
    KnowledgeNode(
        id="6a_jiao_bj",
        name="角的比较与和差倍",
        chapter="六上·第四章",
        prerequisites=["6a_jiao_gn"],
        difficulty=2,
        common_mistakes=["角平分线定义理解不透"],
        life_examples=["披萨均分", "折纸出45°角"],
    ),
    KnowledgeNode(
        id="6a_yubujiao",
        name="余角与补角",
        chapter="六上·第四章",
        prerequisites=["6a_jiao_bj"],
        difficulty=2,
        is_core=True,
        common_mistakes=["余补角混用", "同角余角相等性质不会用"],
        life_examples=["三角尺两锐角互余", "钟表时针分针"],
    ),
    # ---------------------------------------------------------------------------
    # 六年级下册
    # ---------------------------------------------------------------------------
    KnowledgeNode(
        id="6b_kexuejinshu",
        name="科学记数法",
        chapter="六下·第五章",
        prerequisites=["6a_chengfang"],
        difficulty=2,
        common_mistakes=["n的取值数错位"],
        life_examples=["光速3×10⁸米/秒", "人口数量"],
    ),
    KnowledgeNode(
        id="6b_eryuan",
        name="二元一次方程的概念",
        chapter="六下·第六章",
        prerequisites=["6a_fangcheng_jie"],
        difficulty=2,
        common_mistakes=["未知数次数看错", "方程个数与解的关系不清"],
    ),
    KnowledgeNode(
        id="6b_xiaoyuan",
        name="消元——解二元一次方程组",
        chapter="六下·第六章",
        prerequisites=["6b_eryuan"],
        difficulty=3,
        is_core=True,
        common_mistakes=["代入时符号错", "加减消元时系数没配平"],
        life_examples=["鸡兔同笼", "两种奶茶单据求单价"],
        common_thinking_models=["holistic", "transformation"],
    ),
    KnowledgeNode(
        id="6b_fangchengzu_yy",
        name="一次方程组的应用",
        chapter="六下·第六章",
        prerequisites=["6b_xiaoyuan"],
        difficulty=4,
        common_mistakes=["两个等量关系重复使用"],
        life_examples=["折扣组合购买", "行程方案比较"],
        common_thinking_models=["modeling", "holistic"],
    ),
    KnowledgeNode(
        id="6b_dengshi_xz",
        name="不等式及其性质",
        chapter="六下·第六章",
        prerequisites=["6a_fangcheng_jie"],
        difficulty=3,
        is_core=True,
        common_mistakes=["两边乘除负数忘记变向", "解集在数轴上画错空实心"],
        life_examples=["体重超标提醒", "余额不足提示"],
        common_thinking_models=["visualization", "case_analysis"],
    ),
    KnowledgeNode(
        id="6b_jiebudengshi",
        name="解一元一次不等式(组)",
        chapter="六下·第六章",
        prerequisites=["6b_dengshi_xz"],
        difficulty=3,
        common_mistakes=["不等号方向处理不一致", "取公共部分出错"],
        life_examples=["预算范围内选手机套餐"],
    ),
    KnowledgeNode(
        id="6b_huaxianduan",
        name="画线段的和差倍",
        chapter="六下·第七章",
        prerequisites=["6a_xianduan_bj"],
        difficulty=2,
        common_mistakes=["作图痕迹缺失", "尺规使用不规范"],
    ),
    KnowledgeNode(
        id="6b_huajiao",
        name="画角与角的和差倍",
        chapter="六下·第七章",
        prerequisites=["6a_jiao_bj"],
        difficulty=2,
        common_mistakes=["量角器读数内外圈混用"],
    ),
    KnowledgeNode(
        id="6b_changfangti",
        name="长方体的再认识",
        chapter="六下·第八章",
        prerequisites=["6a_xianduan", "elem_tiji"],
        difficulty=2,
        common_mistakes=["棱与面位置关系判断不准"],
        life_examples=["快递纸箱", "教室空间"],
    ),
    # ==========================================================================
    # 七年级
    # ==========================================================================
    # --- 整式的加减 ---
    KnowledgeNode(
        id="7a_zhengshi",
        name="整式的加减",
        chapter="七上·第二章",
        prerequisites=["6a_yicishi"],
        difficulty=2,
        common_mistakes=["合并同类项系数算错", "去括号符号错"],
        life_examples=["购物清单合并同类项"],
    ),
    KnowledgeNode(
        id="7a_zhengshi_chufa",
        name="整式的除法",
        chapter="七上·第二章",
        prerequisites=["7a_zhengshi", "6a_zimu"],
        difficulty=2,
        common_mistakes=["单项式除以单项式漏项", "多项式除以单项式分配不全"],
    ),
    # --- 一元一次方程（深化） ---
    KnowledgeNode(
        id="7a_yiyuanyici",
        name="一元一次方程（深化）",
        chapter="七上·第三章",
        prerequisites=["6a_fangcheng_jie"],
        difficulty=2,
        common_mistakes=["含字母系数的方程讨论不全", "应用题设未知数不恰当"],
        life_examples=["行程问题、工程问题、浓度问题"],
    ),
    # --- 几何初步 ---
    KnowledgeNode(
        id="7a_xiangjiao",
        name="相交线与平行线",
        chapter="七上·第五章",
        prerequisites=["6a_jiao_gn", "6a_yubujiao"],
        difficulty=2,
        is_core=True,
        common_mistakes=["对顶角与邻补角混淆", "平行线判定与性质分不清"],
        life_examples=["斑马线（平行）", "十字路口（垂直）"],
    ),
    KnowledgeNode(
        id="7a_sanjiao",
        name="三角形",
        chapter="七上·第八章",
        prerequisites=["7a_xiangjiao"],
        difficulty=2,
        is_core=True,
        common_mistakes=["三角形内角和180°证明不熟", "全等条件不充分就下结论"],
        life_examples=["自行车车架（三角形稳定性）"],
    ),
    KnowledgeNode(
        id="7a_quandeng",
        name="全等三角形",
        chapter="七上·第八章",
        prerequisites=["7a_sanjiao"],
        difficulty=3,
        is_core=True,
        common_mistakes=["SSA不能判定全等", "对应顶点写错顺序"],
        life_examples=["零件检验（全等匹配）"],
    ),
    # --- 七年级下 ---
    KnowledgeNode(
        id="7b_xiangliang",
        name="实数",
        chapter="七下·第六章",
        prerequisites=["6a_chengfang"],
        difficulty=2,
        common_mistakes=["无理数概念不清", "平方根与算术平方根混淆"],
        life_examples=["正方形对角线长度（√2）"],
    ),
    KnowledgeNode(
        id="7b_pingmianzhijiao",
        name="平面直角坐标系",
        chapter="七下·第七章",
        prerequisites=["6a_shuzhou", "7b_xiangliang"],
        difficulty=2,
        common_mistakes=["象限符号判断错", "坐标轴上的点不属于任何象限"],
        life_examples=["地图经纬度定位"],
    ),
    KnowledgeNode(
        id="7b_erweiyici",
        name="二元一次方程组（深化）",
        chapter="七下·第八章",
        prerequisites=["6b_xiaoyuan"],
        difficulty=3,
        common_mistakes=["消元方法选择不当", "应用题等量关系列错"],
        life_examples=["调配问题、配套问题"],
    ),
    # ==========================================================================
    # 八年级
    # ==========================================================================
    # --- 八年级上 ---
    KnowledgeNode(
        id="8a_yiciganshu",
        name="一次函数",
        chapter="八上·第十四章",
        prerequisites=["6a_yicishi", "7b_pingmianzhijiao"],
        difficulty=3,
        is_core=True,
        common_mistakes=["k、b几何意义理解不透", "函数图像与方程、不等式关系不清"],
        life_examples=["手机套餐费用与通话时长"],
    ),
    KnowledgeNode(
        id="8a_yingbian",
        name="整式的乘除与因式分解",
        chapter="八上·第十五章",
        prerequisites=["7a_zhengshi"],
        difficulty=3,
        common_mistakes=["平方差与完全平方公式用错", "因式分解不彻底"],
        life_examples=["面积计算中的代数变形"],
    ),
    # --- 八年级下 ---
    KnowledgeNode(
        id="8b_fenishi",
        name="分式",
        chapter="八下·第十六章",
        prerequisites=["7a_zhengshi_chufa", "elem_fenshu"],
        difficulty=3,
        common_mistakes=["分式有意义条件漏掉", "通分找错最简公分母"],
        life_examples=["工程效率（工作量/时间）"],
    ),
    KnowledgeNode(
        id="8b_fenishifangcheng",
        name="分式方程",
        chapter="八下·第十六章",
        prerequisites=["8b_fenishi", "7a_yiyuanyici"],
        difficulty=3,
        common_mistakes=["忘记检验增根", "去分母漏乘"],
        life_examples=["行程问题中的速度与时间"],
    ),
    KnowledgeNode(
        id="8b_fuhanshu",
        name="反比例函数",
        chapter="八下·第十七章",
        prerequisites=["8a_yiciganshu", "7b_xiangliang"],
        difficulty=3,
        common_mistakes=["k的正负与图像位置关系搞反", "与一次函数交点求法不熟"],
        life_examples=["路程一定时速度与时间的关系"],
    ),
    KnowledgeNode(
        id="8b_sanjiao_bj",
        name="三角形的证明",
        chapter="八下·第十八章",
        prerequisites=["7a_quandeng"],
        difficulty=3,
        common_mistakes=["等腰三角形性质与判定混淆", "辅助线添加不当"],
        life_examples=["建筑结构中的三角形支撑"],
    ),
    # ==========================================================================
    # 九年级
    # ==========================================================================
    KnowledgeNode(
        id="9a_yuan",
        name="圆",
        chapter="九上·第二十四章",
        prerequisites=["6a_jiao_gn", "7a_sanjiao"],
        difficulty=3,
        is_core=True,
        common_mistakes=["垂径定理应用条件不熟", "圆周角与圆心角关系错"],
        life_examples=["车轮为什么是圆的", "摩天轮设计"],
    ),
    KnowledgeNode(
        id="9a_yuan_jie",
        name="直线与圆的位置关系",
        chapter="九上·第二十四章",
        prerequisites=["9a_yuan", "hs_zhixian"],
        difficulty=3,
        common_mistakes=["切线判定与性质混淆", "弦切角定理用错"],
        life_examples=["过山车轨道设计"],
    ),
    KnowledgeNode(
        id="9a_wuyuanfangcheng",
        name="一元二次方程",
        chapter="九上·第二十一章",
        prerequisites=["7a_yiyuanyici", "8a_yingbian"],
        difficulty=3,
        is_core=True,
        common_mistakes=["求根公式符号错", "判别式应用条件不全"],
        life_examples=["面积问题、利润问题"],
    ),
    KnowledgeNode(
        id="9aercijishu",
        name="二次函数",
        chapter="九上·第二十二章",
        prerequisites=["9a_wuyuanfangcheng", "8a_yiciganshu"],
        difficulty=4,
        is_core=True,
        common_mistakes=["顶点式与一般式互化出错", "开口方向与最值关系搞反"],
        life_examples=["抛物线轨迹（篮球投篮）", "桥梁拱形设计"],
    ),
    KnowledgeNode(
        id="9b_xiangsi",
        name="相似",
        chapter="九下·第二十七章",
        prerequisites=["7a_sanjiao", "8a_yiciganshu"],
        difficulty=3,
        common_mistakes=["相似比与面积比关系错", "对应边找错"],
        life_examples=["地图比例尺", "照片放大缩小"],
    ),
    KnowledgeNode(
        id="9b_juyuan",
        name="锐角三角函数",
        chapter="九下·第二十八章",
        prerequisites=["9a_yuan", "7a_sanjiao"],
        difficulty=3,
        common_mistakes=["正弦余弦正切定义搞混", "特殊角三角函数值记错"],
        life_examples=["测量建筑物高度", "坡度计算"],
    ),
    # ==========================================================================
    # 高中核心知识点
    # ==========================================================================
    # --- 集合与逻辑 ---
    KnowledgeNode(
        id="hs_jihe",
        name="集合",
        chapter="高中·集合与逻辑",
        difficulty=1,
        common_mistakes=["空集是任何集合的子集容易忘", "交并补运算顺序错"],
        life_examples=["班级学生分组", "商品分类筛选"],
    ),
    KnowledgeNode(
        id="hs_luoji",
        name="充分条件与必要条件",
        chapter="高中·集合与逻辑",
        prerequisites=["hs_jihe"],
        difficulty=2,
        common_mistakes=["充分必要方向搞反", "充要条件漏判"],
        life_examples=["下雨是地湿的充分条件"],
    ),
    # --- 函数 ---
    KnowledgeNode(
        id="hs_hanshu_gn",
        name="函数概念与性质",
        chapter="高中·函数",
        prerequisites=["6a_daishushi"],
        difficulty=2,
        is_core=True,
        common_mistakes=["定义域漏考虑分母和根号", "单调性判断用特殊值代替证明"],
        life_examples=["手机电量随时间变化"],
    ),
    KnowledgeNode(
        id="hs_yicishu",
        name="一次函数与二次函数",
        chapter="高中·函数",
        prerequisites=["hs_hanshu_gn"],
        difficulty=2,
        common_mistakes=["二次函数顶点式配方错", "对称轴公式记错"],
        life_examples=["出租车计价（一次函数）", "抛物线轨迹"],
    ),
    KnowledgeNode(
        id="hs_zhishu_duishu",
        name="指数函数与对数函数",
        chapter="高中·函数",
        prerequisites=["hs_hanshu_gn", "6a_chengfang"],
        difficulty=3,
        is_core=True,
        common_mistakes=["对数运算法则混淆", "底数范围遗漏"],
        life_examples=["细胞分裂（指数增长）", "地震里氏震级（对数）"],
    ),
    # --- 三角函数 ---
    KnowledgeNode(
        id="hs_sanjiao_hanshu",
        name="三角函数",
        chapter="高中·三角函数",
        prerequisites=["6a_jiao_gn", "hs_hanshu_gn"],
        difficulty=3,
        is_core=True,
        common_mistakes=["弧度制与角度制混淆", "特殊角三角函数值记错"],
        life_examples=["摩天轮高度随时间变化", "音乐声波"],
    ),
    KnowledgeNode(
        id="hs_sanjiao_hengdeng",
        name="三角恒等变换",
        chapter="高中·三角函数",
        prerequisites=["hs_sanjiao_hanshu"],
        difficulty=3,
        common_mistakes=["和差角公式符号错", "二倍角公式用错"],
        life_examples=["信号叠加", "工程力学分解"],
    ),
    # --- 数列 ---
    KnowledgeNode(
        id="hs_dengcha",
        name="等差数列",
        chapter="高中·数列",
        prerequisites=["hs_hanshu_gn"],
        difficulty=2,
        common_mistakes=["通项公式与求和公式混淆", "项数n的取值"],
        life_examples=["座位排列（每排多2个）", "储蓄每月定存"],
    ),
    KnowledgeNode(
        id="hs_dengbi",
        name="等比数列",
        chapter="高中·数列",
        prerequisites=["hs_dengcha", "hs_zhishu_duishu"],
        difficulty=3,
        common_mistakes=["公比为负时符号处理错", "求和公式分母遗漏"],
        life_examples=["复利计算", "病毒传播"],
    ),
    # --- 向量 ---
    KnowledgeNode(
        id="hs_xiangliang",
        name="平面向量",
        chapter="高中·向量",
        prerequisites=["6a_xianduan", "hs_hanshu_gn"],
        difficulty=3,
        is_core=True,
        common_mistakes=["向量点乘与数乘混淆", "坐标运算符号错"],
        life_examples=["地图导航（位移）", "力的合成与分解"],
    ),
    # --- 解析几何 ---
    KnowledgeNode(
        id="hs_zhixian",
        name="直线与方程",
        chapter="高中·解析几何",
        prerequisites=["hs_xiangliang"],
        difficulty=3,
        common_mistakes=["斜率不存在的情况漏掉", "点斜式与斜截式混淆"],
        life_examples=["GPS定位坐标"],
    ),
    KnowledgeNode(
        id="hs_yuan",
        name="圆与方程",
        chapter="高中·解析几何",
        prerequisites=["hs_zhixian"],
        difficulty=3,
        common_mistakes=["标准方程与一般方程互化出错", "圆与直线位置关系判断错"],
        life_examples=["摩天轮轨迹", "圆形花坛设计"],
    ),
    KnowledgeNode(
        id="hs_yuanzhuiquxian",
        name="椭圆、双曲线与抛物线",
        chapter="高中·解析几何",
        prerequisites=["hs_yuan"],
        difficulty=4,
        is_core=True,
        common_mistakes=["焦点位置判断错", "离心率范围搞混"],
        life_examples=["行星轨道（椭圆）", "卫星天线（抛物面）"],
    ),
    # --- 排列组合与概率 ---
    KnowledgeNode(
        id="hs_pailie",
        name="排列与组合",
        chapter="高中·排列组合与概率",
        prerequisites=["elem_fenshu"],
        difficulty=3,
        common_mistakes=["排列与组合适用场景分不清", "重复计数"],
        life_examples=["选班委（排列）", "组队比赛（组合）"],
    ),
    KnowledgeNode(
        id="hs_概率",
        name="概率",
        chapter="高中·排列组合与概率",
        prerequisites=["hs_pailie"],
        difficulty=3,
        common_mistakes=["互斥事件与独立事件混淆", "条件概率公式用错"],
        life_examples=["抽奖中奖概率", "天气预报"],
    ),
    KnowledgeNode(
        id="hs_tongji",
        name="统计与统计案例",
        chapter="高中·排列组合与概率",
        prerequisites=["hs_概率"],
        difficulty=2,
        common_mistakes=["平均数、中位数、众数适用场景错", "标准差意义理解不透"],
        life_examples=["考试成绩分析", "产品质量检测"],
    ),
    # --- 导数 ---
    KnowledgeNode(
        id="hs_daoshu_gn",
        name="导数概念与运算",
        chapter="高中·导数",
        prerequisites=["hs_hanshu_gn", "hs_zhishu_duishu"],
        difficulty=4,
        is_core=True,
        common_mistakes=["求导公式记错", "复合函数求导漏链"],
        life_examples=["瞬时速度", "边际成本"],
    ),
    KnowledgeNode(
        id="hs_daoshu_yy",
        name="导数的应用",
        chapter="高中·导数",
        prerequisites=["hs_daoshu_gn"],
        difficulty=4,
        common_mistakes=["极值与最值混淆", "单调区间端点处理"],
        life_examples=["利润最大化", "最短路径"],
    ),
]

BY_ID: dict[str, KnowledgeNode] = {n.id: n for n in NODES}


def get_node(node_id: str) -> KnowledgeNode | None:
    return BY_ID.get(node_id)


def all_nodes() -> list[KnowledgeNode]:
    return NODES


# E2：掌握度判定标准兜底生成（未显式配置时按节点属性生成）
_DEFAULT_CRITERIA_TEMPLATES: dict[str, list[str]] = {
    "algebra": [
        "能正确识别涉及「{name}」的题目并说出考察的核心关系",
        "能独立完成含「{name}」的基础题，正确率≥80%",
        "能解释每步变形的依据（不是只会套步骤）",
        "能将简单应用情境转化为「{name}」的数学表达",
        "能识别并纠正至少一种与「{name}」相关的典型错误",
    ],
    "geometry": [
        "能画出「{name}」相关图形并正确标注已知条件",
        "能正确套用「{name}」相关公式/性质，正确率≥80%",
        "能解释公式/性质为什么成立（推导依据）",
        "能区分「{name}」的适用条件，不误用",
        "能解决包含「{name}」的综合几何问题",
    ],
    "number_theory": [
        "能准确说出「{name}」的定义与判定方法",
        "能熟练运用「{name}」相关运算，正确率≥80%",
        "能用「{name}」解决实际数论问题",
        "能识别「{name}」相关概念的区别与联系",
        "能独立完成拓展题并验证答案合理性",
    ],
    "stats": [
        "能收集并整理与「{name}」相关的数据",
        "能正确计算「{name}」相关统计量",
        "能读懂「{name}」相关图表并作出判断",
        "能解释「{name}」结果的实际含义",
        "能基于「{name}」数据提出合理决策",
    ],
    "general": [
        "能正确识别涉及「{name}」的题目并说出考察的核心关系",
        "能独立完成「{name}」的基础题，正确率≥80%",
        "能解释「{name}」每一步做法为什么这样（不是只会套）",
        "能解决包含「{name}」的实际问题",
        "能识别并纠正与「{name}」相关的典型错误",
    ],
}
_DEFAULT_TYPICAL_ERRORS: dict[str, list[str]] = {
    "algebra": ["calc_sign_error", "concept_condition_unclear", "think_rigid"],
    "geometry": ["concept_formula_misremember", "read_unit_error", "think_no_decomposition"],
    "number_theory": ["calc_multiplication_table", "calc_copy_error", "concept_formula_misremember"],
    "stats": ["read_unit_error", "read_miss_condition", "calc_copy_error"],
    "general": ["calc_copy_error", "think_no_decomposition", "read_miss_condition"],
}


def mastery_criteria_for(node: KnowledgeNode) -> list[str]:
    """返回知识点的掌握度判定标准（E2）。显式配置优先，否则按领域生成。"""
    if node.mastery_criteria:
        return node.mastery_criteria
    template = _DEFAULT_CRITERIA_TEMPLATES.get(node.domain, _DEFAULT_CRITERIA_TEMPLATES["general"])
    return [t.format(name=node.name) for t in template]


def typical_errors_for(node: KnowledgeNode) -> list[str]:
    """返回知识点的典型错误模式 ID（E2）。显式配置优先，否则按领域生成。"""
    if node.typical_errors:
        return node.typical_errors
    return _DEFAULT_TYPICAL_ERRORS.get(node.domain, _DEFAULT_TYPICAL_ERRORS["general"])


def prerequisite_chain(node_id: str) -> list[str]:
    """返回所有前置依赖节点（含自身），BFS 遍历完整依赖图，最基础的在前。"""
    chain: list[str] = []
    visited: set[str] = set()
    queue = [node_id]
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        node = BY_ID.get(current)
        if node:
            chain.append(current)
            queue.extend(node.prerequisites)
    return list(reversed(chain))


def find_minimum_gap_node(node_id: str, mastery: "dict[str, float]") -> str:
    """找到依赖链中掌握度最低的节点（最小不会单元）。

    接受两种格式的掌握度映射：{知识点id: float} 或 {知识点id: MasteryRecord}。
    """
    chain = prerequisite_chain(node_id)
    if not chain:
        return node_id

    def _score(nid: str) -> float:
        val = mastery.get(nid)
        if isinstance(val, dict):
            return float(val.get("score", 0.0))
        return float(val or 0.0)

    weakest = min(chain, key=_score)
    return weakest


# 认知阶段顺序（EP-P0-3）
_STAGE_ORDER = {"concrete": 0, "transitional": 1, "formal": 2}


def can_learn_topic(cognitive_stage: str, node: KnowledgeNode) -> bool:
    """检查学生认知阶段是否达到学习该知识点的最低要求。"""
    return _STAGE_ORDER.get(cognitive_stage, 0) >= _STAGE_ORDER.get(node.required_cognitive_stage, 0)


def domain_for_node(node: KnowledgeNode) -> str:
    """返回知识点所属领域（用于分领域认知水平追踪）。"""
    return node.domain


def validate() -> list[str]:
    """校验图谱完整性：ID唯一、依赖存在、无环。返回错误列表。"""
    errors: list[str] = []
    ids = [n.id for n in NODES]
    if len(ids) != len(set(ids)):
        errors.append("存在重复ID")
    for n in NODES:
        for pre in n.prerequisites:
            if pre not in BY_ID:
                errors.append(f"{n.id} 的前置 {pre} 不存在")
        if n.prerequisites and node_id_in_own_chain(n):
            errors.append(f"{n.id} 存在循环依赖")
    return errors


def node_id_in_own_chain(n: KnowledgeNode) -> bool:
    seen: set[str] = set()
    stack = list(n.prerequisites)
    while stack:
        cur = stack.pop()
        if cur == n.id:
            return True
        if cur in seen:
            continue
        seen.add(cur)
        node = BY_ID.get(cur)
        if node:
            stack.extend(node.prerequisites)
    return False


def next_topic_hint(mastery: "dict[str, float]") -> str | None:
    """推荐下一个学习主题：当前章节内未掌握节点中难度最低者。

    接受两种格式的掌握度映射：{知识点id: float} 或 {知识点id: MasteryRecord}。
    """

    def _score(nid: str) -> float:
        val = mastery.get(nid)
        if isinstance(val, dict):
            return float(val.get("score", 0.0))
        return float(val or 0.0)

    candidates = [
        (n.difficulty, n.id)
        for n in NODES
        if _score(n.id) < 0.7
    ]
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][1]
