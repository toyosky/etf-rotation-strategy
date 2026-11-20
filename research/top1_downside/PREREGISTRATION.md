# Top1 downside risk: preregistration and run ledger

Status: IN PROGRESS — design frozen before model experiments.
Created 2026-11-20. Research branch only. No production strategy modifications.

## 2026-11-20 explicit user correction — primary policy is continuous conditional withdrawal

**This section supersedes any older reference to 100/70/40/0, 0/30/60/100 or fixed exit bands as the proposed dynamic risk control.** Earlier discrete pilots are historical experiments/baselines, not the requested final model.

### Normal exposure and conditional action

- When the frozen Top1 router authorizes a risk-asset holding, the *unmodified normal target* is 100% invested. High historical volatility alone must **not** lower ordinary exposure.
- Add a downside-state gate G(t) constructed from at-time-t observable deterioration. If G(t)=false, exit weight E(t)=0 and the original authorized Top1 remains at 100% (or original frozen route remains applicable).
- If G(t)=true, use a calibrated predictive *continuous* exit fraction E(t) in [0,1], with target risk-asset fraction H(t)=1-E(t). The model's decision is **how much to withdraw**, not a new baseline allocation.
- Keep original V1, Void/defensive, premium and intraday execution rules authoritative. These may independently prohibit holding a risk ETF; the overlay cannot override them.

### Candidate primary mathematical rule (to test, not adopted)

- Estimate from an **as-of-t, properly purged chronological OOS** model the conditional future 5-session adverse-excursion distribution using actual executable-period reference price where possible. Let L_5=max(0,-MAE_5) and D_5(t)=Q_{0.90}(L_5|X_t) be the predicted 90th percentile loss severity, with X_t containing OLS/trend, price path, turnover, short/long realized/downside volatility and market context. Test q=0.8/0.9/0.95 and 3/5/10 sessions, and ES as independent risk measures.
- Predetermine an absolute portfolio loss budget B for the risky sleeve. **1%, 2%, 3% are scenario values only**, not user-chosen live limits. For G(t)=true, primary candidate E(t)=clip(1-B/max(D_5(t),epsilon),0,1); for G(t)=false, E(t)=0. This produces continuous fractions, e.g. at B=2% and predicted D_5=3%, E=33.3%; D_5=5%, E=60%; D_5=8%, E=75%. These are **arithmetic examples, not forecasts or preset tiers**.
- Do not claim B is a guaranteed realized-loss cap: quantile coverage, liquidity, execution slippage, overnight gaps and tail beyond q remain. An extreme tail may justify full exit through original router or independently justified hard constraint, but do not sneak in discretionary discrete thresholds.
- Calibrate quantile predictions, compare pinball loss/coverage against OLS-only and vol-only models, check conditional risk beyond unconditional high-volatility scale. Select all model hyperparameters, G(t), q, B and trade hysteresis *inside training folds*, never on test outcomes. If OOS signal quality is insufficient, retain the original Top1 rules.
- Return to 100% as G(t) clears / D_5 falls. Evaluate continuous re-entry and execution-aware no-trade bands/transaction cost controls versus delayed full re-entry; prevent turnover without converting the primary exit function into fixed bands.
- Compare frozen 100% Top1 baseline against continuous budget-driven exit, simple stop, fixed exit, raw vol-only exit and alternative smooth nonlinear exit mapping. Report OOS full portfolio CAGR, MDD, Calmar, net results after costs, days with exits, average E(t), drawdown left-tail, missed rebounds and rebound delay. Evaluate per ETF/asset type/year and explicitly 501018 oil LOF vs 159981; distinguish underlying oil risk from secondary-market premium risk.
- In the absence of PIT-executable 2021–2025 positions and premium, distinguish daily-bar *research proxies* from genuine executable Top1 portfolio tests. Historical data/auditing gates remain in force.

## Research question
For the actual frozen Top1 executable holding at decision time t, do path, trend, volume, volatility and market-context features improve out-of-sample prediction of future adverse excursions, and can risk-based sizing improve realized portfolio drawdown without unacceptable opportunity cost?

