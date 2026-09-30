# NLO Stage 9 — Structural Handoff Events

Date: 2026-09-30

Status: completed exploratory event study; no production-rule change.

## Question

When the current raw OLS Top1 enters a strict structural-decay episode, can a challenger be identified early enough to justify a pre-emptive handoff before the normal ranking switch occurs?

Strict incumbent-decay episode start:
- incumbent is still raw OLS Top1
- annualized > 0
- 5-session annualized change < 0
- 5-session raw-score change < 0
- 5-session R² change is in the most-negative 20% of historical Top1 observations

This produces 76 episode starts from 2021 through 2026-09:
- 2021–2024: 52
- 2025–2026: 24

## 1. Newly rebuilding challengers are common, but usually are not the actual successor

A "transition challenger" is:
- not the incumbent
- annualized > 0
- crossed from non-positive to positive within 0–3 sessions
- 3-session R² change > 0

Search from decay start through +3 sessions and take the earliest/highest-score eligible challenger.

### 2021–2024
- strict decay episodes: 52
- mature transition challenger found: 29 (55.8%)
- mean detection delay: 1.10 sessions
- incumbent loses Top1 within 10 sessions: 93.1% of these episodes
- selected transition challenger itself becomes Top1 within 10 sessions: only 24.1%

Switching at challenger detection vs continuing incumbent:
- 5d excess: -0.32 pct
- 10d excess: -1.59 pct
- 20d excess: -0.52 pct
- median 20d excess: -0.34 pct
- beat-incumbent rate: 48.3%

### 2025–2026
- strict decay episodes: 24
- challenger found: 16 (66.7%)
- mean delay: 1.44 sessions
- incumbent loses Top1 within 10 sessions: 81.3%
- selected challenger becomes Top1 within 10 sessions: only 18.8%

Switching vs incumbent:
- 5d excess: -3.76 pct
- 10d excess: -7.46 pct
- 20d excess: -5.64 pct
- median 20d excess: -2.55 pct
- beat-incumbent rate: 43.8%

Conclusion:

> "newly positive + R² rebuilding" is not usually the next leader and is not an effective direct handoff target.

## 2. Actual successors are usually already near the top at decay start

Among strict-decay episodes where the incumbent actually loses Top1 within 10 sessions, classify the eventual first successor by its rank on the decay-start date.

### 2021–2024
First successors within 10 sessions: 47
- start Rank2: 21
- start Rank3: 12
- start Rank4–5: 10
- start Rank6+: 3
- start non-positive / unavailable: 1

Thus Rank2/3 account for 33/47 = 70.2%.

### 2025–2026
First successors within 10 sessions: 20
- start Rank2: 13
- start Rank3: 5
- start Rank4–5: 1
- start Rank6+: 1

Rank2/3 account for 18/20 = 90%.

Average takeover delay:
- start Rank2: about 2.7 sessions
- start Rank3: about 3.1–3.4 sessions
- lower-ranked successors take longer and are much rarer

Interpretation:

> Leadership handoff is usually a transfer between already-established trends, not a jump from a newly resurrected asset directly to Top1.

## 3. Pre-emptive switch to current Top2 is more plausible, but not robust enough

At strict decay start, compare current Top2 with incumbent.

### 2021–2024
Top2 minus incumbent:
- 5d: +0.41 pct
- 10d: +0.07 pct
- 20d: +0.84 pct
- median 20d excess: +1.44 pct
- Top2 beats incumbent over20: 55.8%

### 2025–2026
- 5d: -1.29 pct
- 10d: -1.89 pct
- 20d: -0.32 pct
- median 20d excess: +1.45 pct
- beat rate: 56.5%

The median and win rate are mildly supportive, but recent-period mean is negative because some incumbents continue extremely strong trends despite structural decay.

An oracle choosing the better of Top2/Top3 would show large excess (+4.10 pct in 2021–24, +2.88 pct in 2025–26), but that is not implementable and demonstrates that identifying the correct successor—not merely exiting the incumbent—is the hard problem.

## 4. Relative trend-structure differentials contain some information

At decay start compare Top2 against incumbent using 3-session changes:

- diff_da = Top2 delta annualized - incumbent delta annualized
- diff_ds = Top2 delta raw score - incumbent delta raw score
- diff_dr2 = Top2 delta R² - incumbent delta R²

Rank IC to Top2 future20 excess over incumbent:

### 2021–2024
- diff_da: -0.017
- diff_ds: +0.010
- diff_dr2: +0.086

### 2025–2026
- diff_da: +0.168
- diff_ds: +0.192
- diff_dr2: +0.118

There is some recent-period information in relative annualized/raw-score improvement, but cross-period monotonicity is not strong enough for a production rule.

Simple sign-vote test (Top2 better than incumbent on delta annualized, delta raw score, and delta R²):

All 3 relative changes better:

2021–2024:
- n=42
- 20d excess: +1.76 pct
- median: +1.68 pct
- beat rate: 59.5%

2025–2026:
- n=17
- mean 20d excess: -2.35 pct
- median: +1.45 pct
- beat rate: 58.8%

Again the recent distribution is right-skewed by a few exceptionally strong incumbents; a majority of events beat the incumbent but mean return does not.

## 5. Current 2026-09-29 state

Current raw OLS ranking:
1. 159509
2. 513100
...
5. 513290

159509:
- annualized: +4.2489
- R²: 0.7546
- raw score: 3.2061
- 3d delta annualized: +1.7843
- 3d delta R²: +0.1945
- 3d delta score: +1.8258
- 5d delta annualized: +3.5086
- 5d delta R²: +0.3609
- 5d delta score: +2.9147
- historical Top1 R²-change percentile: ~89.9%

Therefore 159509 is **not** in incumbent structural decay. It is structurally strengthening.

513100:
- Rank2
- annualized +1.1834
- R² 0.6619
- score 0.7834
- also strengthening over 3d/5d

513290:
- Rank5
- annualized +0.1412
- R² 0.0194
- score 0.0027
- annualized recently crossed positive
- R² has not rebuilt yet; 5d delta R² remains -0.2300

Thus the present market does not match the handoff setup:
- incumbent is not decaying;
- 513290 is not yet a mature replacement;
- existing Rank2 513100 is structurally stronger than 513290.

## Decision

Do not add a pre-emptive handoff rule yet.

Evidence supports:
1. strict incumbent decay strongly predicts that leadership will soon change;
2. the eventual successor is usually already Rank2/Rank3;
3. newly rebuilding low-ranked challengers are useful for monitoring but rarely become the immediate successor;
4. early Top2 switching has mild median/win-rate support but unstable mean returns;
5. relative Top2-vs-incumbent structural improvement is promising but not robust enough across periods.

Recommended next research:
- model successor selection only within current Top2/Top3 during strict decay episodes;
- treat newly rebuilding assets as secondary candidates, not primary successors;
- evaluate a conditional handoff policy versus "wait for actual ranking crossover", including transaction costs and drawdown reduction.
