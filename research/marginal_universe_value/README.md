# Marginal Universe Value (MUV)

## Project status

**Status: active mechanism research / retention branch through Stage18**

研究谱系：[`EXPERIMENT_INDEX.md`](EXPERIMENT_INDEX.md)  
机器可读实验注册表：[`experiment_registry.yaml`](experiment_registry.yaml)

本项目单独研究一个问题：

> 一个 ETF 是否应该获得 OLS Universe 的竞争资格，能否被形式化为一个可估计的数学经济问题？

本项目不直接修改正式策略，也不以“挑出历史收益最高的 ETF”为目标。

---

## Core idea

前序 Universe Oracle / Width Oracle 已经说明：

1. Universe composition 会显著影响最终组合结果；
2. ETF 自己未来收益不错，不代表把它放入 OLS 竞争池以后组合会更好；
3. 增加候选会带来更多机会，也会增加 rank churn / false takeover；
4. 删除错误竞争者有价值，但机械缩小 Universe 会损失真正趋势机会；
5. 因此核心对象不是“ETF 自身好坏”，而是它进入竞争体系后的**边际组合价值**。

定义这一概念为：

> **Marginal Universe Value, MUV**

---

## Two separate decisions

### Retention value

对于当前已经在 Universe 中的 ETF `i`：

```text
RV(i,t) = FutureStrategyValue(P_t) - FutureStrategyValue(P_t \ {i})
```

含义：

> 如果下个月仍允许 `i` 参与 OLS 竞争，相比把它排除，策略未来价值增加了多少？

`RV > 0` 倾向保留；`RV < 0` 表示它在该阶段可能是负边际竞争者。

### Admission value

对于当前 Universe 外的 challenger `j`：

```text
AV(j,t) = FutureStrategyValue(P_t ∪ {j}) - FutureStrategyValue(P_t)
```

含义：

> 允许 `j` 在下个月进入竞争，相比维持现有池不变，是否增加策略价值？

由于新 challenger 会新增一个潜在竞争源，经济上预期 admission 门槛应高于 retention 门槛。

---

## Important modeling choice: do not scalarize too early

V1 不立刻把 `FutureStrategyValue` 写成一个任意加权的单一收益函数。

先把 MUV 保存为多维 counterfactual labels：

- `delta_return`
- `delta_cagr`（较长 horizon 时）
- `delta_max_drawdown`
- `delta_switches`
- `delta_turnover_sides`
- `delta_mean_top1_tenure`
- `delta_invested_ratio`
- `delta_missing_quote_days`

必要时再加入：

- `delta_tail_loss`
- `delta_capture_of_best_trend`
- `false_takeover_count`
- `successful_takeover_count`

这样避免为了得到一个漂亮分数，事后调整 `return / drawdown / turnover` 权重。

后续若确实需要单一 utility，必须在独立版本中预先冻结权重或使用明确的多目标决策规则。

---

## Counterfactual contract

第一版建议采用月频决策：

```text
month-end t
    ↓
只读取 t 及以前的数据构建 features X(i,t)
    ↓
冻结一个月 Universe
    ↓
使用完全相同的 OLS Top1 selector
    ↓
观察 t+1 月的 counterfactual portfolio outcomes
```

核心原则：

- feature 时点严格 point-in-time；
- label 使用下一月真实结果；
- 训练 / 验证必须 chronological walk-forward；
- 不允许用全样本统计确定阈值后再回测历史。

---

## Candidate explanatory variables

第一阶段不追求大量因子，而按经济机制分组。

### A. ETF own trend state

- OLS score / slope / R²
- score_delta / slope_delta / R²_delta
- current residual
- episode age
- historical episode persistence
- ret3 / ret5 / ret10 / ret20 / ret60
- distance to recent high
- volatility / efficiency
- liquidity quality

### B. Remaining-trend quality

来自 Post-OLS Life 项目的 past-only 历史统计：

- 历史 detection 后 remaining-life 分布
- historical MFE / MAE
- historical fwd10 / fwd20
- historical survival probability
- maturity / overextension state

注意：这些必须只由 `t` 以前完成的 episode 构建。

### C. Competition / interference state

这是本项目重点：

- ETF 与当前 Top1 / Top3 的 score gap
- score gap 的变化速度
- 最近进入 Top1 / Top3 的频率
- 历史 takeover success rate
- false takeover rate
- takeover 后平均超额收益
- takeover 后平均 tenure
- 与当前 incumbent 的收益相关性
- 与 incumbent 的 OLS score 同步性
- candidate crowding / trend breadth

### D. Diversification / opportunity uniqueness

- asset class / region / exposure bucket
- 与现有 Universe 的最大相关性 / 中位相关性
- 是否提供当前池中缺失的风险暴露
- 同类 ETF 数量和同类 breadth
- 同类是否已经存在更强 representative

---

## Economic decomposition

概念上，一个 ETF 的边际 Universe 价值可拆成：

```text
MUV
≈ Opportunity Value
+ Diversification Value
- Interference Cost
- Trading / Execution Cost
```

其中：

### Opportunity Value
该 ETF 是否捕捉到现有 Universe 无法捕捉的新趋势。

