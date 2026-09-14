# OURE Stage6 — Historical-Universe Transfer Regime Findings

Date: 2026-09-14
Run: `34847008430`
Artifact: `oure-stage6-transfer-regime-34847008430`
Status: frozen
Decision: `transfer_rank_persistence_regime_shift_pass`

## Primary result
The preregistered regime-shift gate passes 2 of 3 conditions.

Completed half-year medians:

| metric | 2022–2024 | 2025–2026 |
|---|---:|---:|
| past-6M Universe rank vs next-half rank Spearman | **-0.209** | **+0.409** |
| robust 3/6/12 rank vs next-half return Spearman | **-0.087** | **+0.353** |
| past-6M winner future percentile in same library | 0.252 | 0.453 |
| past-6M winner regret log vs future-best library member | -0.362 | -0.206 |

Gate 1 passes: the median past6M→future rank relationship flips from negative to positive, with +0.618 change.
Gate 2 passes: the robust-score→future rank relationship improves by +0.440.
Gate 3 fails: the median future percentile of the single past-6M winner improves strongly but remains below 0.50 in the new era.

Therefore the strong conclusion is not that the historical winner itself becomes reliable. Rather, **the cross-sectional ordering of candidate Universes becomes materially more persistent after 2025**.

Individual periods support the same chronology. Past6M→future Spearman is negative in 2022H1, 2022H2, 2023H1 and 2023H2; becomes mildly positive in 2024; then is +0.118 in 2025H1, +0.409 in 2025H2 and +0.771 in 2026H1. The partial 2026H2 period is -0.650 through 2026-09-09 and is excluded from the primary gate, which warns that the state is not permanent.

## Relay-metric persistence is not the explanation
Past-vs-future equal-weight relay-quality rank correlation does not improve in the new era:
- 2022–24 median: `+0.296`;
- 2025–26 median: `+0.167`.

This is consistent with Stage5: historical relay metrics do not explain the strong realized return transfer. Do not promote them as the regime classifier.

## Market-state change
The market itself changes substantially between the two completed-period groups:

| metric | 2022–2024 median | 2025–2026 median |
|---|---:|---:|
| fraction of point-in-time pool OLS-eligible | 0.399 | **0.530** |
| eligible asset count | 195.3 | **376.5** |
| Top1–Top2 score gap | 0.433 | **1.170** |
| risk-leader switch rate | 0.346 | **0.448** |
| mean risk-leader tenure | **2.85 d** | 2.21 d |
| active-leader share | 0.0626 | 0.0423 |

Thus 2025–26 is not a calmer/persistent-leader market. It has **broader simultaneous OLS eligibility and faster leader turnover**, but also a much wider Top1–Top2 score gap. This is a richer opportunity environment with more decisive cross-sectional leaders despite shorter leader lives.

## Fix15: user's structural memory is partly right, raw-return memory is not
On the same completed half-years:
- linked Fix15 return 2022–24: `+49.49%`;
- linked Fix15 return 2025H1–2026H1: `+604.82%`.

So Fix15 raw performance is much stronger in the later era, not weaker.

However its *structure* becomes faster and less persistent:
- median Fix15 leader switch rate: `0.163 -> 0.207`;
- median Fix15 mean leader tenure: `5.91 d -> 4.68 d`;
- median productive-switch share: `0.477 -> 0.387`;
- median switch counterfactual-gain mean: `+0.00277 -> -0.00212`.

This reconciles the prior observations: 2025–26 can produce much higher returns even while Top1 life shortens and ranking competition accelerates, because the opportunity set is substantially stronger/broader.

## Frozen interpretation
1. There is descriptive evidence of a real historical-Universe transfer regime shift around 2025: candidate-Universe rankings are negatively/weakly persistent in 2022–24 and positively persistent in 2025–26.
2. The single past-6M winner remains unreliable; the useful signal is broad ranking persistence, not winner identity.
3. The later regime is not characterized by longer trends. It is characterized by broader eligibility, faster leadership changes, and larger top-rank score separation.
4. Fix15's later-era raw return is stronger even though its leader stability is worse. Separate opportunity abundance/strength from trend lifetime.
5. The next test should use only X<=t market-state variables to predict whether the *next* half-year will have positive Universe-rank transfer. Natural frozen candidates are past-window eligible breadth, Top1–Top2 score gap, leader switch rate and leader tenure. No return-trained feature search is authorized.
6. Sample size remains small: six old and three new completed half-years. This stage establishes a mechanism pattern, not statistical certainty.
