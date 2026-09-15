# OURE Stage8F — Challenger Oracle + Event Study Findings

Date: 2026-09-15
Authoritative run: `34952907602`
Artifact: `oure-stage8f-challenger-oracle-34952907602`
Status: frozen historical diagnostic

## Frozen setup
Stage8E 27-slot Economic Base and repaired Opportunity Core15 were unchanged. Each day there was at most one actionable outsider: the highest-score Economic Base representative outside Core15, executable only if its raw OLS score exceeded both the best Core15 risk score and cash score. Future information never chose which outsider became challenger.

The preregistered narrow oracle could only choose between the normal Core15 target and that single challenger using the next-session realized gross return. Normal 6bp/side costs were then applied.

## Oracle ceiling
Full period 2021–2026 partial:
- Core15: +114.62%, MDD -44.54%, turnover sides 571, mean tenure 4.68d.
- Narrow next-session oracle: +161,738.19%, MDD -21.54%, turnover sides 1,123, mean tenure 2.41d.

The magnitude is deliberately non-tradable and should not be interpreted as an achievable return. The oracle changes the Core target on 350 of 1,381 sessions and uses perfect next-session information. Its only legitimate interpretation is that the binary outsider-vs-Core decision contains very large theoretical information value; the gate problem is not economically trivial.

There were 747 executable challenge days (54.09% of sessions) grouped into 184 challenge episodes. Thus Economic Base outsiders are not a rare edge case: without a gate they would frequently contest Core leadership.

## No-gate diagnostic (post-run deterministic, no tuning)
A simple deterministic diagnostic was computed from the frozen event output: always admit the executable challenger, with no future information and the same 6bp/side cost.

Full period:
- Always-admit challenger: +178.95%, MDD -57.37%, turnover 707, mean tenure 3.84d.
- Core15: +114.62%, MDD -44.54%, turnover 571, mean tenure 4.68d.

Annual always-admit vs Core15:
- 2021: +35.14% vs +66.93%
- 2022: -23.31% vs +7.67%
- 2023: -17.75% vs -10.94%
- 2024: -7.29% vs +45.82%
- 2025: +93.36% vs +39.95%
- 2026 partial: +82.54% vs -34.30%

Therefore outsider admission has a strong regime dependence: harmful in 2021–2024, strongly helpful in 2025–2026. The full-period gain does not establish a stable gate.

## Forward-alpha event study
Daily challenger-minus-Core-leader mean alpha:
- ALL: +0.03% (1d), +0.05% (3d), +0.01% (5d), +0.17% (10d); medians are zero/slightly negative and positive shares are below 50% at all four horizons.
- 2021–2024: -0.23%, -0.38%, -0.64%, -1.23% at 1/3/5/10d.
- 2025–2026: +0.46%, +0.78%, +1.12%, +2.65% at 1/3/5/10d.

Episode-start means show the same broad era split: negative in 2021–2024 and positive on average in 2025–2026, but positive-event hit rates are not consistently above 50%.

This is direct evidence that the Economic Base contains valuable dormant tools, but a raw OLS takeover by those tools is not universally beneficial.

## Feature separation
Across all daily challenge observations, preregistered univariate features are weak classifiers. Best AUC separation is only about 0.55 at 1d, 0.54 at 3d, 0.54 at 5d and 0.53 at 10d. No feature is close to a robust standalone gate.

At episode starts there are stronger local signals, but they are not stable across eras:
- 2025–2026, 3d: score gap AUC 0.698; gap delta 0.695; challenger slope 0.683; challenger score delta 0.674.
- 2021–2024, 3d: score gap only 0.564 and gap delta reverses direction (raw AUC 0.382); challenger slope also reverses (0.455).

This blocks promotion of a fixed acceleration/gap rule: the apparent recent-era signal is not historically invariant.

## Amount result
Amount does not support the simple `more volume = healthier activation` story in this sample.
- Daily overall amount AUC is approximately random.
- At episode starts, higher amount ratio often predicts *worse* relative challenger performance: raw AUC 0.349/0.376/0.313 in 2021–2024 at 1/5/10d and 0.409/0.445/0.337 in 2025–2026.

This is descriptive, not a license to invert V1. It does mean amount should not be promoted as a positive Economic-Base activation gate from Stage8F.

## Economic-slot diagnostics
The strongest outsider slot is SILVER: 60 challenge days, 14 episodes, mean alpha +1.46% at 1d and +3.61% at 5d, useful share 64.3%/58.0% at 1d/5d. HK offshore broad/value and crude oil are also positive on average. Many other slots are negative, including China resources/energy, emerging ex-China, healthcare and financials. Gold challenges are negative on average in this specific challenger definition despite gold's valid structural role in the Economic Base.

This confirms that `deserves a permanent economic slot` and `should immediately displace the Core leader when its score is higher` are distinct questions.

## Frozen decision
Stage8F does NOT justify a live Challenge Gate yet.

What is established:
1. Economic outsiders contain large theoretical optionality; the gate problem is worth studying.
2. Always admitting them is regime-dependent and materially worsens 2021–2024.
3. Current simple X<=t variables do not provide stable cross-era discrimination.
4. Amount is not validated as a positive activation confirmation feature here.

Next research, if continued, should focus on why outsider usefulness changes across regimes rather than optimize thresholds on score gap/amount. Any Stage8G model must be separately preregistered and should test regime-invariant or explicitly point-in-time regime-conditioned structure without using future era labels.