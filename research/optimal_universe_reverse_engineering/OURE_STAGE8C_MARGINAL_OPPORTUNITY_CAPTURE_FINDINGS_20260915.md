# OURE Stage8C — Marginal Opportunity Capture findings

Date: 2026-09-15
Authoritative run: `34932903125`
Artifact: `oure-stage8c-marginal-opportunity-capture-34932903125`
Status: frozen historical diagnostic

## Integrity / point-in-time audit
Stage8C identified a boundary issue in Stage8A/8B training evaluation. `gross[t] = open[t+2]/open[t+1]-1`, so using historical signal `pos-1` at a Universe decision on `pos` requires `open[pos+1]`, which is not yet known. Stage8C removes that final un-realized training signal for BOTH the old comparator and the new method. The requested 378-session history start is unchanged; 377 historical signals have fully realized holding returns.

This means Stage8B's exact K-frontier numbers should be treated as provisional until rerun with the repaired boundary. Importantly, the repair does not explain away Opportunity's strength: repaired OLD_SAFE_K30 compounds to +302.44%, versus +263.58% in the original Stage8A/8B path.

## New method tested
Marginal Opportunity Capture (MOC) replaces fixed 21-session standalone percentile ranks with direct system-level marginal opportunity capture:
- horizons 21/63/126 sessions;
- rolling starts every 7 sessions;
- equal weight by horizon family;
- each window's available opportunity = best positive single-ETF net log growth;
- candidate Universe is evaluated using its actual frozen OLS Top1 path with 6 bp per-side costs;
- captured opportunity is clipped to the available opportunity;
- greedy addition maximizes MOC.

No Fix15 identity, amount/volume, or future target-block data is used in selection.

## Full-period OOS comparison, 2021–2026 partial
| Variant | Total return | MDD | Turnover sides | Switches | Mean Top1 tenure |
|---|---:|---:|---:|---:|---:|
| FIX15 benchmark | +902.19% | -44.72% | 505 | 260 | 5.31 d |
| OLD_SAFE_K15 | +114.62% | -44.54% | 571 | 300 | 4.68 d |
| OLD_SAFE_K30 | +302.44% | -55.15% | 677 | 345 | 4.02 d |
| MOC_K15 | +53.06% | -45.81% | 489 | 265 | 5.29 d |
| MOC_K30 | -6.72% | -57.65% | 587 | 305 | 4.48 d |

## Annual MOC behavior
MOC_K15 annual returns:
- 2021 +2.93%
- 2022 -1.35%
- 2023 -21.80%
- 2024 +19.01%
- 2025 +13.21%
- 2026 partial +43.06%

MOC_K30 annual returns:
- 2021 -5.38%
- 2022 -19.05%
- 2023 -21.72%
- 2024 +17.83%
- 2025 +15.00%
- 2026 partial +14.80%

## Structural result
MOC does what it was designed to do mechanically: it suppresses routine competition. MOC_K15 turnover falls to 489 sides and mean Top1 tenure rises to 5.29 sessions, almost the Fix15 benchmark's 5.31 sessions. K15 already captures on average 99.61% of MOC_K30's historical capture objective.

But this objective is not predictive enough. The economic result deteriorates sharply versus the repaired old Opportunity comparator. Directly maximizing historical realized marginal OLS value therefore over-penalizes assets that were historically noisy or dormant but may carry future regime optionality.

The clearest example is the 2025-08-25 Universe decision. Repaired OLD_SAFE_K30 includes `161226`, while MOC_K30 excludes it. The subsequent silver trend is precisely the kind of rare future regime that MOC cannot value from historical realized marginal contribution if the asset was not recently useful. At the current 2026-09-08 decision MOC does rank `161226` first and `501018` seventh, showing that MOC can recognize an asset after its opportunity has become historically visible; that is not the same as preserving ex-ante dormant optionality.

## Interpretation
Stage8C rejects the hypothesis that a pure historical system-level marginal-return objective is a better replacement for Stage8A Opportunity Coverage. It solves the competition problem by becoming too conservative.

The key distinction is now clearer:
- `routine marginal value`: does adding the ETF improve the historical OLS path now?
- `latent optionality value`: does the ETF represent a distinct regime/tool that may be dormant for a long time but become uniquely valuable later?

A good Universe selector likely needs both. Pure historical stability (Robust30) underweights optionality; pure realized marginal OLS value (MOC) also underweights optionality; the old standalone opportunity-coverage rule accidentally preserves more of it, despite being crude.

## Frozen decision
- Do not promote MOC to the live/research baseline.
- Keep the repaired OLD_SAFE Opportunity algorithm as the stronger current research comparator.
- Treat Stage8B's exact K-frontier values as provisional until the point-in-time boundary repair is propagated.
- Next algorithmic work should explicitly separate a routine/core score from a latent-tail/optionality score, rather than trying to make one scalar historical-return objective do both jobs.
- Amount/volume remains out of long-horizon membership scoring; it can still be tested later as a point-in-time activation signal.
