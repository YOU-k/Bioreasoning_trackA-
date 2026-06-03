# Track A 可能存在的 trick + LLM 推理经验整合

本文件融合三组信息：
- Track A 数据集本身的几何（采样、阈值、双轴 OOD）
- `Fig6_decomposition_framework_writeup_中文版.pdf` 提出的 Y = B_c + G_c + S_p + I + C + ε 分解和它揭示的几个 metric 病理
- 你在 aging_agent (`_stage_b_prompts.py`)、VCWorld、`llm_geneset_benchmark` 上得到的经验教训

主线就一句话：**Track A 不是"知识竞赛"，是"对 LLM 已有偏见做几何控制"的竞赛**。

---

## A. 数据分布层面的 trick

### A1. G_c 是 freebie——但用它换不到大分

PDF 显示**所有扰动共享的方向 G_c 在某些数据集占 88% 方差**。BMDM CRISPRi 大概率也有类似现象——KD 任何基因都会触发：
- ISR (Atf4, Ddit3, Chac1 等)
- 翻译抑制、ribosomal 蛋白调整
- 应激相关的 immediate-early genes (Fos, Jun, Egr1)
- 慢病毒/sgRNA 表达带来的批次方向

**Trick**：对**任何** (pert, gene) 行，如果 gene ∈ {ISR genes ∪ stress response ∪ ribosomal} 就让 `p_up + p_down` 偏高（即倾向 DE），方向按这些基因在 CRISPRi 应激下的常规反应给。
**预期收益**：可能能让 DE-AUROC 从 0.50 升到 0.55-0.62（这是"baseline2_AdditiveMean"在 PCC benchmark 上 punch above weight 的同一现象）。
**但天花板低**：因为 G_c 是 *所有* 扰动共享的，它对**区分两个不同 pert 在同一 gene 上**的响应没有帮助——而你 1813 行测试有大量这种区分。

### A2. 双轴 zero overlap，但 family / class 重叠

虽然具体的 pert 和 gene 在 train/test 上零重叠，但**功能类**几乎必然重叠：
- pert 类：转录因子（Stat、Irf、Jun、Fos…）、kinase、ribosomal、ubiquitin ligase、proteasome 等
- gene 类：cell cycle、ISR、proteostasis、metabolic enzyme、immune effector 等

**Trick**：构造 pert-class × gene-class 的先验矩阵（从 train.csv），用功能类查 test 行的先验。
比如 "ribosomal-pert × ISR-gene → 80% up"（KD 一个 ribosomal 蛋白会触发 ISR）。
这不是答案，但它给你一个有信号的"base rate prior"，再让 LLM 在它之上推断 pert-specific 调整。

### A3. 每个 pert ~9 DEG + ~9 non-DE 的几何含义

每个 pert 在数据集里只有 **~18 行**——9 个最显著的 DEG（top-9 by significance/effect）+ 9 个 negative-sampled non-DE。这隐含两点：

- **per-pert DE 比例固定在 ~50%**（不是 45%——因为整个数据集还有 55% none，肯定有 organizer 在 pert-level 做了过采样平衡）
- **每个 pert 的 "DE" 是它最 top 的几个**——也就是说，"这个 gene 在这个 pert 下是 DE" 是相对而言的：它必须在所有响应基因里排进前 9。这意味着**轻度 DE 不会出现在 train 里**——所有 train 中标 up/down 的都是 *显著* 上下调。

**Trick**：训练目标其实是"在 pert 的 top-K (K=9) DEG 里，预测 G 是否在前 K"。这本质是一个 **per-pert ranking 问题**伪装成 ternary classification。如果你能算每个 (pert, gene) 的"在该 pert 下的 rank"——比如基于 GRN 邻接 + 通路距离 + 共表达 score——把这个 rank 作为 `p_up + p_down` 的代理，理论上 DE-AUROC 应该不错。

### A4. negative sampling 不均匀

`none` 不是从全基因组随机抽的——organizer 写了"negative sampling strategy to keep balanced"。**他们大概率挑了**：
- 表达水平和 top-DEG 匹配的基因（避免"未表达 gene 默认 none"的 trivial 信号）
- 或者：在该 pert 下 |logFC| 接近 0 但有一定表达的基因

