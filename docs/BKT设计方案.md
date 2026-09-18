# 小圆助教 — BKT 学生级参数估计落地设计（进度表 135）

> 状态：✅ 已实现（2026-09-19，进度表 135）
> 定位：设计方案.md §12.5「BKT 贝叶斯掌握度追踪（当前掌握度已用贝叶斯，BKT 学生级参数估计暂未引入）」的落地规格。
> 背景：现有 `mastery_tracker.py` 是**固定权重 0.4 的比例收缩 EMA**（并非严格贝叶斯），无学习率/遗忘率/猜测/失误参数；本设计引入标准 4 参数 BKT（Corbett & Anderson 1995）作为**逐次作答的预测与掌握度参考口径**，与现有 EMA 并存。

---

## 0. 决策摘要（8 项，均已在本文给出理由）

| # | 决策点 | 结论 |
|---|--------|------|
| D1 | BKT 状态挂载层 | `MasteryRecord` 扩展可选字段（`p_known`/`bkt_n`/`last_bkt_update`），零破坏；不新建独立字典 |
| D2 | BKT 与现有 EMA 关系 | **双轨并存**：EMA 保持对外口径（`mastery_score` 不变），BKT 新增只读接口 `bkt_p_known()` 供预测/评估/达标判定参考 |
| D3 | 观测注入点 | 四类事件分级：`record_review`/延迟验证=强观测；`apply_eval` 独立作答=中观测（需清洗缺省 False）；PBL LLM 弱评估**不入 BKT** |
| D4 | 学生级参数 | 每学生 1 个全局学习速度偏移 `s_u`（logit 叠加，跨知识点共享），会话内 1-D 网格搜索更新；**不做**每生每点 4 参数 |
| D5 | 遗忘 | BKT 层用 FSRS 可提取性 `R(Δt,S)` 阻尼（ReviewSchedule.stability 作 S），**不替换**现有 `apply_forgetting`（EMA 口径不变） |
| D6 | 切片/回滚 | BKT 为纯增量字段+新服务，删除即回滚；现有测试与 API 零回归 |
| D7 | 验收清单 | 见 §7（行为/数据/性能三层） |
| D8 | 实施顺序 | Step1 内核+持久化 → Step2 观测接入+参数估计 → Step3 遗忘协同+达标判定 |

---

## 1. 模型选型与公式

### 1.1 标准 4 参数 BKT（每作答一轮）

状态：`L_t ∈ {未掌握, 已掌握}`，`P(L_t)` 为掌握概率。

参数（每知识点 + 学生级偏移合成）：
- `P(L0)`：初始掌握先验
- `P(T)`：学习转移概率（未掌握→已掌握）
- `P(G)`：猜测概率（未掌握却答对）
- `P(S)`：失误概率（已掌握却答错）

每轮作答的递推（**先预测 → 再更新 → 后转移**）：

```
预测：   P(correct_t) = P(L_t)(1-P(S)) + (1-P(L_t))·P(G)
更新：   P(L_t | correct)   = P(L_t)(1-P(S)) / P(correct_t)
        P(L_t | incorrect) = P(L_t)·P(S) / (1 - P(correct_t))
转移：   P(L_{t+1}) = P(L_t|obs) + (1 - P(L_t|obs))·P(T)
```

logit 等价形式（固定步长证据累加器，利于数值稳定与参数叠加）：

```
ℓ = logit(P(L));  ℓ += log((1-P(S))/P(G))   答对
                  ℓ += log(P(S)/(1-P(G)))   答错
P(L) ← σ(ℓ);  P(L) ← P(L) + (1-P(L))·P(T)
```

> 与 Beta-Bernoulli（EMA）的关键差异：BKT 是**含状态转移 + 噪声观测通道**的隐马尔可夫更新，能区分"猜测/失误"；EMA 把每次答对直接当证据平移。BKT 对"连续答对→快速达标""隔天遗忘"建模更合理。

### 1.2 达标判定（带滞回，防抖）

```
进入达标：P(L) ≥ 0.90（BKT 口径）
退出达标：P(L) < 0.80
```

> 参考：Classic Cognitive Tutor 用 P(L)≥0.95；K12 稀疏数据下放宽到 0.90（pyBKT 论文：掌握度估计精度约在 15 次作答后趋于稳定，故滞回区间防抖动）。

### 1.3 学生级学习速度偏移（Yudelson 2013 组合函数）

```
s_u        ∈ (0,1)：每学生全局学习速度（初值 0.5 = 标准 BKT）
P(T)_{u,k} = σ( logit(P(T)^k) + logit(s_u) )
P(L0)_{u,k} = σ( logit(P(L0)^k) + logit(b_u) )   （可选先验偏移，本期不做）
```

