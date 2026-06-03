# 比赛任务分析与思考笔记

本文档归纳我们对 MLGenX Bioreasoning Challenge Track A 的讨论。比赛元信息和提交格式见 `overview.md`；数据 schema 与基本统计见 `data_summary.md`。这里只放**判断、原理、争议点**。

---

## 1. 这是什么数据？

- **scRNA-seq，不是 bulk。** Perturb-seq 在定义上就是 single-cell RNA-seq + 在同一文库里读出 CRISPR sgRNA。每个细胞带一个 sgRNA → 表达一种 pert（CRISPRi 把目标基因抑制下去）。
- **CropFlow** 这条 pipeline：同 pert 的细胞 pseudo-bulk → 与 control 比较 → 输出每个 (pert, gene) 的 logFC、p-value、shrunken logFC、FDR。
- 所以**测量是 single-cell，下发给你的"一行 (pert, gene)"是 pseudo-bulk DE 统计**。

### 关键事实：你只看到了完整矩阵的 ~0.2%

完整 DE 矩阵规模：
```
482 perts × ~10–20k expressed genes ≈ 5–10 M (pert, gene) 对
```
竞赛下发 9,518 行 → 覆盖 ≤0.2%。每个 pert 你只看到 ~9 个 top DEG + ~9 个 non-DE。剩下 ~99.8% 是 blank。

派生结论：
- **训练里的 `none` 是被挑过的负样本**，不是均匀随机负采样 → 训练和"任意 (pert, gene)"上的分布不同
- **完整 DE 矩阵大概率没有公开**——否则就是直接发答案。规则只说"可以用公开扰动数据集（PerturbQA 等）"也印证这一点
- 你**不能**从 csv 里推"这个 pert 平均影响多少基因"（恒等于 9，是上限）
- 也**不能**用 csv 推任何 pert-level 全局统计

---

## 2. 切分方式：pert × gene 双轴 disjoint

不是一条 split，是两条独立 split 取笛卡尔对角块：

```
                  gene-train(60%)   gene-val(20%)   gene-test(20%)
pert-train (80%)    ✅ TRAIN          ✗              ✗
pert-val   (10%)    ✗               ✅ VAL          ✗
pert-test  (10%)    ✗               ✗              ✅ TEST
```

| 轴 | 比例 | 总数 | train / val / test |
|---|---|---:|---|
| pert | 80 / 10 / 10 | 482 | 386 / ≈48 / ≈48 |
| gene | 60 / 20 / 20 | ≈2600 | ≈1570 / ≈525 / ≈525 |

数字校对：train 7,705 行 = 386 pert × 1,570 gene 的采样子集；test 1,813 行 = 96 pert × 636 gene 的采样子集。

### 为什么不对称（pert 80/10/10 vs gene 60/20/20）
pert 总量小（482），10% 已经够 test 用；gene 多但每个 gene 样本少，20% 才撑得住 AUROC 统计稳定性。

### 直接含义
**test 行里 pert 和 gene 两边都没在 train 里出现过**。任何 "memorize (pert, gene) → label" 的策略零分；模型必须从基因身份本身（功能/通路/序列/共表达模式）迁移。这是比单轴 hold-out 难一个量级的 OOD 设定。

---

## 3. 标签分布该怎么读

| 类别 | train 数量 | 占比 |
|---|---:|---:|
| `up` | 2,359 | 30.6% |
| `down` | 1,086 | 14.1% |
| `none` | 4,260 | 55.3% |

两个独立现象别混：

**up : down ≈ 2.2 : 1 是真实生物分布**
阈值 `\|logFC\| ≥ log2(1.5)` 是双向对称的，所以 skew 不来自阈值。BMDM（免疫细胞）富含抑制型调控 + 有炎症反馈环，CRISPRi knockdown 单基因后**下游 net 效应**经常是 derepression 居多 → up 多。这是数据本身的性质，不要"修正"。

**none ≈ 55% 是人为造的**
真实分布里 (pert, gene) 是 `none` 的概率 >90%（top-9 DEG 之外几万个基因都是 none）。organizer 故意做了 negative sampling，每个 pert 加 ~9 个 non-DE 来平衡——避免任务退化成"几乎全标 none"。所以 `none` 比例不能被解读为"真实数据中 55% 的扰动反应是 silent"。

