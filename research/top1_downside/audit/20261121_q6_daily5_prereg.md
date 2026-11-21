# Q6 pre-registered protocol: no-lock daily Q90 rebalancing with minimum 5% threshold
Date: 2026-11-21. Research only; strategy and Q90 forecast outputs frozen, production unchanged. Protocol saved BEFORE reading Q6 portfolio outcomes.

## Intent
Test whether removing the historical 5 trading-interval E lock, with a 5% minimum action threshold, materially reduces or increases CAGR, max drawdown and turnover. No Top2 overlay: the de-risked slice is held in zero-interest cash, to isolate Q90 position sizing.

## Data
Use 1419 existing daily out-of-sample Q90 forecast rows (2021-01-04 to 2026-11-12), unchanged original daily Top1 route s and open-to-open return ret. The exact previously frozen E is:
Eraw=clip((1-1.1*Dbase/D)*clip(1+2*(pLoss5_full-pLoss5_vol),0,1.8),0,1) only when s nonempty. No tuning or fit. Portfolio day t weights apply to return ret[t] after t signal at close and hypothetical next open rebalance. Compare with previous Q1/Q5 cash baseline.

## Precisely distinguish 'minimum reduction of 5%' ambiguities

Main policy: **daily-min5pp**. On each day compute target cash fraction T = Eraw if Eraw >=0.05 else 0. If |T - last actual cash fraction| >= 0.05 (five percentage points, using tolerance 1e-12) update actual cash fraction to T; else hold previous actual fraction. A signaled portfolio route becomes cash (s empty) -> cash allocation resets to 0; Top1 fund change transfers risk sleeve to new Top1 but cash fraction persists unless E rule changes. Rebalance may both buy and sell according to threshold, no five-day hold period and no forced flat at 5 days.

To isolate thresholds:
- **daily-raw**: target Eraw every day, even <5%.
- **daily-Efloor5**: T=Eraw if >=5%, else 0; every day exact T (no minimum 5pp delta).
- **daily-step5**: every day Eraw, adjust only if |Eraw - last actual E|>=5pp, without separate Efloor.
- **daily-min5pp** (primary): Efloor and step5 as above.
- **lock5-raw**: existing Q90 5-interval hold: E stays frozen from start to end of 5 intervals, then reevaluate signal for a new 5-interval episode (even if E<5%).
- **lock5-Efloor**: start only when Eraw >=5%, frozen 5 intervals and released if none at next available date.
- **baseline-full**: original Top1 with no overlay; still charge historical turnover at every daily s change.

Trade cost: 0.0006 (6 basis points) per side, multiply absolute asset-weight turnover across risk-fund holdings; cash not charged. Note entry/exit to cash each costs 6bp. Annual 244 trading days.

## Evaluation
Full compounded CAGR, total return, MDD, Calmar, standard annualized vol and Sharpe without cash yield, weighted realized cash-exposure days, E adjustment count, 5pp action count, gross asset turnover and incremental total fees relative to lock5. Per-year 2021-26 time-weighted net return, MDD, action count, cash exposure. 20 trading-day year-stratified paired moving block bootstrap 2500 draws for annualized log excess daily-min5pp vs lock5-raw and Efloor variants; and drawdown episode/date analysis. Avoid treating identical daily signals as independent.

Do NOT infer improved ability to forecast risk from better realized NAV. This is a backtest of position execution without live premiums/09:31 or dynamic compounding of weights, no actual downstream Top2 reentry mechanism, cash interest excluded. The OOS forecast came from older research; 2021–2026 backtests have been inspected repeatedly and cannot be a truly untouched holdout. Show sensitivity to threshold meaning: if a user intended a minimum size of *new sells* rather than 5pp total target change, the report covers both threshold variants but the main policy is explicitly defined.

Outcomes read only after this protocol commit; no production deployment without fresh holdout and execution audit.