- 个体化 **P(T)** 收益 > 个体化 P(L0)（Yudelson/Koedinger/Gordon 2013）。
- `s_u=0.5` 时 logit=0，完全退化为标准 BKT → **冷启动零风险**。
- 每生每点 4 参数在 5-50 次作答下**不可辨识**，故只用每生 1 个全局偏移。

---

## 2. 参数表（知识点级先验 + 学生级估计）

### 2.1 知识点级先验（手工默认，按节点类型 3 档）

| 节点类型 | P(L0) | P(T) | P(G) | P(S) | 依据 |
|---------|-------|------|------|------|------|
| concept（概念型） | 0.15 | 0.12 | 0.08 | 0.12 | K12 常规区间（L0 0.15-0.35、T 0.10-0.18、G 0.05-0.15、S 0.05-0.15） |
| calculation（计算型） | 0.25 | 0.15 | 0.10 | 0.08 | 计算型猜测高、失误低 |
| application（应用型） | 0.20 | 0.12 | 0.15 | 0.10 | 应用型猜测高 |
| 未知类型（默认） | 0.20 | 0.12 | 0.10 | 0.10 | 保守居中 |

- 数值取自：Slater & Baker 2011 仿真（L0=0.25/T=0.15/G=0.10/S=0.10）、pyBKT ASSISTments 真实拟合（prior=0.82/ learns=0.18/ guesses=0.27/ slips=0.15）、Baker 2008 受限区间（G≤0.3、S≤0.1）。
- 知识点类型从 `syllabus` 节点元数据或 `Gap.type` 推断；无则用默认档。
- **EP 离线刷新（Hawkins 2014）为后期选项**：数据攒够（每知识点 ≥ 50 学生 × ≥15 次）后单遍计数刷新知识参数表，本期不做。

### 2.2 学生级 s_u 估计（1-D 网格搜索）

```
候选档：logit 空间 [-1.5, -1.0, -0.5, 0, 0.5, 1.0, 1.5]（7 档）
目标：  池化该生全部知识点作答序列，最小化 Brier 损失 Σ(P(correct_t) - 实际)^2
时机：  会话结束（end_session）时，若有 ≥10 条干净观测则重估；否则保持 0.5
开销：  实测 ~0.1ms/学生（纯 stdlib）
```

> 关键洞察：`s_u` 是**跨知识点共享**的，所以可池化该生所有作答来估计——即使每个知识点只有 5-50 次作答，学生总量足够。

---

## 3. 数据模型变更（student.py，全部向后兼容）

### 3.1 `MasteryRecord` 扩展（每知识点 BKT 状态）

```python
class MasteryRecord(BaseModel):
    score: float = 0.0
    confidence: float = 0.0
    attempts_correct: int = 0
    attempts_total: int = 0
    last_interaction: str = ""
    # ---- BKT-6 状态（进度表 135；默认值零破坏）----
    p_known: float = 0.0        # BKT 掌握概率 P(L)，0=未初始化
    bkt_n: int = 0              # BKT 已消费的作答数（用于 s_u 重估时机判断）
    last_bkt_update: str = ""   # 上轮 BKT 更新日期 ISO（遗忘阻尼用）
```

- 新增字段默认值→旧档案反序列化**零迁移成本**（Pydantic 默认填充）。
- `p_known=0` 表示"尚无 BKT 状态"（新知识点），首次作答时用先验 `P(L0)` 初始化（0 后首次更新即离开 0，不会与"掌握概率为 0"混淆——BKT 概率恒 >0）。

### 3.2 `Student` 扩展（学生级参数）

```python
class Student(BaseModel):
    ...
    bkt_learn_offset: float = 0.5   # 学生全局学习速度偏移 s_u（0.5 = 标准 BKT）
    bkt_obs_correct: int = 0         # 干净观测累计答对数（跨知识点池化，s_u 重估用）
    bkt_obs_total: int = 0           # 干净观测累计作答数
```

### 3.3 不新增逐条观测日志

- 逐条观测已有 `review_logs`（ReviewLog，topic_id/rating/datetime，截断 200）覆盖复习场景。
- 学习会话内的逐条对错**不新增日志**——避免档案膨胀；改为 MasteryRecord 聚合计数 + review_logs 已有序列。
- 对错观测通过 `record_review`（强）+ `apply_eval` 独立作答（中，清洗后）两条路径进入 BKT。

---

## 4. 服务层设计（backend/services/bkt.py，纯 stdlib）