**含义**：train 上的 `none` 比"任意 (pert, gene) 对"的 `none` 要"更像 DE 但实际不是 DE"——分布偏移，让任务比看起来难。
**Trick 的反面**：不要在 prompt 里用"是否表达"这种特征——organizer 已经把 expression-level signal 平衡掉了。

### A5. 阈值 log2(1.5) ≈ 0.585 的灰色地带

阈值很松（很多扰动数据集用 log2(2) 或 |logFC|>1）。意味着**有大量"临界 DE"基因，本质是噪声但被标了 up/down**。这部分 noise floor 直接吃掉 AUROC 的上限——任何模型都做不到 1.0。
**含义**：如果你拿到 ~0.85 的 AUROC，可能已经接近 noise ceiling，再优化提升空间小。

---

## B. Fig 6 框架直接映射过来的 trick

### B1. "评估前先减 G_c" 对应 prompt 设计上的"扣掉通用应激"

PDF 直接说：标准 PCC/MSE 里**测量的有相当一部分是对 G_c 的恢复，不是对 S_p 的恢复**。在 LLM prompt 里这变成：

> ❌ "Will Stat1 KD affect Irf1?"  → 模型套用通用知识答 "yes"，多半是 G_c-level 的 derepression / ISR
>
> ✅ "After accounting for the universal stress response that occurs in any BMDM CRISPRi experiment, does Stat1 KD specifically alter Irf1 above and beyond stress response?" → 强迫模型回答 S_p

这是 *prompt-level deconfounding*。aging_agent 的 "PBMC-specific concerns: is the candidate's primary target actually expressed/relevant in immune cells, or is it tissue-restricted? Off-target / stress-response speculation alone is NOT a sufficient mechanism." 完全是这个套路。

### B2. PCC inflation 在 AUROC 上的对应——majority-class 推动

PDF：ρ(||S_p||, PCC) = -0.91，**小效应扰动 PCC 虚高**，因为预测接近 control 就足以拿高 PCC。

AUROC 是 rank-based，**理论上不受 effect size 影响**。但 LLM 的输出**会受影响**：

- LLM 看到"小机理证据"的样本时倾向输出"none"（保守）
- 看到"大机理证据"时输出 "up" 或 "down"（自信）

如果 organizer 在 test 里也有 effect-size 分层，LLM 的相对排序会受 effect size 主导而**不是受真实标签主导**——这就是 AUROC 版本的"PCC inflation"。

**Trick**：让 LLM 输出**对单个证据强度**的连续评分，而不是"yes/no DE"的二元类——这样 AUROC 排序信号在 effect size bin 内还能保持。

### B3. Variance compression → LLM 的"中庸化"

PDF Panel G：方向准确率与 ||S_p|| 负相关 (ρ=-0.33)，原因是模型把所有预测都推到均值附近（variance compression）。在 LLM 上对应：

> LLM 倾向输出 `(p_up=0.55, p_down=0.45)` 或 `(p_up=0.4, p_down=0.4)`，**从来不输出 (0.95, 0.02)**

**直接后果**：DIR-AUROC 上拉不开排序。

**Trick 1（aggregation 层）**：3 seed 输出后**做 sharpening**——比如 `p̂_up = sigmoid(τ · logit(p_up_avg))`，τ > 1 的 temperature。但这不会改变 AUROC 排序（rank-preserving)。所以——

**Trick 2（prompt 层）**：强制 LLM 输出连续值并对 logit 域做 anchor，比如：

```
output two integers between 0 and 100:
  P_up: <0-100>     (your subjective certainty this gene is upregulated)
  P_down: <0-100>   (your subjective certainty this gene is downregulated)

Calibration anchors:
  - 90+: as confident as 'glucose feeds glycolysis'
  - 60-80: confident based on direct mechanistic chain
  - 30-50: pathway-level evidence only, no direct chain
  - 10-25: weak prior, mostly uninformative
  - <10: actively contradicted by mechanism
```

整数刻度 + anchor 强迫 LLM **使用整个量程**，对抗中庸化。aging_agent 用了同样的策略（confidence 1-10 + 显式 tier rule）。

### B4. Buffering vs Synergy → 已知 pert 用 additive baseline 已经够好

