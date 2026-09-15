# OURE Stage7G — Robust30 + frozen V1 annual findings

Date: 2026-09-15
Authoritative run: `34927439106`
Artifact: `oure-stage7g-robust30-v1-annual-34927439106`
Status: frozen historical diagnostic

## Design integrity
- Frozen Robust30 construction unchanged.
- B10 reproduction guard passed exactly.
- 126-session grid anchored at the first 2022 trading session and extended backward by exact 126-session increments for the 2021 diagnostic.
- Frozen V1 only overlays pure OLS rank switches: `ResistancePct252 >= 75% AND raw ScoreDelta_new <= 0`.
- Primary transaction cost = 6 bp per side.
- Reported execution window = 2021-01-04 through 2026-09-11; final return ends at 2026-09-14.

## Year-by-year primary results (6 bp per side)

| Year | Robust30 baseline | Robust30 + V1 | V1 - baseline | Baseline MDD | V1 MDD | V1 veto days |
|---|---:|---:|---:|---:|---:|---:|
| 2021 | +1.58% | +1.58% | +0.00 pp | -16.30% | -16.30% | 0 |
| 2022 | -26.42% | -26.42% | +0.00 pp | -49.58% | -49.58% | 0 |
| 2023 | -9.74% | -9.74% | +0.00 pp | -25.63% | -25.63% | 0 |
| 2024 | +15.03% | +15.03% | +0.00 pp | -27.09% | -27.09% | 0 |
| 2025 | +73.38% | +72.63% | -0.75 pp | -17.21% | -17.06% | 4 |
| 2026 partial | +28.94% | +29.94% | +1.00 pp | -28.61% | -28.61% | 3 |

Full-period compounded return:
- baseline: +73.48%
- V1: +74.06%
- terminal difference: about +0.59 pp
- full-period MDD: both -52.34%

Turnover sides by year baseline -> V1:
- 2021: 118 -> 118
- 2022: 86 -> 86
- 2023: 82 -> 82
- 2024: 92 -> 92
- 2025: 118 -> 114
- 2026 partial: 100 -> 94

Thus V1 mainly reduced turnover late in the sample; it did not improve drawdown.

## Veto incidence is highly concentrated
There are only 7 V1 veto days in the entire requested period, all in 2025–2026. They collapse into 5 independent holding-path divergence segments.

Those five segment-level 6 bp effects were approximately:
- 2025-04-29 to 2025-05-06: -1.92 pp
- 2025-10-28: +1.48 pp
- 2026-01-19: -5.00 pp
- 2026-04-30: +8.46 pp
- 2026-05-25: -2.47 pp

V1 wins only 2/5 independent segments. Median segment alpha is negative (-1.92 pp). The positive aggregate is therefore driven by one large 2026 event, not broad consistency.

The lack of 2021–2024 vetoes is not mainly missing profile data: resistance percentile and ScoreDelta are finite for almost all switch-like events. The frozen joint condition simply almost never occurs in those Robust30 paths.

## Cost sensitivity
Full-period results:
- 6 bp: baseline +73.48%, V1 +74.06%
- 12 bp: baseline +21.24%, V1 +22.39%
- 20 bp: baseline -24.85%, V1 -23.53%

V1's relative advantage grows slightly at higher costs because it removes some turnover, but this is not evidence of better signal quality; the strategy path itself degrades strongly as assumed friction rises.

## Main V1 conclusion
The frozen Fix15 V1 does **not** transfer cleanly to Robust30.

It is too sparse to explain a meaningful improvement in the Robust30 path, does not improve MDD, and its five independent divergences are not consistently favorable. Do not add V1 to the frozen Robust30 deployment rule on this evidence. Keep it as an archived candidate overlay unless a separate, genuinely prospective validation supports it.

## Separate Robust30 finding
The backward historical extension also reveals a broader limitation of the current Robust30 method:
- 2022 is -26.42% with -49.58% within-year MDD;
- 2023 full-calendar-year is -9.74%.

This does not contradict the previously frozen Stage7B result, whose common H126 evaluation window begins in 2023-07 and was positive in 5/6 subsequent half-years. It does show that the claim "Robust30 produces stable positive returns every year" is not supported when the exact current method is extended backward through 2021–2022 and the first half of 2023.

These early years were not fresh OOS for the Robust30 research and the entire specification was developed later, so this is a retrospective robustness diagnostic rather than independent validation. Nevertheless the negative early-period result should be retained, not optimized away.

## Frozen decision
- Robust30 baseline remains unchanged for Stage7F prospective monitoring.
- V1 is **not promoted** into the deployment baseline.
- No threshold retuning is permitted from this Stage7G result.
