# OURE Stage8P — Defensive Anchor / 511220 Audit

Date: 2026-09-16
Authoritative run: `35102909825`
Artifact: `oure-stage8p-defensive-anchor-35102909825`
Artifact digest: `sha256:5ca4e30a110254771d3f3b5bb75d3ecfac443cd05c85dc8cc75bcc57007cdde6`
Status: exploratory diagnostic; no carrier promotion

## Why this audit was needed

Stage8M retained `511220` as the OLS cash comparator, but the historical accounting mapped the defensive state to `None/CASH` with 0 gross return. Therefore two economically different roles were conflated:

1. `511220` as a **threshold / regime comparator** deciding whether a risky Top1 is strong enough to hold.
2. `511220` as an **investable defensive carrier** actually held when risky assets fail that threshold.

Stage8P isolates those two effects, then compares several pre-specified defensive roles without selecting a winner post hoc.

Frozen risky universe and V1-75 are unchanged from Stage8M. Cost = 6 bp per side.

## 1. Clean isolation: same 511220 signal path, zero-cash vs actually holding 511220

### Full available history

| Overlay | Zero-cash CAGR | Hold-511220 CAGR | CAGR delta | Zero-cash MDD | Hold-511220 MDD | Zero-cash Sharpe | Hold Sharpe | Turnover sides zero/held |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| RAW | 39.43% | 39.70% | +0.27pp | -38.59% | -39.08% | 1.142 | 1.147 | 761 / 829 |
| V1-75 | 40.34% | 40.61% | +0.27pp | -38.59% | -39.08% | 1.162 | 1.166 | 749 / 817 |

There are 235 defensive-state sessions in the full V1 sample.

Interpretation:
- `511220` is not irrelevant as an investable asset: despite 68 extra transaction sides, actually holding it raises long-run CAGR by about 0.27 percentage points and slightly raises Sharpe.
- The improvement is not a drawdown improvement. The dominant MDD becomes slightly worse (-39.08% vs -38.59%).
- Therefore the strongest historical value of `511220` is primarily its **comparator / gating role**, with a smaller positive long-run carry contribution when actually held.

### Year-level pattern for V1-75

The held version is strongly beneficial in some early defensive episodes but not uniformly beneficial:

- 2015: 2.99% -> 7.43%
- 2017: 2.10% -> 3.26%
- 2018: 11.23% -> 11.70%
- 2016: 10.68% -> 10.08%
- 2020: 60.05% -> 58.19%
- 2023: 21.31% -> 21.02%
- 2024: 65.57% -> 65.17%
- 2026 partial: 134.99% -> 132.54%

This explains the aggregate result: historical carry helped, but recent defensive windows are too short for the extra buy/sell legs to reliably pay for themselves.

## 2. Defensive-role substitution, common 2023+ window, V1-75

These candidates were fixed by economic role before observing results:
- `511220` 城投债
- `511010` 国债
- `511260` 10年国债
- `511360` 短融
- `511520` 政金债
- `511580` 国债政金债
- `159001` 货币ETF was attempted but cannot function as an OLS comparator in the current price dataset because its stored close is identically 1.000, so it produces no meaningful OLS trend signal.

Results when the defensive carrier is actually held:

| Defensive | CAGR | MDD | Sharpe | Calmar | Defensive days |
|---|---:|---:|---:|---:|---:|
| 511220 城投债 | 91.88% | -39.08% | 1.643 | 2.351 | 37 |
| 511010 国债 | 90.45% | -38.78% | 1.625 | 2.333 | 26 |
| 511260 10年国债 | 88.07% | -38.80% | 1.597 | 2.270 | 24 |
| 511360 短融 | 91.27% | -35.51% | 1.637 | 2.570 | 29 |
| 511520 政金债 | 89.95% | -39.18% | 1.619 | 2.296 | 26 |
| 511580 国债政金债 | 91.80% | -39.33% | 1.625 | 2.334 | 14 |

Important: this is a same-sample exploratory comparison and is **not** a replacement ranking.

The main structural observation is that `511360` short-credit behaves differently: it gives up only modest CAGR relative to `511220` in 2023+ while reducing MDD materially (-35.51% vs -39.08%), producing the highest Calmar among the tested defensive roles. That is enough to justify a separate frozen robustness test, but not enough to replace `511220` now.

## 3. Transaction-cost lesson

For every 2023+ defensive candidate, actually holding the defensive ETF underperformed the same comparator path with a literal 0%-return cash state after 6bp-per-side costs.

Examples under V1-75:
- 511220: 92.77% zero-cash CAGR -> 91.88% held
- 511360: 91.78% -> 91.27%
- 511010: 91.07% -> 90.45%

The mechanism is straightforward: recent defensive episodes are sparse and short. Turning `risk -> cash -> risk` into `risk -> defensive ETF -> risk` adds two extra transaction legs around many brief defensive episodes; current bond carry is often too small to offset those costs.

Therefore `cash comparator` and `cash carrier` should remain separate concepts in the architecture.

## Frozen interpretation

1. `511220` was indeed an important omitted research dimension. Stage8M already used it as a comparator, but not as a true held asset.
2. Its largest contribution is the **OLS gating threshold**, not its bond return stream.
3. Actually holding 511220 improves full-history CAGR by about +0.27pp, but does not improve the dominant MDD and is mildly detrimental in several recent years because of extra friction.
4. Do not automatically change the live strategy to always buy 511220 during defensive states.
5. `511360` short-credit is the most interesting next defensive-role hypothesis because its 2023+ drawdown profile is materially different. It requires a separately frozen, longer-history / role-continuity or walk-forward validation before any promotion.
6. The strategy architecture should explicitly separate:
   - **defensive comparator**: the score threshold used to reject weak risky Top1s;
   - **defensive carrier**: what is actually held after the rejection decision.

This distinction should be preserved in future FixV2 research and in the website documentation.