PDF Panel D：buffering 组合**控制 effect size 后**仍然比 synergy 容易预测，因为 buffering 可以被加性基线捕获，synergy 需要真正的非线性建模。

Track A 没有组合扰动，但**对应类比**是：

- **"加性可预测"的 (pert, gene)**：pert 和 gene 在同一条已知通路上，方向由通路结构推得。LLM 在这种行**表现非常好**——它本质上做的就是"加性"推理。
- **"需要非线性"的 (pert, gene)**：feedback loop、bistable switch、reservoir effect。LLM 在这种行**完全没办法**——它没有动力学模型。

**含义**：test 行里能被 LLM 准确预测的，是 ~30-40% 的"加性可推"行。剩下 60-70% 大家都猜——主要 AUROC 来自前者。**所以重点是把前者抓全**，而不是死磕后者。

### B5. Cross-celltype conservation 在 BMDM 内的对应——response stereotypy

PDF Panel E：ρ(cross-celltype conservation, transfer ΔPCC) = 0.55。即一个扰动的响应越在多细胞型 conserved，越容易迁移。

Track A 只在 BMDM 一种细胞型，但对应物是：**响应越 stereotyped 的扰动越容易预测**。

- 已知有大量文献描述的 pert (Stat1, Stat3, Irf3, Nfkb 等炎症 TF) → response stereotyped → LLM 准
- 冷门 pert (uncharacterized RNA-binding protein, ncRNA-related) → response idiosyncratic → LLM 瞎猜

**Trick**：在 prompt 里**给 pert 的 "characterization level"**——如 "this pert has 500+ PubMed mentions" vs "this pert has 5 PubMed mentions"——这相当于一个 confidence prior，让 LLM 自动校准输出强度。

---

## C. 你已有经验直接迁移过来的 trick

### C1. 你的核心观察：**"示例的 vote 主导，事实信息次要"**

源自 aging_agent (_stage_b_prompts.py 的 Min2 策略) + drug_discovery_controller benchmark 跑出来的经验：给 LLM 一堆 retrieved exemplars，最终答案分布**跟 exemplar 标签分布几乎一一对应**，跟具体事实关联弱。

**在 Track A 上的直接迁移**：

如果你的 prompt 里塞 6 个 retrieved (pert', gene') 例子（按相似度排序），它们的 label 分布会主导 LLM 的输出。所以你必须：

1. **Min2 strategy**（你已经用过的）：retrieved 列表里强制至少 2 个 minority class。对 Track A 三分类，更安全的版本是 "Min1-per-class"（每个类至少一个）。
2. **类先验对齐 retrieval**：检索完后**重新采样**保证 retrieved 集合的类比例和 test prior 一致 (~31% up / 14% down / 55% none)，避免因为相似度本身偏 majority 而拉偏。
3. **更激进**：分组 retrieval——分别从 up/down/none 三个池子里各 retrieve top-K，然后展示给 LLM 时刻意 interleave 三类。

**但 Track A 的麻烦**：4k token 预算装不下 10 个 exemplar——大概只能 4-6 个。所以这里的 trade-off：

- 多 exemplar (4-6) + 少机理叙述 → 适合 "common pert" 测试行
- 少 exemplar (0-2) + 多机理叙述 → 适合 "obscure pert" 测试行
- 动态：在离线 retrieval 阶段决定，根据 test pert 的 well-characterized 程度切换 prompt 模板

### C2. "Any function = useful" 乐观偏差 → 强制 disconfirming step

你的另一个发现：LLM 看到基因有任何功能描述（GO term、pathway annotation、随便什么文献），就倾向于说"它跟这个 pert 有关、有响应"。在 drug_discovery_controller 跑 V1/V3 时这是主要的 false positive 来源。

**直接后果在 Track A**：LLM 把 `p_up + p_down` 推得整体偏高，DE-AUROC 上"DE 类别压不下来"，true-none 行被错排到 DE 头部 → DE-AUROC 受损。

**aging_agent 的应对（你已经实现的）**：Step 5 disconfirming check 强制找 ≥2 个反证，如果找不到必须显式说"No serious disconfirmer found"。

**Track A 适配版**：

