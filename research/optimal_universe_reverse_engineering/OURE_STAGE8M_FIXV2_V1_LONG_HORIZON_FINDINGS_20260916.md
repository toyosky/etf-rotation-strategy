# OURE Stage8M — FixV2 + V1 Long-Horizon Findings

Date: 2026-09-16
Authoritative run: `35037031141`
Artifact: `oure-stage8m-fixv2-v1-long-horizon-35037031141`
Artifact digest: `sha256:3ac7cca828637731f34c6cc5d2ecbd4cf24da05c557d60eadefd98bfc32bd6a9`
Status: frozen historical audit

## Frozen main universe
Original Fix15 repaired only by previously frozen decisions:
- remove `159825`
- retain `159981`
- `513920 -> 513530`
- `518880 -> 159934`
- `159915 -> 159957`
- all other members unchanged
- `511220` remains the cash comparator

Risk members:
`159934,159985,161226,513100,159957,159509,513290,159529,159981,501018,513530,511380,164824`

Strict real-listing availability is used. No pre-listing proxy or backfilled carrier is allowed.

Backtest window:
- first signal: 2015-01-23
- first execution: 2015-01-26
- last execution: 2026-09-14
- last return end: 2026-09-15
- 2,829 execution sessions

## Primary full-period result, 6bp per side

| Metric | FIXV2_RAW | FIXV2_V1_75 |
|---|---:|---:|
| Cumulative return | +4074.96% | **+4390.08%** |
| Terminal wealth | 41.75x | **44.90x** |
| CAGR | 39.43% | **40.34%** |
| MDD | -38.59% | -38.59% |
| Annualized vol | 34.13% | 34.10% |
| Sharpe, rf=0 | 1.142 | **1.162** |
| Calmar | 1.022 | **1.045** |
| Turnover sides | 761 | **749** |
| Switches | 414 | **408** |
| Mean risk tenure | 6.81d | **6.92d** |

V1 improves terminal wealth by about 7.55% relative to RAW, but it does not change the dominant full-period MDD because the 2026 drawdown is untouched.

## Year-by-year, 6bp/side

| Year | RAW | V1 | V1 alpha pp | V1 MDD | Turnover sides | Veto days |
|---|---:|---:|---:|---:|---:|---:|
| 2015 | +2.99% | +2.99% | 0.00 | -7.22% | 22 | 0 |
| 2016 | +10.68% | +10.68% | 0.00 | -17.62% | 35 | 0 |
| 2017 | +2.10% | +2.10% | 0.00 | -9.22% | 42 | 0 |
| 2018 | +11.23% | +11.23% | 0.00 | -19.06% | 38 | 0 |
| 2019 | +27.54% | +27.54% | 0.00 | -19.20% | 62 | 0 |
| 2020 | +64.29% | +60.05% | -4.24 | -21.14% | 70 | 1 |
| 2021 | +31.12% | +34.93% | +3.81 | -15.27% | 62 | 1 |
| 2022 | +25.67% | +23.87% | -1.80 | -33.41% | 78 | 1 |
| 2023 | +21.31% | +21.31% | 0.00 | -11.59% | 60 | 0 |
| 2024 | +57.17% | **+65.57%** | +8.40 | -28.12% | 92 | 5 |
| 2025 | +110.48% | **+115.42%** | +4.94 | -22.43% | 92 | 3 |
| 2026* | +132.79% | **+134.99%** | +2.20 | -38.59% | 96 | 1 |

*2026 partial through return end 2026-09-15.

V1 is inactive in performance terms through 2019. It hurts 2020 and 2022, helps 2021 and especially 2024-2026. This is not a uniformly positive yearly overlay.

## V1 mechanism diagnostics
Frozen V1 rule:
`ResistancePct252 >= 75% AND raw ScoreDelta_new <= 0` vetoes only a pure rank switch.

Across the whole 2015-2026 sample:
- 12 veto signal-days
- 7 actual divergence segments versus RAW
- V1 wins 4/7 divergence segments
- sum of local divergence alpha: +7.34pp
- median divergence alpha: +1.08pp

Largest beneficial segment:
- 2024-12-06 through 2024-12-12
- RAW switched to `159529`
- V1 retained `513100`
- local alpha: +5.06pp

Largest harmful segments:
- 2020-07-22: V1 retained silver instead of switching to 159957, alpha -2.47pp
- 2022-01-26: V1 retained crude oil instead of switching to 159981, alpha -1.35pp