---

## 4. 评测指标的几个 tricky 点

公式：
```
score = (micro_AUROC_DE + micro_AUROC_DIR) / 2

DE-AUROC:  二分类 {up∪down} vs {none},  分数 = p_up + p_down
DIR-AUROC: 仅在真 up/down 行,  binary up=1/down=0,  分数 = p_up / (p_up + p_down)
```

不那么显眼但重要的点：

1. **两标量编码三分类问题。** 你只输出 `p_up, p_down`；`p_none = 1 − p_up − p_down` 是隐含的。
2. **DE 看"大小"，DIR 看"角度"——两个轴正交。**
   - DE-AUROC 只看 `p_up + p_down` 的排序，up/down 谁多无关
   - DIR-AUROC 只看 `p_up : p_down` 的比例，乘任何正常数不变
   - **训练目标应该是两个独立二分类**：① DE-vs-none 的 BCE；② up-vs-down 的 BCE（仅在真 DE 上）。不要用 3-class softmax 直接训——会把两个本来正交的方向耦合。
3. **AUROC 是 rank-based，不在乎绝对校准。** LLM 概率不需要校准到"30% 真等于 30%"，只要相对排序对。
4. **"信心陷阱"。** 对方向极有把握时输出 `(p_up=0.99, p_down=0.01)` 听起来好。但如果这行真实是 `none`，那 `p_up + p_down = 1.0` 把它排到 DE 排行榜最前 → 伤 DE-AUROC。所以 **DE 信心和 direction 信心必须分开标定**。最佳参数化：先输出 DE 概率 `q`，再输出条件方向 `r ∈ [0,1]`，最后 `p_up = q·r, p_down = q·(1−r)`。
5. **public/private LB**：1813 行测试 → public 通常占小头，AUROC 在几百行规模上方差不小。public LB overfit 风险存在但不极端。
6. **指标不直接奖励 calibration / ECE，也不惩罚 token 数和 tool 调用数**（虽然 secondary LB 会显示），但 organizer 写"善意反作弊"暗示极端行为会被卡。

---

## 5. 三个 track 的第一性原理拆解

去掉表面差异，每个 track 锁死了**"信息进入模型的唯一渠道"**：

| 渠道 | Track A | Track B | Track C |
|---|---|---|---|
| 推理时模型可调外部资源 | ✗ | ✅ ≤250 工具调用 | ✗ |
| 训练时把数据压进权重 | ✗ | ✗ | ✅ 任意 FT |
| 离线写在 prompt 里 | ✅ 4k tokens | ✅ 16k tokens | ✗ |
| 基座模型 | GPT-OSS-120B 冻结 | GPT-OSS-120B 冻结 | <10B 开源开模 |

**这三个 track 是一个控制变量实验**，不是三道独立题。组委想用同一数据 + 同一指标对照三种范式，回答下面三个问题。

| 对比 | 揭示什么 |
|---|---|
| A vs B | inference-time 检索的边际收益（同基座 → 加工具能 +几 pt？） |
| A vs C | scale-frozen 大模型 vs small-tuned 特化（120B 知识 vs <10B + RL） |
| B vs C | agentic generalist vs domain specialist（哪个是 deployable 路线） |

公布所有 reasoning trace + token / tool 用量 = 给社区画 Pareto frontier 用。**这场比赛真正的产出不是某一条排行榜，是这三张排行榜叠在一起的图。**

### Track A 的隐藏甜点

"prompt-only"并不限制你**离线**做什么——只限制 LLM 推理时是否能调外部资源。你可以：
- 用任何模型、任何 KB、任何检索系统**离线**构造 question-specific prompt
- 然后把最有用的信息压缩进 ≤4096 tokens
- 让 GPT-OSS-120B 当末端解码器

实际竞赛的 Track A 拼的是**离线检索 / curation pipeline 的质量**，不是 prompt engineering 的灵感。

### Track B 的核心
真正的瓶颈是 OOD 事实召回（"Stat1 KD 在 BMDM 里影响 Irf1 吗"）。事实召回交给确定性工具比让 LLM 凭记忆稳。这条 track 应该出最高绝对分。