```
Step 5 (MANDATORY, do not skip):
List AT LEAST TWO reasons this gene might NOT change under this perturbation:
(a) Is the target gene in a pathway that's >2 hops from the perturbed gene?
    If yes, mechanistic propagation is unlikely in a 24-72h CRISPRi window.
(b) Does the perturbed gene have known compensation by paralogs in BMDM?
    If yes, knockdown effect is buffered.
(c) Is the target gene's expression in BMDM control near detection floor?
    If yes, fold-change is unreliable and likely binned as "none" by the 
    differential expression pipeline (FDR<5% & |logFC|>=log2(1.5)).
If you cannot identify two specific concerns, explicitly write
"No serious disconfirmer found" and explain why each of (a)/(b)/(c) is
inapplicable.
```

这一步是 Track A 性能的**关键校准杆**。如果没有它，LLM 会过度预测 DE。

### C3. Calibrated confidence tiers——把 LLM 数值预测拉出量程

aging_agent 用 confidence 1-10 + 显式 tier rules（"conf ≥8 iff i+ii+iii+iv all hold"）把 LLM 从中庸输出推向使用整个量程。

**Track A 直接套用**：你可以让 LLM 输出两个 0-100 的整数（P_up 和 P_down），每个对应到具体 tier rule：

```
Output P_up calibration:
  90-100: direct evidence (the perturbed gene is a known direct repressor
          of the target; KD will release repression -> up). 
  70-89:  pathway-level evidence and consistent direction. 
  50-69:  some functional connection but path is indirect.
  30-49:  weak prior; default toward null.
  10-29:  active mechanistic reason it would NOT go up (e.g., target gene
          paralogs compensate; downstream feedback opposes).
  0-9:    contradicted: target gene is known to decrease in similar conds.

(Same scale for P_down.)
```

这是 *prompt-injected calibration*，比让 LLM 自己想 "0.71 vs 0.83" 稳得多。

### C4. 把 DE 和 DIR 分成两次问，正好匹配 metric 结构

aging_agent 输出 `decision ∈ {BETTER, WORSE, INSUFFICIENT}` + `confidence`，相当于"是否有效"和"方向"分两个轴。Track A 的双 AUROC 结构（DE-AUROC + DIR-AUROC）**几乎是同样的形状**——所以你应该照搬：

```
Question 1 (drives DE-AUROC):
  P_DE = <0-100>   (likelihood the target gene is differentially expressed
                    under this perturbation)

Question 2 (drives DIR-AUROC, only relevant if P_DE > 0):
  P_up_given_DE = <0-100>  (if DE, likelihood it's up rather than down)

Then:
  p_up   = (P_DE / 100) * (P_up_given_DE / 100)
  p_down = (P_DE / 100) * (1 - P_up_given_DE / 100)
```

这样两个 AUROC 各自被自己 hit-target 的标量驱动，**不会相互拖累**。一个直接的好处：3 seed 平均时，P_DE 和 P_up_given_DE **各自独立平均**，再合成 p_up/p_down，比直接对 p_up/p_down 取平均稳。

---

## D. Track A 特有的几个杠杆

### D1. 离线 pipeline 自由 → 用任何模型/KB

规则只约束推理时 GPT-OSS-120B + 4k prompt。**离线你可以用任何东西**：
- 用 Claude/GPT-4 帮你为每个 test (pert, gene) 写 query-specific prompt
- 用 PubMed 检索 + LLM 摘要
- 跑 GeneTAK / VCWorld 的 KG retrieval 离线
- 训练一个小预测模型（在公开 Perturb-seq 上）然后把它的预测**作为 prompt 里的一行**告诉 GPT-OSS-120B

这是 Track A **被低估的核心杠杆**。

### D2. Per-question prompt → 子组特异 prompt 模板

规则说 "Question-Specific Prompt + input question"——意思是 prompt 模板**可以随每个 test row 而变**（这跟 "general prompt + question" 的 Track B 不同）。

利用方式：
- 离线分析 test 集，把 1813 行分成 5-10 个 cluster（如"TF-KD on cell-cycle gene"、"ribosomal-KD on housekeeping gene"、"signaling-KD on TF target"…）
- 每个 cluster 用一个专门的 prompt 模板，包含**这一类**最相关的 ICL exemplars 和**这一类**的常见 disconfirmers

