# Healthy Trend Universe Attribution

Date: 2026-09-09
Status: completed

## Question
Why do apparently healthy OLS trends have materially different forward returns in the curated fixed15 universe versus Cluster90?

This is a mechanism/attribution diagnostic only. It does not introduce a production filter or optimize thresholds.

## Frozen definitions
- Data: Supabase `public.daily_bars`.
- OLS: exact current 26-price, nominal HL10 implementation from the full-market research engine.
- Cluster90: monthly point-in-time liquidity-first 120d return-correlation dedup, rho>=0.90 treated as duplicate.
- Fixed15: frozen original 15-asset research universe.
- Healthy new leader: new non-cash Top1 entry with `ScoreDelta>0` and valid `ResistancePct252<75%`.
- Primary: 2021-2024; posterior: 2025-2026.
- No threshold search.

## Main result 1 — asset identity dominates inside Cluster90
Healthy Cluster90 new leaders, 2021-2024:

| Group | n | Fwd5 | Fwd10 | Fwd20 | Avg signal tenure |
|---|---:|---:|---:|---:|---:|
| Fixed15 members | 20 | +0.56% | **+0.67%** | -0.63% | 5.55d |
| Outside fixed15 | 144 | +0.05% | **-0.47%** | -0.12% | 4.49d |

Symbol-equal-weighted Fwd10 remains separated: fixed15 +0.19% vs outsiders -0.68%.

Posterior 2025-2026 is more extreme: fixed15 members +7.86% Fwd10 vs outsiders -0.37%, though the fixed15 sample is only 9 entries and includes strong commodity episodes.

## Main result 2 — the same fixed15 assets do not deteriorate in the large universe
Restricting to fixed15 symbols only in 2021-2024:
- when selected by Cluster90: Fwd10 +0.67%, average tenure 5.55d;
- when selected by the fixed15 selector: Fwd10 +0.23%, average tenure 8.35d.

Thus the large-universe argmax does not inherently make the same asset bad. The main damage comes from the additional non-fixed15 leaders admitted by Cluster90.

## Main result 3 — paired same-date comparison is strong
On 140 primary-period dates where Cluster90 entered a healthy outside-fixed15 leader while the fixed15 selector had another eligible risk asset:
- Cluster90 outsider Fwd10: about -0.55%;
- fixed15 alternative Fwd10: about +0.79%;
- paired difference: **-1.33pp**;
- Cluster90 outsider beat the fixed15 alternative only 41.4% of the time.

In 2025-2026 the paired difference is even more negative (-3.75pp), largely amplified by strong fixed-universe commodity/trend episodes. Excluding oil/silver still leaves a material fixed15 advantage in both periods.

## Main result 4 — not explained by ETF product expansion
Among outside-fixed15 healthy Cluster90 leaders in 2021-2024:
- symbols without 252 pre-2021 bars: Fwd10 -0.06%;
- symbols with >=252 pre-2021 bars: Fwd10 -0.86%.

So the failure is not mainly caused by newer ETF products entering the market later.

## Main result 5 — high opportunity-set breadth is harmful in 2021-2024, but not stable across regimes
For healthy Cluster90 leaders in 2021-2024, splitting at the period median candidate count:
- lower breadth: Fwd10 +0.55%;
- higher breadth: Fwd10 -1.22%.

But in 2025-2026 the sign reverses (higher breadth +1.34%, lower breadth -0.28%). Candidate-count Spearman relationship with Fwd10 is weak. Therefore breadth describes the regime but is not a robust standalone filter.

## Interpretation
The evidence points primarily to an **opportunity-selection / asset-prior problem**, not a simple Top1-ranking or execution problem.

Cluster90 can find leaders that look healthy by all of the local trend diagnostics — positive ScoreDelta, low overhead resistance, long remaining raw OLS life — yet many outside-fixed15 assets still have near-zero/negative forward drift. The curated fixed15 contains assets whose trend states historically carried more residual forward return.

This does **not** prove that the fixed15 was selected ex ante without hindsight. It shows that OLS health alone is insufficient to reconstruct the useful asset prior.

## Next diagnostic
Test structural asset priors rather than new OLS thresholds: first cross-sectional independence/common-factor exposure, then—if that is insufficient—walk-forward asset-level historical trendability.

## Reproducibility
- Code: `research/healthy_trend_universe_attribution.py`
- Workflow: `.github/workflows/healthy-trend-universe-attribution.yml`
- Successful run: `34342389700`
- Preregistration commit: `706d15eabdf953b207f2f0d34f400128ef5dfb96`
