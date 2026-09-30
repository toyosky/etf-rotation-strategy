# Non-Leader Opportunity Study — Stage 1 Baseline

Date: 2026-09-30  
Status: Stage 1 baseline completed; diagnostic only; no production strategy change.

## Question

Historically, how many meaningful rallies occurred in assets that were not OLS Top1, and how late did the frozen 26-session OLS ranking discover them?

This study was motivated by 513290 in September 2026, but the unit of analysis is every asset in the current FixV2 risk pool rather than one security.

## Data boundary

Source: Supabase `public.daily_bars`, Tencent HFQ canonical daily bars.

Current production risk pool:

`159934, 159985, 161226, 513100, 159957, 159509, 513290, 159529, 159981, 501018, 513530, 511380, 164824`

The current Supabase replacement no longer contains full daily history for several old Fixed15 carriers (518880 / 159825 / 159915 / 513920), so Stage 1 deliberately does **not** pretend that the old Fixed15 can be reconstructed exactly from this database.

OLS matches the production raw State Map definition:

- 26 prices
- nominal half-life 10
- fit/R² weights = q²
- annualization = 250
- raw Score = annualized slope × R² when both are positive; otherwise 0
- D2 is recorded but does not affect raw rank

## Rally event definition

Primary event:

- forward 20-session close-to-close return >= +8%
- consecutive qualifying dates for the same symbol are collapsed into one event by retaining only the first date

Sensitivity thresholds: +5%, +8%, +12%.

"Captured by Top1" means the same asset becomes raw OLS Top1 at least once from the event start through the next 20 sessions.

This is an ex-post event study. Future returns define the outcome only; they are not used in the OLS state.

## Result 1 — the majority of rallies do not start as Top1

### 2025–2026

| 20d rally threshold | Events | Top1 at start | Top3 at start | Top1 within 20d | Top3 within 20d | Median Top1 delay | Median move before Top1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| +5% | 171 | 5.3% | 17.5% | 25.7% | 64.3% | 9d | +5.7% |
| +8% | 133 | 6.8% | 22.6% | 46.6% | 88.0% | 11d | +7.1% |
| +12% | 76 | 6.6% | 23.7% | 56.6% | 97.4% | 13d | +8.6% |

### 2021–2024

| 20d rally threshold | Events | Top1 at start | Top3 at start | Top1 within 20d | Top3 within 20d | Median Top1 delay | Median move before Top1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| +5% | 358 | 10.1% | 29.1% | 37.2% | 81.0% | 8d | +3.8% |
| +8% | 231 | 11.7% | 27.3% | 52.4% | 94.8% | 10d | +5.7% |
| +12% | 98 | 23.5% | 45.9% | 82.7% | 100.0% | 9d | +6.0% |

The central result is robust to the three thresholds: a strong rally usually begins outside Top1. In 2025–2026 the effect is stronger than in 2021–2024.

For +8% events in 2025–2026, only 9 of 133 events began as Top1. Even after allowing 20 sessions, only 46.6% ever reached Top1. When Top1 eventually appeared, the median asset had already risen about 7.1% from the event start.

## Result 2 — Top3 contains much more information than Top1

For +8% events in 2025–2026:

- Top1 capture within 20 sessions: 46.6%
- Top3 capture within 20 sessions: 88.0%

For +8% events in 2021–2024:

- Top1 capture within 20 sessions: 52.4%
- Top3 capture within 20 sessions: 94.8%

This does **not** imply "buy Top3". It shows that the cross-section below Top1 contains substantial opportunity information that the current single-winner execution discards.

## Result 3 — Score=0 is heterogeneous, but the first simple REPAIR rule is not yet a trading signal

A diagnostic state was tested:

`ZERO_REPAIR = Score=0 AND annual<0 AND SignedScore improves vs 3 sessions ago AND ret5>0`

The initial daily-state test does not show a robust average-return advantage over other Score=0 observations. Therefore this rule must **not** be promoted to production.

However, among +8% rally events the Score=0 starts are important because they are especially late to reach Top1.

### +8% event starts, 2025–2026

| Start state | Events | Top1 capture | Median Top1 delay | Median move before Top1 | Top3 capture |
|---|---:|---:|---:|---:|---:|
| Top1 | 9 | 100.0% | 0d | 0.0% | 100.0% |
| Top2–3 | 21 | 81.0% | 8d | +6.6% | 100.0% |
| Positive Score, rank >=4 | 40 | 37.5% | 11d | +7.1% | 92.5% |
| Score=0, preliminary repair | 10 | 50.0% | 17d | +9.7% | 90.0% |
| Other Score=0 | 53 | 30.2% | 17d | +8.9% | 77.4% |

The 513290 September 2026 case is therefore consistent with a broader structural pattern: zero/low-ranked assets can start meaningful rallies long before the 26-session OLS can promote them.

## Interpretation

Stage 1 rejects the implicit assumption:

> If an asset has a meaningful rally, OLS Top1 will usually discover it early enough.

The data instead suggest two separate questions:

1. **Opportunity coverage** — which assets are already in a meaningful move?
2. **Winner selection** — which one should actually receive capital?

Current OLS Top1 primarily answers the second question among established smooth trends. It is not a complete opportunity detector.

This does not invalidate OLS. Top1 remains more selective and has historically concentrated stronger trend states. The new finding is that the non-leader cross-section contains useful state information that should be measured rather than discarded.

## Next stages

### Stage 2A — Top3 / Top5 shadow book

Track every asset that is Top3/Top5 but not Top1:

- subsequent 5/10/20d return
- rank path
- Score path
- whether it later becomes Top1
- how much return occurred before Top1
- whether current incumbent was actually superior during the waiting interval

Goal: distinguish "useful shadow leaders" from harmless ranking noise.

### Stage 2B — Zero-state decomposition

Do not use a single hand-written REPAIR rule. Decompose Score=0 using continuous variables:

- Signed Score level
- Signed Score 1/3/5d slope
- annual slope and its change
- R² level and change
- 3/5/10d return
- distance from 20d low
- distance from 20d high
- D2 state
- volume/turnover confirmation where available

Then evaluate future 5/10/20d outcomes and transition probabilities to Top3 / Top1.

### Stage 2C — opportunity coverage metric

Define strategy-level coverage:

- share of realized rally events detected by Top1
- share detected by Top3
- detection delay
- return already realized before detection
- false-positive cost of widening observation from Top1 to Top3/Top5

This metric should become a permanent diagnostic alongside return/MDD/Top1 life.

## Production decision

No live-rule modification from Stage 1.

The correct next step is a shadow evaluation layer, not a second automatic entry rule.
