# Q7 preregistration: asymmetric Q90 execution and small-ticket friction
**Frozen before calculating Q7 outcome** · 2026-11-21

## Main decision
Can we keep the Q90-forecast risk-worsening response as fast as Q6, but stop unnecessary same-week full buybacks and fee-heavy round trips? Never change source Q90 forecasts, original OLS Top1 routes or full-year data. This study is **cash-only Q90 sizing**; Top2 capital redeployment is excluded. Research branch only, no live changes.

## Input and timing
Same archived 2021-01-04 through 2026-11-12 daily Q90 predictions (1419 rows) as Q6. On signal date t after close: raw E_t = clip((1-1.1 Dbase_t/D_t)×clip(1+2(Pfull5_t-Pvol5_t),0,1.8),0,1) for nonempty top1 route; E=0 when route empty. Execution proxy on **next open** using archived per-day open-to-next-open Top1 return. The risk sleeve follows the existing daily Top1 route. Cash earns zero. No use of future market outcomes for controls.

**Risk activation floor**: target T_t=E_t if E_t>=0.05, otherwise 0.
**Size units** are portfolio percentage points, not percentage of the unliquidated balance.

## Fixed baseline policies
A lock5: old historical Q90 all-positive E trigger, 5-market-interval fixed total E, release/recheck after fifth interval.
B daily5: T_t every day; change executed total E only if |T_t-actual E|>=0.05, else hold. No hold lock.
All-in Top1: no Q90 E, as context only.

## Primary asymmetric mechanism C (preregister)
- Q90 risk worsens: if T_t >=actual E+0.05, set actual E=T_t **immediately**, cancel confirmation counter.
- Q90 risk eases: whenever T_t<=actual E-0.05, maintain a consecutive **below-current-position-target** confirmation counter. First consecutive close: no buyback. Starting at the second consecutive qualifying close: buy back **at most 0.10 of total portfolio per day**, never more than (actual E-T_t). Re-evaluate condition every day; counter stays active as long as current T is still >=5pp below actual E, so restoration may take multiple days. If gap drops below 5pp, reset counter. There is no five-day hold and no automatic full reset.
- If the risk Top1 route is empty, actual E=0 and counter resets because risk sleeve is zero.
- Tiny leftover E<5pp may remain due to the five-pp buffer until a later qualifying target swing; record stale fraction/time. Do NOT silently force a full restoration.
- Risk deterioration by under5pp from actual position: no action, reset relief counter.

## Primary cost-aware asymmetric D (preregister)
Identical fast risk-worsening sells as C. For buybacks use **10pp minimum gap** (at 20,000 yuan = 2,000 yuan nominal) and two consecutive confirming closes; each buyback capped 10pp. For smaller residual when T_t is exactly zero, after **three consecutive days at zero raw target** clear the entire remainder regardless of small-ticket limit to avoid permanently stale cash. If T_t is positive with <10pp gap, hold buffer. Maintain separate consecutive below-target and zero-risk counters; risk-worsening sale resets both. A 5pp trigger sell always has priority over minimizing commissions.

D is not a learned cost-optimal control; 2,000 yuan minimum and 3-day dust cleanup are interpretable structural sensitivity policies, fixed before outcomes.

## Stress / ablations before outcomes
C1 uses one qualifying close, cap10pp; C3 requires three qualifying closes, cap10pp. All other parameters exactly match C; results are sensitivity only, not choose-the-winner. Also Cbuy20 uses two qualifying days but max20pp buyback as a speed sensitivity. C is the main comparator, D the cost-aware main comparator.

## Costs
1. **Q6 original cost proxy**: 6bp per asset-side weight turnover, charged on position change, including normal Top1 symbol switches. Verify A/B reproduce Q6 exact CAGR/MDD.
2. **2万元 initial account with 5元 minimum ticket**: each nonzero ETF buy or sell ticket costs max(0.06% of traded notional, ¥5); notional = 20,000 * equity-index at decision * |weight change| (start 20,000, compound as NAV changes). Actual cost as fraction of current NAV is sum(ticket fee / current NAV yuan). No charge for movements solely in bookkeeping cash; if switching Top1, both sell and buy are separate tickets; no stamp tax. This is an explicit hypothetical commission schedule, not known user's actual fee. This scenario ignores taxes, spreads, premium and tracking errors.
3. **Conservative high friction**: tier2 min ticket ¥5 + extra 4bp each traded ETF side for spread/slippage, relative to 6bp base already included, not replacing it.

For comparability compute every policy under every fee scenario, with NAV-dependent ticket min only under fee scenario 2/3. Count asset trades, buyback/extra sell decisions, days of nonzero E, mean E, cumulative fees, total asset turnover, and sub-¥2000 attempted buybacks, year by year.

## Outcomes and uncertainty
Full compounded CAGR, MDD, annualized vol, Calmar, yearly returns and drawdowns, worst daily and 5d rolling losses, turnover and explicit 2025/2026 split, shadow execution risk. Compare C/D versus lock5 and daily5 on **identical** dates/cost model. Annual-stratified 20-market-day circular block pair bootstrap 2,000 resamples on annualized log return difference (not naïve event independent). Evaluate drawdown paths and the sign and magnitude of missed rebounds. Separate cost-benefit from forecast false positives; avoid tuning after results. If C/D not reliably better, record failure.

## Limitations
All research period 2021–26 previously used repeatedly; this is not a fresh unseen holdout. Previous Q90 historical OOS provenance is inherited. Next-open proxy from pre-archived data; no actual ETF lot-size, minimum-ticket rule, dynamic premiums/LOF NAV, limit-up fills, or stop-hour audit. Annualized returns not real-world promised returns. Do not modify production jobs.
