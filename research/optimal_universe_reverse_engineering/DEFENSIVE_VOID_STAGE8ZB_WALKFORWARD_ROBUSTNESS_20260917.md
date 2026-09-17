# Stage8ZB — Pre-Void incumbent freeze / deterioration robustness audit

## Purpose

Validate the Stage8ZA mechanism without choosing the best historical streak ex post.

Frozen mechanism:

1. When Market Regime first enters `DEFENSIVE_VOID`, freeze the actual pre-Void incumbent (prior signal day's output position).
2. Do not accept new cross-sectional leadership switches while Void persists.
3. Incumbent must first fail the 511220 hurdle (`incumbent raw OLS score <= 511220 raw OLS score`).
4. For the routed variants, both Breadth and Gap percentile must also remain below their Void-entry values for N consecutive Void signal days.
5. N = 1 / 2 / 3 are robustness neighbors, not optimized inside any evaluation period.
6. Once deepening + invalidation is satisfied, use 513500 only when it is historically eligible (>=365 days since listing) and its raw OLS score exceeds 511220; otherwise use 511220. Hold the routed target until Void exit.

Base is frozen Stage8M FixV2/V1(75), formal 26-day weighted log-price OLS, half-life 10, 6 bp per side.

## Key subperiod results versus ORIGINAL_V1

### 2015–2022

Original V1: CAGR 21.13%, MDD -33.41%, Sharpe 0.848.

- Freeze incumbent, invalid -> cash: CAGR 20.96% (-0.16pp), MDD -32.20% (+1.21pp drawdown improvement), Sharpe essentially flat.
- Deepen1 + invalid -> route: CAGR 23.23% (+2.10pp), MDD -31.30% (+2.11pp), Sharpe +0.058.
- Deepen2 + invalid -> route: CAGR 22.81% (+1.69pp), MDD -31.98% (+1.43pp), Sharpe +0.043.
- Deepen3 + invalid -> route: CAGR 22.74% (+1.62pp), MDD -33.42% (essentially unchanged), Sharpe +0.034.

Conclusion: the early sample does not collapse. N=1/2/3 all improve CAGR; N=1/2 also improve MDD. This supports the mechanism rather than one isolated streak value.

### 2023–2026 partial

Original V1: CAGR 93.78%, MDD -38.59%, Sharpe 1.666.

- Freeze incumbent, invalid -> cash: CAGR 111.64% (+17.86pp), MDD -27.72% (+10.86pp), Sharpe +0.216.
- Deepen1: CAGR 103.78% (+10.00pp), MDD -28.54% (+10.05pp), Sharpe +0.123.
- Deepen2: CAGR 103.07% (+9.29pp), MDD -28.54% (+10.05pp), Sharpe +0.115.
- Deepen3: CAGR 104.43% (+10.65pp), MDD -28.54% (+10.05pp), Sharpe +0.130.

Conclusion: recent-sample risk improvement is strong and not sensitive to N=1/2/3.

## Finer splits

### 2015–2018

- Deepen1: CAGR +1.37pp vs base, but MDD slightly worse by ~0.21pp.
- Deepen2: CAGR +2.21pp, MDD worse by ~0.72pp.
- Deepen3: CAGR -0.38pp, MDD worse by ~0.72pp.

This is the weakest early block. It argues against claiming monotonic improvement in every regime.

### 2019–2022

- Deepen1: CAGR +2.99pp, MDD +2.11pp improvement, Sharpe +0.057.
- Deepen2: CAGR +1.00pp, MDD +1.43pp improvement.
- Deepen3: CAGR +4.14pp, MDD essentially unchanged, Sharpe +0.071.

### 2023–2024

This is the important counterexample:

Original CAGR 43.79%, MDD -28.12%.

- Freeze-invalid-cash: CAGR 48.16% (+4.37pp), MDD -18.29% (+9.84pp improvement).
- Deepen1: CAGR 40.44% (-3.35pp), MDD -21.56% (+6.56pp improvement).
- Deepen2: CAGR 39.53% (-4.26pp), MDD -22.31% (+5.81pp improvement).
- Deepen3: CAGR 41.26% (-2.52pp), MDD -20.81% (+7.31pp improvement).

Interpretation: `freeze incumbent` remains useful, but the second-stage US Carrier route is not return-improving in every subperiod. The robust part is the admission/hold logic; the fallback destination still needs separate treatment.

### 2025–2026 partial

Original CAGR 174.91%, MDD -38.59%.

All Deepen1/2/3 are identical here: CAGR 215.24% (+40.33pp), MDD -28.54% (+10.05pp), Sharpe +0.296.

This period contributes a large fraction of the recent full-sample uplift, so it must not be allowed to dominate the interpretation.

## Turnover

Across all tested windows, the freeze/deepening variants reduce switching substantially versus ORIGINAL_V1. This is consistent with the economic mechanism: Void primarily disables unnecessary leadership competition rather than forcing a defensive trade.

## Stage conclusion

The central hypothesis survives the robustness audit:

> Entering `DEFENSIVE_VOID` is not itself a sell signal. It is better interpreted as a cross-sectional competition freeze. Continue to hold the pre-Void incumbent while it remains valid; only consider leaving after the incumbent itself fails and the Void structure persists/worsens.

Evidence strength differs across components:

- **Strongest / most robust:** freeze the actual pre-Void incumbent; suppress new Top1 switching inside Void.
- **Supported:** require incumbent failure before leaving.
- **Supported but not uniformly return-positive:** require Void deepening before routing; N=1/2/3 neighborhood is broadly stable.
- **Not yet fully robust:** the post-failure destination `513500 vs 511220`. 2023–2024 favors cash/freeze more than US Carrier, while 2025–2026 strongly favors the routed structure.

Therefore Stage8ZB does **not** justify freezing a final `Void -> US Carrier` rule yet. It does justify promoting `Void -> freeze incumbent -> wait for actual deterioration` into the strategy-design candidate set.

Next audit should isolate the destination decision after true Void failure: compare 511220, regional Carrier, and historical point-in-time regional OLS only on the small subset of events that pass both deterioration + incumbent-failure gates. This avoids contaminating the robust freeze mechanism with a weaker destination-selection rule.
