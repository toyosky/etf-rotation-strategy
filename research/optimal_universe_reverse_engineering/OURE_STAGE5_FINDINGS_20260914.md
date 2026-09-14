# OURE Stage5 — Historical Universe Transfer Findings

Date: 2026-09-14
Run: `34845528263`
Artifact: `oure-stage5-history-transfer-34845528263`
Status: frozen
Decision: `multiwindow_transfer_aggregate_positive_but_regime_unstable`

## Frozen question
Can a Universe found only from prior history transfer value into the next half-year, and can simple low-dimensional relay metrics improve that transfer?

The search at every Jan/Jul decision used only information strictly before the decision date. Historical search was deterministic local search, not exact/global optimization. Forward Universes were frozen for the next half-year. Evaluation begins 2022H1 because the robust rule requires 252 trading days of history. 2026H2 is partial through 2026-09-09.

## Rule A — Past-6M Winner
Across 10 forward periods (9 completed + 2026H2 partial):
- linked total return: `+51.79%`;
- linked same-K random-median return: `-2.33%`;
- completed-half-year same-K-random median hit rate: `4/9 = 44.44%`;
- median noncash K: `9`.

Completed periods only:
- linked total return: `+96.64%`.

The preregistered persistence gate **fails** because the completed-half-year hit rate is not above 50%, despite positive aggregate linked return. Historical six-month winner persistence is therefore not promoted as a reliable standalone rule.

## Rule B — Robust 3/6/12M Winner
Across 10 forward periods:
- linked total return: `+84.89%`;
- linked same-K random-median return: `-8.52%`;
- completed-half-year same-K-random median hit rate: `5/9 = 55.56%`;
- median noncash K: `10.5`.

Completed periods only:
- linked total return: `+142.01%`.

Relative to Rule A, Rule B improves both linked forward growth and same-K-random hit rate. The preregistered robustness-increment gate therefore **passes**.

Interpretation: requiring a Universe to remain strong across 3/6/12-month historical windows is more transferable than simply selecting the single past-6M winner. This is evidence for historical set-value stability only in a multi-window, low-DoF form.

## Rule C — Mechanism-Assisted
Across 10 forward periods:
- linked total return: `+131.18%`;
- linked same-K random-median return: `-0.80%`;
- completed-half-year same-K-random median hit rate: `6/9 = 66.67%`;
- median noncash K: `8.5`.

Completed periods only:
- linked total return: `+204.74%`.

However, the preregistered mechanism gate requires future relay quality to improve over Rule B on at least two of three frozen metrics. Median future deltas versus same-K random are:
- coverage efficiency: Rule C `+0.0055` vs Rule B `-0.0184` — better;
- productive-switch share: Rule C `+0.0461` vs Rule B `+0.0589` — worse;
- switch counterfactual-gain mean: Rule C `+0.00283` vs Rule B `+0.00472` — worse.

Completed periods only gives the same direction: Rule C improves coverage but is worse than Rule B on productive-switch and gain-mean deltas.

Therefore the mechanism-assisted rule **fails the preregistered mechanism-increment gate**, even though its realized forward return is highest. Do not promote this return improvement as evidence that the frozen relay metrics have predictive power; it may be favorable outcome noise.

## Strong regime split
The aggregate Rule-B pass is not regime-stable.

2022–2024 linked forward returns:
- Past6M Winner: `-50.68%`;
- Robust 3/6/12M: `-36.72%`;
- Mechanism-Assisted: `-32.09%`.

2025–2026 (including partial 2026H2) linked forward returns:
- Past6M Winner: `+207.74%`;
- Robust 3/6/12M: `+192.18%`;
- Mechanism-Assisted: `+240.42%`.

Against same-K random, the same split appears: all three historical-transfer rules are weak in 2022–24 and much stronger in 2025–26. This echoes the previously frozen regime dependence of OLS competition. Therefore Rule B should not yet be treated as a universally stable production rule.

## Benchmarks
Over the same 10 forward periods:
- original Fix15 linked total return: `+693.43%`;
- full point-in-time candidate market linked total return: `-80.23%`.

Completed periods only:
- Fix15: `+953.66%`;
- full market: `-70.50%`.

The dynamic historical-transfer rules beat full-market OLS decisively but remain far below the historically strong Fix15 benchmark. Fix15 is not a clean ex-ante construction rule, so this comparison is diagnostic rather than proof of deployability.

## Frozen conclusions
1. `Past 6M winner -> next 6M` is too unstable by itself; the persistence gate fails.
2. Multi-window 3/6/12M stability provides a real aggregate transfer increment and passes the frozen Rule-B gate.
3. The apparent return boost from relay-metric assistance is not supported by future relay-quality improvement and is frozen as a failed mechanism claim.
4. Historical Universe transfer is strongly regime-dependent: weak in 2022–24, strong in 2025–26.
5. The next stage should test whether a low-dimensional X<=t state variable can identify when historical set-value transfer is likely to work. Do not change the 3/6/12 windows or mechanism weights to rescue 2022–24.
6. Residual limitation: the point-in-time price availability filter is strict, but current metadata is used for leverage/inverse/data guards, leaving some survivorship-metadata risk.