### Diversification Value
该 ETF 是否增加独立资产驱动，而不是重复已有风险暴露。

### Interference Cost
该 ETF 是否经常以短暂 score 优势抢走更好的 incumbent，制造 false takeover / rank churn。

### Trading Cost
新增竞争是否造成换手、滑点和实际执行成本。

本分解用于指导 feature 设计，不在 V1 直接指定人为权重。

---

## Main hypotheses

### H1 — MUV is predictable

当时可观察的状态变量对下一月 counterfactual MUV 存在稳定关系。

### H2 — individual return is insufficient

单 ETF 自身未来收益不能充分解释 MUV；competition / interference 特征具有额外解释力。

### H3 — admission and retention are asymmetric

新 challenger 的正 MUV 条件应比 incumbent retention 更严格。

### H4 — universe width is endogenous

最优有效池宽不是固定参数，而是通过当期满足正边际价值条件的 ETF 数量内生形成。

### H5 — quality gate matters more than Top-K

基于 MUV 的 admission / retention gate 应优于固定 Top-K 或机械 Cluster90 扩池。

---

## Modeling roadmap

### Stage 0 — Counterfactual label engine

先建立可重复的 month × ETF counterfactual 数据集：

- incumbent remove-one labels
- challenger add-one labels
- 相同冻结 OLS selector
- 相同交易成本
- 输出多维 MUV labels

这一阶段只造 target，不训练模型。

### Stage 1 — Descriptive economics

研究：

- 哪些 feature 与 `delta_return` / `delta_drawdown` / `delta_switches` 稳定相关；
- 2021–24 与 2025–26 是否同方向；
- own-return features 与 competition features 谁解释力更强；
- incumbent / challenger 是否存在明显不同的分布。

### Stage 2 — Simple interpretable models

优先使用：

- 分位数 / 单调关系
- sparse linear / logistic model
- low-complexity GAM / tree as robustness check

第一阶段不直接上复杂 ensemble / deep learning。

### Stage 3 — Retention / Admission models

分别估计：

```text
P(RV > 0 | X_t)
P(AV > 0 | X_t)
```

以及连续目标：

```text
E[delta_return | X_t]
E[delta_switches | X_t]
E[delta_drawdown | X_t]
```

不强制把两类决策合并成一个模型。

### Stage 4 — Monthly walk-forward strategy

月末：

```text
incumbents -> retention gate
outsiders   -> admission gate
             ↓
允许 vacancy
             ↓
冻结下月 Universe
             ↓
原 OLS Top1
```

只与冻结 Fixed15 benchmark 比较，不同时修改 OLS / V1 / C2 / execution。

### Stage 5 — Robustness

- 时间切分
- asset-class leave-one-group-out
- threshold perturbation
- transaction-cost stress
- alternative horizon
- alternative market regimes
- feature ablation
- universe-size neutrality check

---

## Anti-overfitting rules

1. Oracle 实验只能用于提出假设，不能直接成为 feature threshold。
2. 所有 MUV feature 必须 point-in-time。
3. 所有训练 / 阈值拟合必须使用严格过去数据。
4. 任何模型必须与简单 baseline 比较：
   - keep-all Fixed15
   - remove-none
   - random admission
   - fixed-size Top-K
5. 不允许只报告最优 pool width 或最优 threshold。
6. 结果必须报告横截面分布和分时期稳定性。
7. 若复杂模型不能稳定优于简单可解释模型，则保留简单模型。
8. 允许 `no replacement / vacancy`，不为了维持固定池宽强制补位。

---

## Data / storage plan

代码与正式研究文档：

```text
research/marginal_universe_value/
```

大型中间结果：

```text
Supabase Storage / etf-research-archive/
  marginal_universe_value/
    v1/
      asof=YYYY-MM-DD/
        counterfactual_labels.parquet
        features.parquet
        monthly_panels.parquet
        model_predictions.parquet
        walkforward_results.parquet
```

PostgreSQL 只保存最终摘要 / 当前模型状态，不保存大规模 month × ETF counterfactual matrix。

---

## Relationship to existing research

本项目吸收但不覆盖：

- `research/post_ols_life/`：回答 detection 后还剩多少趋势；
- `research/universe/`：Oracle / width / replacement 机制验证；
- `research/ols/`：OLS 本身的识别、episode、ranking；
- `research/execution/`：实际换手 / minute execution。

MUV 项目的角色是把这些发现统一成一个**Universe 决策目标函数 / counterfactual modeling framework**。

---

## Frozen first question

项目第一阶段只回答：

> **在月末时点，仅使用过去信息，哪些可观察特征能够解释一个 incumbent 被移除、或一个 challenger 被加入后，下个月 OLS 策略表现的 counterfactual 差异？**

在这个问题得到稳定答案之前，不直接优化正式策略。

## Research log

- 2026-09-12：正式立项 Marginal Universe Value (MUV)。冻结核心经济对象、retention/admission counterfactual 定义、V1 多维 labels、研究阶段和反过拟合约束。
- 2026-09-13：Retention 主线推进至 Stage18；引入实验注册表与研究谱系，Stage19 分支必须由 Stage18 预声明机制判据决定，不允许按全样本回测优劣事后选路。