```
bkt.py 公开接口（全部只读/纯函数 + 一个状态更新器）：
  PRIORS_BY_TYPE: dict[str, dict]          # §2.1 先验表
  def p_known(student, topic_id) -> float  # 只读：当前 P(L)（无状态返回先验或 0）
  def is_mastered(student, topic_id) -> bool        # 达标判定（滞回，读 p_known）
  def update_bkt(student, topic_id, correct: bool, node_type: str) -> None
      # 1. 取/初始化 P(L0)；2. 遗忘阻尼 R(Δt,S)；3. 预测/更新/转移；4. 落 MasteryRecord + 学生聚合计数
  def estimate_learn_offset(student, topic_id=None) -> float  # 1-D 网格搜索 s_u（纯函数）
```

**遗忘阻尼（D5）**：

```
Δt = days between last_bkt_update and today
if Δt ≥ 1 and rs.stability > 0:   # 同日不遗忘（Qiu 2011 结论）
    S = rs.stability             # ReviewSchedule.stability（FSRS-6）
    R = (1 + FACTOR·Δt/S)^DECAY  # FSRS 可提取性；FACTOR=0.9^(1/DECAY)-1, DECAY=-0.1542
    P(L) ← P(L) · R
```

- 不新增待拟合参数（S 直接取 FSRS 稳定性）；无 ReviewSchedule 时跳过遗忘（新知识点）。
- `record_delayed_check_result` 失败路径追加 `P(L) ← σ(logit(P(L)) − 1.5)`（显式遗忘回退）。

---

## 5. 观测注入点与清洗规则（D3）

| 源 | 位置 | 强度 | 是否入 BKT | 清洗规则 |
|----|------|------|-----------|---------|
| 复习作答 | `main.py:666` `record_review(s, topic, success)` | 强 | ✅ | 二值 success 直接映射 correct=success |
| 延迟验证通过 | `mastery_tracker.py:225` | 强 | ✅ | correct=True（已有 record_review 路径，BKT 随 record_review 自动更新） |
| 延迟验证失败 | `mastery_tracker.py:231-233` | 强 | ✅ | correct=False + 遗忘回退 −1.5 logit |
| 会话内独立作答 | `assessment.py:84-90` `apply_eval` | 中 | ✅（清洗后） | 仅当 `independent_success` 为**显式 True/False** 且该轮为作答轮（`is_answer_eval`）才入；缺省 False（LLM 未作答）**不入** |
| 会话内非独立作答（提示后） | `apply_eval` `hinted=True` | 弱 | ⚠️ | 仅当 `independent_success` 显式给出才入；**不**用 weight 降权，BKT 无此参数 |
| PBL 应用后 LLM 评估 | `pbl_service.py:324-327` | 弱 | ❌ **不入** | LLM 置信估计非作答证据 |

- **同一轮结果刷多个知识点**：`apply_eval` 的 `mastery_updates` 每知识点独立评分（`independent_success` 是轮级、`mastery_updates[].score` 是知识点级）。规则：**轮级 independent_success 只用于"该轮是否有真实作答"判定**；每个知识点的 BKT 观测用 `mastery_updates[topic].score`（LLM 对答对与否的估计）→ 取 `score ≥ 0.6` 视为 correct。这样规避"一轮结果刷 N 点"。
- `gaps_cleared` 兜底（`assessment.py:148` 直改 score=0.7）**不动 BKT**（长时间学习后的掌握确认由延迟验证覆盖）。

---

## 6. 对外口径与集成（D2/D6）

- `mastery_score()` / `mastery_confidence()` **保持不变**（EMA 口径，20+ 读取点零回归）。
- 新增只读 `bkt_p_known(student, topic_id)` / `is_mastered(student, topic_id)`：
  - `syllabus` / `main.py` `/progress` 可选用 BKT 口径标注"已达标的掌握度置信"（本期接 1 个展示点即可：`learning_path.py` 的 ZPD 排序可改为优先 `is_mastered` 未达标点——**本期仅加接口，不改任何现有调用**）。
- `chat.py:1489` `schedule_review` 的初始掌握度：**暂不切换**到 `p_known`（FSRS 已有独立冷启动），列为 Step3 可选优化。
- 回滚策略：删除 `bkt.py` 导入与 MasteryRecord 新字段默认值即完全回退，EMA 链路无感知。

---

## 7. 验收清单（D7）