这是 aging_agent 没有的优势（aging_agent 的 prompt 是 per-parent 固定结构）。Track A 因为 per-question prompt 自由，**你可以把更多专家知识精确投递到每个 test row**。

### D3. 3 seed × T=1 不是分辨率工具

之前讨论过：千万别让 LLM 出三选一然后投票频率当概率。让 LLM 出连续值，3 seed **作为方差估计/降噪**。或者用 vLLM 拿 next-token logprobs。

### D4. VCWorld-style KG retrieval 是天然路线

VCWorld 已经是 (cell_line, pert, gene) → DE/DIR 的 pipeline，几乎是 Track A 的"现成解"：

| VCWorld 模块 | Track A 对应 |
|---|---|
| 阶段1：构建 KG（STRING + Reactome + GO + GRN + 文献） | 离线，pipeline 自由 |
| 阶段2：semantic + graph-aware retrieval 找相似 (pert', gene') | 离线，pipeline 自由 |
| 阶段3：structured reasoning prompt 给 LLM | 4k token prompt |

ICLR 2026 那篇 VCWorld 论文（Shuangjia Zheng 组，Tahoe-100M / GeneTAK 数据集）几乎就是这场比赛的参考解。**直接抄 architecture（不抄代码）是合理的起点**。

---

## E. 几个反直觉点 / 别走错的方向

### E1. AUROC rank-based → calibration 是浪费时间

你不需要让 0.7 真的等于 70%。你只需要让 DE 行排在 non-DE 行前面。所以**不要花时间做 Platt scaling / isotonic regression**——把精力放在让排序变好。

### E2. 不要直接 3-class softmax

如果你训一个辅助小模型当 retrieval-augmented prior，**不要**用 3-class softmax 输出 (p_up, p_down, p_none)。两个独立二分类（DE-vs-none，up-vs-down|DE）会更稳——理由参考 `analysis.md` §4 的双 AUROC 解耦。

### E3. public LB 信号弱，别 overfit

1813 行 test 里 public 可能只占 20-30%（~400-540 行）。AUROC 在几百行规模上方差不小，public LB 上 ±0.02 的波动是噪声。**别看到 public LB 涨了就以为找到了 trick**——可能是 public 集偶然喜欢你的 bias。每次决策前用本地的 leave-one-pert-out CV 验证。

### E4. 别太信"reasoning trace 越长越好"

aging_agent 的 reasoning trace 有 6 步是为了**约束 LLM 的推理路径**，不是为了**填满 token budget**。Track A 排行榜会显示 total tokens used——organizer 显然在 watching 这个数。**reasoning trace 应该 dense 而非长**。

---

## F. 可能的"邪路"+ 风险点

### F1. Public Perturb-seq 数据**可能**包含 test (pert, gene) 答案

PDF 提到的 BMDM CRISPRi Perturb-seq 可能是公开发表过的（Replogle 2022？Genome-wide screens？）。如果是公开数据集：

- **如果**你能拿到原始 logFC 矩阵 → 直接查 test 行答案 → 拿满分
- **但** organizer 写"允许 public 数据训练辅助模型"暗示**他们的源数据没公开**，或者他们刻意改了 split / 加了噪声让答案查不到
- 如果你查 PerturbQA 等公开 Perturb-seq 表，**有可能**部分 test pert 在公开表里出现——这种"半泄露"在过去几次类似 Kaggle 比赛上出过事

**建议**：先把 test 集的 pert / gene 列单拿出来，到公开 Perturb-seq 数据库（PerturbQA、scPerturb、Replogle 2022 Cell paper、Tahoe-100M 等）查一次，**看是不是直接能 lookup**。

- 如果直接能 lookup → 这场比赛没意义，但你能拿冠军（可能会被组委做后续调查）
- 如果部分可以 lookup → 用这些做**校准**，其余 test 行用 LLM 路线
- 如果完全 lookup 不到 → 老老实实 KG retrieval + LLM 路线

### F2. Negative sampling 偏置反推

如果你能反推 organizer 的 negative sampling 策略（"挑表达水平匹配 top-DEG 的非 DE 基因"），你可以**预测哪些 test 行更可能是 none**——基于 statistical 特征（表达水平、与 top-DEG 的某种距离）而非生物学特征。

风险：这等于"sampling artifact 而非 biological signal"，论文写出来不光彩，但 Kaggle 不在乎。

