# OURE Stage8E — Human Economic Coverage Findings

Date: 2026-09-15
Authoritative run: `34934817616`
Artifact: `oure-stage8e-economic-coverage-34934817616`
Status: frozen historical diagnostic

## Design integrity
The economic taxonomy was frozen before any Stage8E return result was computed. Slot membership used only structural identity metadata. Within each slot, the historical representative was chosen mechanically by highest median trading amount over the prior 60 completed sessions. No historical return, OLS performance, Fix15 identity, or target-block future return entered membership selection.

The final taxonomy contains 27 human-defined economic slots. Historical K is variable because a slot is empty when no point-in-time eligible ETF existed. Actual K rose from 20 at the 2020-12-21 decision to 27 from 2025-08-25 onward. All risky metadata buckets were covered by the taxonomy; the only unmapped current bucket was CASHLIKE, which is intentionally handled by the frozen cash comparator.

Caveat: structural metadata are current labels, not a historically versioned metadata snapshot. Historical trading/data eligibility remains point-in-time, but mandate/name changes could create a residual metadata-history risk.

## Full-period OOS 2021–2026 partial
| Variant | Total return | MDD | Turnover sides | Switches | Mean Top1 tenure |
|---|---:|---:|---:|---:|---:|
| FIX15_BENCHMARK | +902.19% | -44.72% | 505 | 260 | 5.31 d |
| OLD_SAFE_K15 | +114.62% | -44.54% | 571 | 300 | 4.68 d |
| OLD_SAFE_K30 | +302.44% | -55.15% | 677 | 345 | 4.02 d |
| ECONOMIC_COVERAGE | +213.34% | -54.81% | 643 | 327 | 4.25 d |

Economic Coverage is substantially stronger than repaired Opportunity K15, but weaker than repaired Opportunity K30 on total return. Relative to K30 it uses fewer turnover sides and has longer Top1 tenure, with almost identical full-period MDD.

## Annual returns
| Year | Economic Coverage | OLD_SAFE_K15 | OLD_SAFE_K30 | Fix15 benchmark |
|---|---:|---:|---:|---:|
| 2021 | +10.95% | +66.93% | +44.89% | +20.19% |
| 2022 | -25.78% | +7.67% | -36.48% | +18.57% |
| 2023 | -5.75% | -10.94% | -9.68% | +26.34% |
| 2024 | -8.96% | +45.82% | -0.06% | +16.51% |
| 2025 | +99.71% | +39.95% | +156.66% | +124.50% |
| 2026 partial | +122.06% | -34.30% | +88.74% | +112.80% |

The method is therefore not a general solution to early-regime weakness. Its strongest relative behavior appears in the later tail-opportunity regime.

## Dormant optionality result
The structural hypothesis succeeds on the specific mechanism it was intended to test: economically distinct dormant tools remain available even before their future regime is visible.

Examples:
- SILVER is represented by 161226 at every Stage8E decision from 2020-12-21 through 2026-09-08 because silver is a frozen economic slot, not because recent silver returns are strong.
- CRUDE_OIL is represented by 501018 at every decision over the same span.
- GOLD is represented by 518880 throughout.
- Agriculture enters once a point-in-time eligible direct product exists (159985 from the 2022-07-14 decision onward).

This is materially different from MOC, which dropped dormant silver before its later trend because silver had insufficient recent realized marginal value.

## Economic contribution diagnostic
Across the full Economic Coverage path, the largest positive slot log contributions include:
- SILVER: log contribution +0.9186 (approx +150.6% compounded if isolated by slot days);
- CRUDE_OIL: +0.2800 (approx +32.3%);
- CN_TECH_DIGITAL: +0.2558 (approx +29.2%);
- HK_OFFSHORE_BROAD_VALUE: +0.2214 (approx +24.8%);
- HK_OFFSHORE_GROWTH: +0.1826 (approx +20.0%).

The largest negative slot log contributions include:
- CN_RESOURCES_ENERGY: -0.3854;
- CN_HEALTHCARE: -0.2782;
- CN_FINANCIALS: -0.2360;
- GLOBAL_RESOURCE_EQUITY: -0.1184;
- EMERGING_EX_CHINA: -0.0974.

This shows both sides of the architecture: structural coverage successfully preserves rare winners, but forcing every economic niche into the competitive Universe also admits niches that repeatedly create harmful OLS competition.

## Interpretation
Stage8E supports economic coverage as a structural prior, not as a complete selector.

The evidence is consistent with a two-component Universe architecture:
1. a routine/core component selected for historical OLS competitive quality;
2. an economically defined optionality component that guarantees representation of distinct dormant risk sources irrespective of recent performance.

Pure Opportunity K30 has better historical total return but more competition. Pure Economic Coverage better preserves latent optionality and is more competition-efficient than K30, but has insufficient routine selection quality in 2021–2024.

The next clean question is therefore not whether to replace Opportunity with economics. It is whether a compact Opportunity Core plus a small economically mandatory optionality set can retain the tail benefits of Stage8E without forcing all 27 economic representatives to compete every day.

## Frozen decision
- Do not promote ECONOMIC_COVERAGE as a standalone replacement for Opportunity or Fix15.
- Promote `economic coverage as a structural optionality prior` to the next research hypothesis.
- Do not retune the 27-slot taxonomy based on these returns within Stage8E.
- Keep volume/amount out of economic slot value; prior-60-day amount remains only the operational same-slot representative selector.