Conclusion: V1 is a modest competition filter, not the source of the strategy's core return.

## Full-period return-source decomposition, V1 6bp
Contributions use additive log-wealth contribution; shares therefore sum correctly at the portfolio level.

| Symbol | Role/name | Holding days | Switch-ins | Net log contribution | Share of net log growth | Isolated net compound |
|---|---|---:|---:|---:|---:|---:|
| 161226 | silver | 245 | 40 | +1.119 | **29.4%** | +206.2% |
| 513100 | Nasdaq 100 | 540 | 49 | +0.678 | **17.8%** | +97.0% |
| 501018 | crude oil | 411 | 52 | +0.596 | **15.7%** | +81.5% |
| 159957 | ChiNext | 263 | 41 | +0.412 | 10.8% | +50.9% |
| 159509 | Nasdaq technology | 146 | 21 | +0.407 | 10.7% | +50.2% |
| 159981 | energy-chemical | 107 | 20 | +0.198 | 5.2% | +21.9% |
| 513530 | HK dividend | 106 | 17 | +0.154 | 4.0% | +16.6% |
| 159985 | soymeal | 212 | 28 | +0.146 | 3.8% | +15.7% |
| 159934 | gold | 293 | 48 | +0.117 | 3.1% | +12.4% |
| 159529 | S&P consumer | 37 | 10 | +0.096 | 2.5% | +10.0% |
| 513290 | Nasdaq biotech | 81 | 15 | +0.056 | 1.5% | +5.7% |
| 511380 | convertible bonds | 15 | 6 | -0.017 | -0.4% | -1.7% |
| CASH | cash state/cost | 235 | 34 | -0.020 | -0.5% | -2.0% |
| 164824 | India | 138 | 28 | **-0.136** | **-3.6%** | **-12.7%** |

Top three return sources — silver, Nasdaq100 and crude oil — contribute about 62.6% of total net log growth. Top five contribute about 80.7%. Return is diversified across several regimes but still materially concentrated in a handful of tail-opportunity assets.

The long-run positive contribution of `159981` is important: despite weak post-2021 marginal evidence, its full-period log contribution is +0.198 and it is the largest positive source in 2021. This supports retaining it as a regime-dependent opportunity asset rather than treating it as permanently bad.

`164824` is the clearest persistent full-period drag in this frozen audit, but Stage8M does not promote any new deletion based on this same-sample result.

## Major yearly return sources, V1
- 2015: Nasdaq100 positive; gold main drag.
- 2016: gold dominates; silver main drag.
- 2017: Nasdaq100 positive; crude oil main drag.
- 2018: crude oil dominates; ChiNext and Nasdaq100 detract.
- 2019: ChiNext, gold and silver positive; crude oil detracts.
- 2020: Nasdaq100, ChiNext, silver and energy-chemical drive gains; India is main drag.
- 2021: energy-chemical is the largest positive contributor; crude oil and India also positive.
- 2022: crude oil leads; India is main drag.
- 2023: soymeal and Nasdaq100 lead; HK dividend detracts.
- 2024: HK dividend, ChiNext and Nasdaq technology lead; biotech detracts.
- 2025: silver dominates; Nasdaq technology is second.
- 2026*: silver and crude oil dominate; ChiNext is the largest drag.

## Cost stress
V1-75 remains profitable under all frozen friction assumptions:

| Cost per side | Cumulative | CAGR | MDD | Sharpe |
|---|---:|---:|---:|---:|
| 6bp | +4390.08% | 40.34% | -38.59% | 1.162 |
| 12bp | +2762.51% | 34.82% | -40.19% | 1.044 |
| 20bp | +1469.35% | 27.79% | -42.26% | 0.886 |
| 30bp | +639.39% | 19.51% | -44.76% | 0.689 |

At every tested cost, V1 remains above RAW because it has slightly fewer turnover sides and a modest positive gross-path effect.

## V1 threshold stress, 6bp
No post-hoc threshold selection is allowed.

| Resistance threshold | Cumulative | CAGR | MDD | Switches | Veto days |
|---|---:|---:|---:|---:|---:|
| 70% | +4608.72% | 40.93% | -38.59% | 406 | 14 |
| **75% frozen** | **+4390.08%** | **40.34%** | **-38.59%** | 408 | 12 |
| 80% | +4338.81% | 40.20% | -38.59% | 410 | 5 |