### F3. GPT-OSS-120B 的 known issues

- 它对 mouse vs human gene name 有时混淆（Stat1 vs STAT1）
- 在长 reasoning chain 上有 hallucination drift
- temp=1 + top_p=1 在 mouse gene 上比 human gene 更容易跑偏

**对策**：prompt 里**显式声明** "All gene names follow mouse nomenclature (e.g., Aars, Stat1, NOT AARS, STAT1)"。

---

## G. 把 trick 落成一条 pipeline 的草图

下面是把上面所有 trick 拼起来的最小可行 Track A pipeline：

```
[离线阶段，对 train.csv + 公开 KB]
  1. 构建 KG: STRING (mouse) + Reactome + GO + ENCODE BMDM ChIP-seq + 
     Replogle/PerturbQA + 文献 abstract 索引
  2. 为每个 pert 算 "characterization level" score (PubMed mentions)
  3. 算 pert-class × gene-class 先验矩阵（从 train，~50 × 50 size）
  4. 训练一个小辅助模型（GBM 或 GNN，在 PerturbQA 上）→ 输出 p_DE_aux, p_up_aux

[离线阶段，对每个 test row (pert, gene)]
  5. KG retrieval: 找 path(pert -> gene)，深度 ≤3, score by edge confidence
  6. 检索 top-K (pert', gene') 邻居（按 pert-similarity × gene-similarity），
     Min1-per-class 强制三类各 ≥1
  7. 跑 GPT-OSS-120B-quality 的 LLM（Claude/GPT-4 离线代理）写 question-
     specific narrative，包含：
        - mouse gene context (must specify mouse nomenclature)
        - KG path summary (≤200 tokens)
        - 4-6 ICL exemplars (Min1-per-class, ~250 tokens each)
        - pert/gene class prior from step 3
        - aux-model prediction p_DE_aux, p_up_aux from step 4
        - disconfirming checklist (a)/(b)/(c) from §C2
        - calibrated 0-100 anchor scale from §C3
        - two outputs: P_DE and P_up_given_DE per §C4
     总长度 ≤4096 tokens

[推理阶段，每行 3 次]
  8. 调 GPT-OSS-120B with seed ∈ {42, 43, 44}, T=1, top_p=1
  9. 解析 P_DE 和 P_up_given_DE (整数 0-100)
  10. 3 seed 各自平均 P_DE 和 P_up_given_DE
  11. 合成 p_up = P_DE * P_up_given_DE / 10000
              p_down = P_DE * (1 - P_up_given_DE/100) / 100

[提交]
  12. 输出 submission.csv (per-seed + final) + prompt.txt + 打包 zip
```

**预期分数**：粗估
- 朴素 LLM 直接问 → 0.55-0.62
- + KG retrieval + ICL exemplars → 0.65-0.72
- + Min1-per-class + disconfirming step → 0.70-0.76
- + aux 小模型作为 prompt 线索 → 0.74-0.80
- 极致工程 → 0.80-0.85

这些是猜测，实际只能跑了才知道。

---

## 小结：哪些"trick"是真 trick，哪些只是"勤奋"

| 类型 | 实质 | 性价比 |
|---|---|---|
| §A1 G_c freebie | 物理学告诉你 | ★★★（自动会发生，知道就行） |
| §A2 class prior | 数据工程活 | ★★★ |
| §B1 deconfounding prompt | 一句话改 prompt | ★★★★ |
| §B3 anchor scale 反 variance compression | 一段 prompt | ★★★★ |
| §C1 Min2/Min1-per-class | 你已经会 | ★★★★（核心） |
| §C2 disconfirming step | 你已经会 | ★★★★（核心） |
| §C4 DE/DIR 分开问 | metric-aware prompt | ★★★★★（最高 ROI） |
| §D2 per-question 子组模板 | 离线工程 | ★★★ |
| §D4 VCWorld-style KG retrieval | 离线工程 | ★★★ |
| §F1 公开数据 lookup | 检查 5 分钟 | 必须检查；如果通就 ★★★★★ |

**最该先做的**：§F1（lookup 检查）+ §C4（双标量参数化）。第一项告诉你这比赛有没有意义，第二项是 metric-aligned 的最简单杠杆。