### Track C 的赌注
<10B 模型对单个 mouse gene 的知识储备有限。test 集双轴 OOD → 不能靠记忆 → 必须让小模型学一种**推理模板**（先想 pert 通路 → 想 readout 在该通路的位置 → 推方向）。SFT 数据要按这种模板造，然后**用 RL 直接打两个 AUROC** 是它唯一比 A/B 占便宜的地方。

---

## 6. 各 track 难易点

**所有 track 共有的根难点**：
- pert × gene 双轴零重叠的 OOD
- `none` 的 train 分布是被采样过的（非均匀）
- per-pert 只能看到 ~18 个 readout，无法做 pert-level 全局统计

**Track A**：
- 难：4k token 严格压缩；自己的 retrieval pipeline 决定上限
- 易：工程复杂度最低（一条离线 pipeline + 一个 prompt template + 跑 GPT-OSS-120B 三次）
- 注意：3 seed 的作用是降噪，不是分辨率工具（详见 §7）

**Track B**：
- 难：100 个工具 + agent 编排是软件工程活；GPT-OSS-120B 当 agent 的可靠性 vs 闭源前沿模型还有差距
- 易：信息瓶颈最小，工具补足参数化知识
- 注意：reasoning trace 和工具调用数都上 LB，要在 score 和 efficiency 间平衡

**Track C**：
- 难：<10B 容量 + OOD test 双重制约；构造能迁移的 SFT 数据
- 易：唯一可以直接对 metric 做 RL 的 track
- 注意：SFT 数据从 train.csv 直接来会让模型记一群"unseen 之外"的 pert，不会迁移；要重写成"推理过程"

---

## 7. Track A 工程细节备忘

**3 seed 不要当投票频率用。** 错误做法："每次 LLM 输出 up/down/none → 3 次 → 频率当概率"。这样 `p_up` 只能取 `{0, 1/3, 2/3, 1}` 四个值；1813 行平均 ~450 行打同分，AUROC 上限被锁死。

**正确做法**：prompt 强制要求 LLM 输出数值，例如：
```
Final answer (must be the last two lines):
P_up = <float in [0,1]>
P_down = <float in [0,1]>
```
3 seed 平均后还是连续值。或者更强：用 vLLM/HF 拿 next-token logprobs，对 "up" / "down" / "none" 三个 token 的 logprob 取 softmax → 单次 inference 就有完美连续概率，3 seed 是噪声平均。

**双 AUROC 双头参数化**：让模型先吐 DE 概率 `q`，再吐方向 `r`，最后 `p_up = q·r, p_down = q·(1−r)`。比直接吐 (p_up, p_down) 更稳，因为两个数的语义被解耦。

**离线检索（pipeline 你随便）**：
- 公开 Perturb-seq / PerturbQA → 拿 pert-level 注释和 known 反应
- GO/Reactome/STRING → pert 和 readout 的通路位置和邻接关系
- 文献 abstract → "Stat1 represses X" 这类直接证据
- 上述拼成结构化、紧凑的 prompt context（4k 真的紧，要疯狂压缩，表格优于散文）

---

## 8. 哪个 track 最可能效果好？

**B > A > C**，分差大致 +3~5 pt、+3~6 pt。

理由：
1. 任务主要瓶颈是 OOD 事实召回 → 工具/数据库永远比 LLM 记忆稳 → Track B 占便宜
2. Track A 通过离线 pipeline 可以逼近 B，但少了"动态决策再查一下"的能力
3. Track C 受 <10B 容量限制 + 双轴 OOD，最难，除非把 RL on metric 做到位

**但**——这个排名不是最重要的。组委办三 track 就是要看 Pareto frontier。**Track A 反而最容易出"惊喜"**：4k token 压得越狠，单位信息密度越高，最 token-efficient 的解法多半在那里。

### 实操选择
如果只打一个 track 冲奖 → **Track A**：
- 工程复杂度最低
- 离线 pipeline 完全自由 → 跟其他选手的差距能拉得最大
- 评测确定性高，3-seed 顺手做 ensemble
- 没有 agent 那种"工具调用超 budget 或失败"的不确定性

如果做研究 → 三 track 都做，专门做对照图。
