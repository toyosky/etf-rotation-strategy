# OURE Stage8A — Opportunity30 Findings

Date: 2026-09-15
Authoritative run: `34929135905`
Artifact: `oure-stage8a-opportunity30-34929135905`
Status: frozen historical mechanism test

## Design integrity
- Fix15 was benchmark only and was never used in selection.
- Each dynamic Universe used only the preceding 378 sessions.
- 378 sessions were split into 18×21-session windows.
- Each ETF/window was scored by frozen single-asset OLS/cash performance percentile.
- `OPPORTUNITY30` greedily maximized average best-two coverage across the 18 windows.
- `OPPORTUNITY30_AMOUNT` used the preregistered equal-weight combination of opportunity rank and amount-participation rank.
- Old Robust30 was rebuilt with its frozen Stage7 rule and the B10 reproduction guard passed.

## Full-period 2021–2026 partial, 6 bp/side
| Variant | Total return | Full MDD | Turnover sides |
|---|---:|---:|---:|
| FIX15 benchmark | +902.19% | -44.72% | 505 |
| OLD_ROBUST30 | +73.37% | -52.34% | 597 |
| OPPORTUNITY30 | +263.58% | -65.60% | 697 |
| OPPORTUNITY30_AMOUNT | -50.11% | -61.09% | 719 |

## Year by year
| Year | Old Robust30 | Opportunity30 | Opportunity30+Amount | Fix15 benchmark |
|---|---:|---:|---:|---:|
| 2021 | +1.52% | +28.63% | -9.30% | +20.19% |
| 2022 | -26.42% | -39.96% | -38.20% | +18.57% |
| 2023 | -9.74% | -12.65% | +4.06% | +26.34% |
| 2024 | +15.03% | -21.61% | -5.54% | +16.51% |
| 2025 | +73.38% | +187.55% | +23.97% | +124.50% |
| 2026 partial | +28.94% | +139.10% | -26.96% | +112.80% |

## What changed
Opportunity30 behaves in the intended direction: it is much better at retaining assets that can become exceptional tools in specific regimes.

Average overlap with Fix15, measured only after selection:
- old Robust30: 1.5 / 15;
- Opportunity30: 3.67 / 15;
- amount-aware: 1.0 / 15.

Current B10 (2026-09-08) Opportunity30 independently rediscovered four Fix15 assets: `159509, 161226, 501018, 518880`, versus only two for old Robust30. Fix15 identities were not available to the selector.

This helped strongly in the recent extreme-trend years: Opportunity30 beats both old Robust30 and Fix15 in 2025 and 2026 partial, and also beats Fix15 in 2021.

However, it fails badly in 2022–2024 and has a much worse full-period drawdown.

## Competition / turnover diagnostic
The new objective also creates more internal competition:
- old Robust30 mean non-cash Top1 tenure: ~4.49 sessions;
- Opportunity30: ~3.91;
- amount-aware: ~3.79;
- Fix15 benchmark: ~5.31.

Opportunity30 turnover is 697 sides versus 597 for old Robust30 and 505 for Fix15.

Thus the first opportunity-coverage formulation appears to recover rare trend optionality but at the cost of adding too many simultaneously competitive leaders. This raises switch noise and drawdown.

## Amount conclusion
The preregistered upstream amount formulation is rejected.

The amount-aware selector deliberately chose assets with very high historical participation quality (current B10 selected-member mean amount-quality percentile ~0.963), but its full-period result is -50.11% with 719 turnover sides. High turnover participation during OLS-eligible periods is therefore not a useful stand-alone upstream quality signal in this form.

This does **not** prove that amount information is useless. It shows that giving generalized amount participation 50% of Universe selection weight destroys the optionality structure. The original V1 information is more plausibly local admission/friction information than a global asset-quality characteristic.

## Current experimental Opportunity30 (B10)
`159501,159502,159509,159518,159713,159831,159880,159881,161226,501018,513000,513200,513310,513350,515050,515880,516150,516650,517520,517900,518880,560280,560780,561160,561360,561910,563200,588200,588290,588880`

This remains experimental; it does not replace the live/frozen baseline.

## Main conclusion
Changing the objective from stability to opportunity coverage materially improves the economic result relative to old Robust30 (+263.6% vs +73.4%), which supports the hypothesis that OLS benefits from dormant/heterogeneous option-like assets.

But `best-two 21d coverage` is not yet a satisfactory objective because it produces excessive leader competition, high turnover, and poor 2022–2024 robustness.

The next logical objective is therefore **opportunity coverage minus competition**: reward assets that uniquely cover otherwise-missing regimes while penalizing simultaneous OLS leadership/eligibility overlap. This targets the observed Fix15-like property without using Fix15 identities.

No Stage8A weight or threshold should be retuned after this result.