## Dataset and audit gates
- Primary: reconstruct the *executable* historical Top1 holding with the correct period-specific 26-day half-life-10 log-price OLS, V1 / Void / defensive / premium and intraday execution routing. **Current production strategy has retired C2; no fictitious C2+Void hybrid.** Distinguish original challenger, final target, actual human holdings.
- Secondary: all ETF down-day events, explicitly not equated to held Top1.
- Verify as-of adjusted OHLC, volume units, ETF inception, gaps, splits, NAV/premium availability, slippage, delistings and survivorship. Current public.daily_bars coverage is only 19 symbols (2021–2026), not full market. Investigate historic Parquet/Release/Storage.
- If executable historical holding cannot be reconstructed, do NOT claim primary validation.

## Outcomes and information cutoff
End-of-day t features only; target determination and purchase/sale execution must follow the period-specific code, including 09:31 gap gate, 14:00 sell and 14:05 buy (rather than assuming unconditional next-open purchases). At horizons 3, 5, 10 sessions: min subsequent executable-period low relative to execution price (MAE); binary loss thresholds 3%, 5%, 8%; conditional quantiles, duration to trough and recovery, missed rebounds. Explicitly label the alternative signal-close-relative descriptive outcome and never conflate it with executable MAE. Mark censored episodes.

## Prespecified feature blocks
B0 OLS-only: beta, R², fitted deviation, score/gap where available.
B1 price path: returns 1/3/5/10/20, downside streak, speed, prior peak drawdown, rebound age, gap, range.
B2 volume: lagged 20-session relative volume and turnover, price-volume interaction, OBV proxies, liquidity. Independently test B0+B1+B2 vs B0+B1.
B3 volatility: 5/10/20 realized and downside vol, ATR, semivariance, expansion, extreme moves.
B4 market: point-in-time breadth/regime, cross-sectional dispersion, risk-relative bond/market proxies, correlation.
No future index membership, delayed NAV, news or fundamentals allowed in X.

## Statistical protocol
- Purged chronological walk-forward, 10-session minimum label embargo at train/test boundaries; first viable OOS block determined by data availability. Report 2021–24 vs 2025–26 and annual slices without implying 2021–24 were all out-of-sample.
- Baseline constant event-rate and OLS-only; sequential ablation B0, B0+B1, +B2, +B3, +B4; test interactions on training folds only.
- Models: regularized logistic and quantile regression first; shallow gradient-boosted trees only as complexity check. Preprocessing and missing-value policy fit on train only.
- Brier, log loss, PR-AUC, ROC-AUC secondary, calibration, pinball loss, risk stratification; cluster/block bootstrap for dependent events and uncertainty; control comparisons/multiple testing; by-year, by-asset, leave-one-ETF-out sensitivity.
- Compare frozen 100% Top1 baseline with continuously sized conditional withdrawal E(t) as the primary candidate; fixed fractional exits, volatility targeting and fixed stops are **comparators only**. Run dynamic portfolio simulations only after predictive OOS increment is shown; include transaction costs, correct execution gates, turnover, gap and missed-rebound costs. No production deployment without user approval.

## Stop / acceptance criteria
Archive exact inputs, provenance, code, reproducible commands, year/event counts, feature ablations, robustness and honest null results. Explicit decision: accepted, rejected or insufficient evidence. Stop automation after final report; if irrecoverable access/coverage failure, document limitation and stop rather than looping indefinitely.

## Run ledger
2026-11-20 initial run:
- Checked repository research root: no existing research/downside_risk directory, avoiding duplication.
- Current production Actions latest run was Fundamental Audit Trigger #44576203650, unrelated to this experiment.
- Created isolated research branch research/top1-downside-20261120.
- This file is the preregistration; no model fitting, historical execution reconstruction, or strategy performance result is claimed.
- Next: audit historical data sources and frozen execution code, implement reproducible feature/label construction and chronological tests.

## Execution 2 amendment (2026-11-20, before predictive fitting)
- Audited production `strategy/main.py`: current strategy ID `FIXV2_V1_75_VOID_ROUTE_BANK14_INTRADAY_S1_PREMIUM10`; code header explicitly retires old C2. The initial generic C2 reference above has been corrected as a source-audit finding, not an outcome-based threshold optimization.
- Daily-bar approximations and signal-close descriptive outcomes must not be called exact historical executable holdings. Minute data only begins 2026-09-14; premium history currently has 0 PIT-safe rows. See `audit/20261120_source_and_screen.md`.
- Executed initial SQL exploration at `sql/exploratory_volume_path.sql`, but no OOS model has been fitted. Continue with reconstructability audit first.
- GitHub research commits: 28c8b2ea (SQL diagnostic), a74fb5f4 (source audit), and this amendment.
