# Full-market walk-forward candidate-pool research — 2026-09-09

## Question
Can the full ETF market be screened point-in-time for healthy, not-overmature OLS trends, then ranked by the original OLS score?

## Engine
- Source: `public.daily_bars`, 633 ETFs, 726,035 rows.
- Exact 26-price OLS implementation from the frozen research engine.
- Base tradeability and D2 conditions unchanged.
- Daily research execution: close(t) signal -> open(t+1) execution -> open(t+2) mark.
- Cost: 6 bp per buy/sell side.
- Walk-forward thresholds use only strictly earlier raw OLS episode starts.
- Natural quintiles only: bottom 20% health exclusion, top 20% maturity exclusion.

## Step 1 — episode lifetime evidence
The strongest stable start-state predictors of longer remaining trend life were:
1. `slope_delta`
2. `current_resid`
3. `ret5`
4. `dist_high20`

Raw `score` and `slope` were not monotone: extreme high values often corresponded to shorter remaining MA10/mom5 life, especially in 2025-2026.

## Step 2 — naive full-market Top1 fails
Same daily engine:

| Universe | 2021-2024 net | 2025-2026 net | Full 2021-2026 net | MDD |
|---|---:|---:|---:|---:|
| Full 633 raw Top1 | -67.6% | -38.9% | -80.2% | -82.9% |
| Original fixed15 | +35.9% | +44.7% | +96.7% | -30.9% |

This sanity check shows the daily engine itself is not the source of the full-market failure. Expanding from a curated small universe to 633 ETFs and taking the raw maximum OLS score creates a severe extreme-value / winner's-curse problem.

## Step 3 — frozen episode health gate
Health admission at episode start was frozen for the raw OLS episode.

Admission rates, 2021+:
- H1 (`slope_delta` >= historical Q20): 77.4%
- H2 (+ `current_resid` >= Q20): 76.1%
- H4 (+ `ret5`, `dist_high20` >= Q20): 63.9%

Frozen health gates improved 2025-2026 materially but did not robustly improve 2021-2024 portfolio returns. Longer trend life alone is therefore not equivalent to higher portfolio return when the final selection is still the maximum raw score across hundreds of ETFs.

## Step 4 — maturity must be entry-only
A daily hard maturity veto improved gross returns but created near-daily switching (~1,270 switches over 1,377 trading days), so costs destroyed net returns.

Corrected architecture:
- health = episode-start admission, frozen;
- maturity = dynamic buy-veto;
- an existing holding is grandfathered while its raw OLS trend remains eligible;
- a stronger admissible entrant can still replace the current holding.

Entry-only H4 + dynamic Score/Slope Q80 improved the full-market result to approximately flat net:
- 2021-2024: +6.0%
- 2025-2026: -6.0%
- Full 2021-2026: -0.4%
- MDD: -44.1%

This is a large improvement over raw full-market Top1, but still inferior to fixed15.

## Step 5 — point-in-time correlation dedup
To test whether duplicate/similar ETFs cause the remaining extreme-value problem, each month was deduplicated using only data available before the month:
- prior 120 trading-day close-return correlation;
- previous-day universe eligibility;
- previous-day 60d average amount;
- greedy representatives sorted by liquidity.

Two non-optimized robustness thresholds were tested: correlation >=0.95 and >=0.90 treated as near-duplicates.

Representative counts:
- 0.95: mean ~40.5 monthly representatives, median 18
- 0.90: mean ~28.7 monthly representatives, median 14

### Main results

| Variant | 2021-2024 net | 2025-2026 net | Full net | Full gross | MDD | Switches |
|---|---:|---:|---:|---:|---:|---:|
| Dedup95 + H4 + dynamic Score80 | +37.2% | +20.8% | +65.8% | +116.4% | -39.4% | 228 |
| Dedup95 + H4 + dynamic Score/Slope80 | +38.5% | +18.9% | +64.7% | +117.3% | -39.1% | 237 |
| Dedup90 + H4 + dynamic Score80 | +14.2% | +15.1% | +31.4% | +65.9% | -38.8% | 198 |
| Dedup90 + H4 + dynamic Score/Slope80 | +14.7% | +19.4% | +37.0% | +73.6% | -38.5% | 201 |

The 0.95 and 0.90 tests are both positive, so the improvement is not confined to one exact correlation threshold. However, annual results remain uneven: 2022 and 2023 are weak, and Dedup95 remains negative in 2026 while Dedup90 is around flat/slightly positive.

## Interpretation
1. The dynamic-universe idea is viable, but **raw all-market Top1 is not**.
2. The main failure when expanding from 15 to 633 ETFs is not only trend timing. It is also a cross-sectional extreme-value problem amplified by duplicate ETFs.
3. Episode-start health information is useful, but should be used as an **entry qualification layer**, not as a daily sell rule.
4. Extreme Score has information as a **buy-veto**, but forcing daily exits causes unacceptable turnover.
5. Point-in-time dedup is essential before allowing OLS to rank the full market.

## Current best architecture to test next

```text
Master Universe
  -> point-in-time liquidity/tradeability
  -> point-in-time correlation dedup (representatives)
  -> episode-start health admission
       slope_delta / current_resid / ret5 / dist_high20
  -> dynamic maturity buy-veto
       extreme Score (and optionally slope)
  -> original OLS score ranking
  -> Top1
  -> existing execution layer / V1
```

## Not yet production-ready
- Current 633-symbol Master Universe has survivorship bias from present-day fund-scale screening.
- Correlation dedup is monthly and purely price-based; index/fund metadata could produce cleaner duplicate groups.
- Thresholds have not been tuned and should not be optimized on 2021-2026.
- Annual robustness is not yet strong enough to replace the fixed universe.
- V1 / minute-level execution has not yet been layered onto the full-market candidate engine.

## Recommended next test
Do not tune Q20/Q80 or choose 0.95 because it has the highest backtest. Next run a leave-theme/leave-cluster robustness audit and inspect 2022/2023/2026 failure episodes. The objective is to determine whether residual performance is concentrated in a few ETF clusters or whether the candidate architecture has genuine cross-cluster breadth.
