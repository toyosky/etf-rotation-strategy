# OURE Stage7B — Quarterly Robust30 Horizon and Friction Audit

Date: 2026-09-15
Status: preregistered before outcome inspection

## Question
Does shortening the frozen Robust30 refresh cycle from 126 sessions (~6 months) to 63 sessions (~3 months) improve adaptation without sacrificing robustness once actual OLS turnover and Universe-refresh friction are accounted for?

## Frozen variants
Both variants keep K=30 and the Stage7A robust score formula unchanged.

### H126 baseline
- block length: 126 sessions;
- training history: immediately previous 3 completed 126-session blocks;
- target holding / Universe-lock period: next 126 sessions;
- score: `0.5 * median(P1,P2,P3) + 0.5 * Q25(P1,P2,P3)`;
- target-specific candidate library: frozen Stage6G/7A family generator using only X<=t data;
- point-in-time common-pool rule: ETF must be available at all 3 training starts and target start.

### H63 quarterly variant
- block length: 63 sessions;
- training history: immediately previous 3 completed 63-session blocks;
- target holding / Universe-lock period: next 63 sessions;
- same score formula, K=30, candidate generator and common-pool logic;
- no threshold or weight tuning.

## Fair comparison window
Primary path comparison uses the exact common calendar span covered by Stage7A H126 targets B04..B09: from the H126 B04 decision date through the end of H126 B09. Because 126=2*63 and both grids start from the same 2022 anchor, this corresponds to 6 H126 blocks versus 12 H63 blocks.

## Primary outcomes
1. Chained OLS path total return at 6bp per side, with block-boundary positions chained rather than re-entered from cash mechanically.
2. Same path at 12bp and 20bp per side.
3. Same-calendar 126-session paired returns: each two consecutive H63 blocks are compounded and compared with one H126 block.
4. Worst 126-session paired return and positive paired-block share.
5. Total turnover sides, annualized turnover sides, mean Top1 tenure.
6. Universe refresh friction:
   - mean successive K30 Jaccard;
   - mean members replaced per refresh;
   - number/share of refresh boundaries where new Universe changes the day-1 OLS target versus keeping the old Universe;
   - number/share where the previously held ETF is removed from the new Universe.
7. Cross-sectional OOS robustness diagnostics for H63: median Spearman between robust score and next63 set value, positive-IC share, Top50 actual percentile, selected Top1 actual percentile.

## Interpretation rules
This is a horizon diagnostic, not a parameter search.

- `quarterly_preferred`: H63 beats H126 at 6bp and remains ahead at 12/20bp, while worst paired126 return is not materially worse (more than 5 percentage points) and turnover inflation is not enough to reverse the result.
- `halfyear_preferred`: H126 has higher 6bp return and/or H63 loses its advantage under modest cost stress, or H63 materially worsens the worst paired126 block.
- `mixed_horizon_tradeoff`: H63 improves return/adaptation but pays meaningfully in turnover or downside, or vice versa.

No alternative 63-day lookback count, robust weights, quantile, K, refresh threshold, member-retention rule, or hybrid 6M-core/3M-maintenance rule may be tested as a rescue inside Stage7B after results are seen.