**行为层**
- [ ] 新知识点首次作答：`p_known` 从 `P(L0)` 先验开始，答对升、答错降（单调性单测）
- [ ] 连续答对可达到 `≥0.90` 达标、`<0.80` 退出（滞回单测）
- [ ] 复用作答（record_review）正确驱动 BKT 更新（与 ReviewLog 同源）
- [ ] 会话内独立作答经清洗后正确入 BKT（独立_success 缺省 False 的轮次不入）
- [ ] PBL 弱评估不入 BKT
- [ ] 延迟验证失败触发遗忘回退（logit −1.5）
- [ ] 隔天间隔（ReviewSchedule.stability>0）应用 FSRS 阻尼；同日不衰减

**数据层**
- [ ] 旧档案（无 BKT 字段）加载正常，新字段填充默认值
- [ ] `p_known=0` 与"真掌握概率"不混淆（首次更新即离开 0）
- [ ] 学生 `bkt_obs_*` 聚合计数与逐条观测一致（随机 100 次作答对账单测）

**性能层**
- [ ] 单次 `update_bkt` < 1ms（纯 stdlib）
- [ ] `estimate_learn_offset` 7 档网格 < 10ms（1000 次观测内）

**测试**
- [ ] 新建 `tests/unit/test_bkt.py`（内核公式/滞回/遗忘阻尼/清洗规则/s_u 网格/对账）——项目 style：unittest 纯 stdlib
- [ ] 现有 `tests/unit/test_repetition.py` 6 用例 + py_compile 全过，无回归

---

## 8. 实施顺序（D8）

| 步骤 | 边界 | 可验证产出 |
|------|------|-----------|
| **Step 1：内核 + 持久化** | `bkt.py` 纯函数内核（先验表/更新/遗忘/滞回/网格）+ `student.py` 字段 | test_bkt.py 内核用例全过；py_compile；无任何调用点接入（面向未来） |
| **Step 2：观测接入 + 参数估计** | `record_review`/`apply_eval`/延迟验证三处接线 + 清洗规则；会话结束重估 `s_u` | 行为层验收全过；`bkt_obs_*` 对账；`estimate_learn_offset` 生效 |
| **Step 3：遗忘协同 + 达标判定展示** | 遗忘阻尼接 FSRS `stability`；`learning_path.py` 接 `is_mastered`；可选 `schedule_review` 初始掌握度切 BKT | 跨天单测；ZPD 排序行为变化文档化；回归全过 |

> 建议每次提交一个 Step，commit message 带 `feat(12.5) 135 BKT...` + 进度表行号，与 131-134 惯例一致。

---

## 9. 明确不做（本期边界）

- ❌ 不做每生每点 4 参数（不可辨识）
- ❌ 不做全班/每生 EM（数据量不足；pyBKT 论文要求 ≥50 学生 × ≥15 次/点才收敛）
- ❌ 不引入 numpy/torch/pyBKT/masterytrace 依赖（内联 ~100 行 stdlib，参考 MIT 实现）
- ❌ 不替换 `mastery_score` 对外口径（双轨并存，EMA 稳定）
- ❌ 不新增逐条学习会话作答日志（用聚合 + review_logs 已有序列）
- ❌ EP 离线刷新知识参数表（数据攒够后再做）
- ❌ `P(L0)` 前置知识图谱先验（`P(L0)_k = σ(logit(0.15)+0.8·mean(logit(parent)))`，列为后期增强，本期保持 3 档类型表）

---

## 参考

- Corbett & Anderson 1995（BKT 原始模型）[DOI](https://doi.org/10.1007/BF01099821)
- Baker, Corbett & Aleven 2008（受限 G≤0.3/S≤0.1）[PDF](https://learninganalytics.upenn.edu/ryanbaker/expanding-the-space.pdf)
- Yudelson, Koedinger & Gordon 2013（学生级 p(T) 个体化 logit 组合）[PDF](https://www.cs.cmu.edu/~ggordon/yudelson-koedinger-gordon-individualized-bayesian-knowledge-tracing.pdf)
- Hawkins, Heffernan & Baker 2014（EP 启发式，后期离线刷新用）[PDF](https://learninganalytics.upenn.edu/ryanbaker/paper_143.pdf)
- Qiu et al. 2011（BKT-F 新一天遗忘；同日不遗忘）[PDF](https://www.cs.cmu.edu/~yqiu/edm2011.pdf)
- pyBKT（EM/forgets/multilearn；重依赖，仅参考）[GitHub](https://github.com/CAHLR/pyBKT) / [论文](https://arxiv.org/html/2105.00385v2)
- MasteryTrace（纯 stdlib 前向递推 + 1225 组网格，MIT，内联参考）[GitHub](https://github.com/RudrenduPaul/MasteryTrace)