All three thresholds remain above RAW (+4074.96%), which supports the sign of the mechanism. Although 70% is historically highest, Stage8M explicitly does not retune the frozen 75% threshold from this result.

## 159981 universe sensitivity, 6bp

| Universe | Variant | Cumulative | CAGR | MDD | Sharpe | Turnover |
|---|---|---:|---:|---:|---:|---:|
| with 159981 | RAW | +4074.96% | 39.43% | -38.59% | 1.142 | 761 |
| with 159981 | V1 | **+4390.08%** | **40.34%** | -38.59% | 1.162 | 749 |
| without 159981 | RAW | +3995.07% | 39.19% | **-34.72%** | 1.157 | 749 |
| without 159981 | V1 | +4241.96% | 39.92% | **-34.72%** | **1.174** | 739 |

Interpretation: retaining 159981 modestly raises terminal return/CAGR, but removing it materially reduces MDD and slightly improves Sharpe. Its role is a genuine return-versus-drawdown tradeoff, not a clear yes/no member-quality result.

## Tail-risk stress
V1 primary path:
- worst single session: -19.23%
- worst rolling 5 sessions: -21.56%
- worst rolling 20 sessions: -24.11%
- dominant full-period MDD: -38.59%

Largest drawdown episodes:
1. peak 2026-06-03 -> trough 2026-08-19: -38.59%; still unrecovered at 2026-09-15.
2. peak 2022-03-09 -> trough 2022-05-10: -33.41%; recovered 2023-07-04; 320 sessions underwater.
3. peak 2024-07-10 -> trough 2024-09-30: -28.12%; recovered 2024-10-09.
4. 2016-08-01 -> 2018-04-04: -21.31%; recovery 2018-10-09; 531 sessions underwater.

V1 materially improves one 2024-2025 drawdown episode (RAW about -21.70% versus V1 about -18.14%) but cannot address the 2026 dominant drawdown because no relevant V1 divergence occurred during that loss sequence.

## Real carrier availability caveat
The strict new-carrier retrotest is deliberately harsh: the replacement ETF does not receive a historical proxy before it existed.

First finite OLS scores:
- 159934 gold: 2014-01-21
- 513100 Nasdaq100: 2013-07-05
- 161226 silver: 2015-09-25
- 501018 crude oil: 2016-08-18
- 159957 ChiNext replacement: 2018-02-28
- 164824 India: 2018-11-06
- 159985 soymeal: 2020-02-20
- 159981 energy-chemical: 2020-05-07
- 511380 convertible: 2020-06-19
- 513530 HK dividend: 2022-06-02
- 513290 biotech: 2022-10-11
- 159509 Nasdaq technology: 2023-09-12
- 159529 S&P consumer: 2024-03-18

Therefore the actual number of OLS-ready risky members expands approximately:
- 2015: 2 at start, 3 by year-end
- 2016: 3 -> 4
- 2017: 4
- 2018: 4 -> 6
- 2019: 6
- 2020: 6 -> 9
- 2021: 9
- 2022: 9 -> 11
- 2023: 11 -> 12
- 2024 onward: 13

This is why 2015-2017 results are much weaker than older Fix15 historical tests: the new `159957` carrier did not exist, and Stage8M does not fall back to old `159915`. Stage8M is a strict current-carrier retrotest, not a role-continuity backtest.

## Frozen conclusion
1. The repaired carrier set plus frozen V1 has a strong long historical path under the same daily engine: +4390% at 6bp/side, CAGR about 40.3%, but still with a severe -38.6% MDD.
2. V1 is positive in aggregate and robust to 70/75/80 resistance thresholds and higher trading costs, but the effect is small and event-sparse. It should remain an execution overlay rather than be treated as the main alpha engine.
3. The dominant economic alpha sources are silver, Nasdaq100, crude oil, ChiNext and Nasdaq technology. This supports the thesis that the small fixed universe works because it preserves a few structurally distinct tail-opportunity channels.
4. 159981 is regime-dependent: positive long-run contribution and return uplift, but worse MDD. Do not permanently delete it based only on 2021-2026.
5. 164824 is the strongest full-period drag, but no further same-sample deletion is authorized by Stage8M.
6. The 2015-2017 results are not a fair test of the ChiNext economic role because 159957 was not yet listed. A separate, explicitly frozen role-continuity diagnostic would be required if the research question is historical asset-role robustness rather than literal current-carrier robustness.
