# New Stage5 Findings

Date: 2026-09-14
Source run: 34792039084
Artifact: universe-size-stage5-34792039084
Status: frozen
Decision: reject_adaptive_low_dof_composition_on_same_history

## Primary result

Stage5 tested two pre-registered executable K15 composition rules against the frozen Stage1 random-K15 distribution.

Current-score rule, 68 months:
- mean minus random-K15 mean: +0.972 pp/month
- bootstrap 95%: [-1.144, +3.217] pp
- above random P90: 14.7%
- mean random percentile: 48.2%

Lagged-inclusion rule, 67 months:
- mean minus random-K15 mean: +1.235 pp/month
- bootstrap 95%: [-1.330, +4.222] pp
- above random P90: 14.9%
- mean random percentile: 47.9%

Neither rule has a stable positive paired advantage over random same-K.

## Era split

2021-24:
- current-score minus random: -0.696 pp; bootstrap [-2.650, +1.351]
- lagged-inclusion minus random: -0.861 pp; bootstrap [-2.692, +0.898]

2025-26:
- current-score minus random: +4.975 pp; bootstrap [-0.052, +10.635]
- lagged-inclusion minus random: +6.162 pp; bootstrap [-0.788, +14.582]

The later-era point estimates are positive, but uncertainty still crosses zero. Do not promote either rule.

## External diagnostics

Fix15, retained only as a pre-existing external benchmark, is the only benchmark with a clearly positive historical paired advantage over random K15 overall:
- overall minus random: +4.146 pp
- bootstrap 95%: [+1.134, +7.607]
- 2021-24: +2.693 pp, bootstrap [+0.381, +5.128]
- 2025-26: +7.632 pp, bootstrap crosses zero

Full-market has no stable advantage over random K15.

This does not authorize reverse-engineering or retuning Fix15 on the same history.

## Frozen conclusion

Stage4 showed large K15 composition hindsight dispersion but weak single-symbol reproducibility and nearly zero adjacent-month persistence. Stage5 confirms that neither contemporaneous score ranking nor one-month-lagged inclusion value stably captures that headroom.

Freeze the research line as follows:
1. Size effects are real but regime-dependent.
2. Low-DoF point-in-time size direction is not identifiable.
3. History-only best-K does not stably improve on the K15 engineering anchor.
4. Fixed-K15 composition has large hindsight headroom.
5. Symbol-level inclusion value is weakly reproducible and non-persistent.
6. The two simple executable member rules do not stably beat random same-K.

Do not escalate feature search, model capacity, lag search, K search, or interaction mining on this same history.

Conservative fallback: K15 engineering anchor + a pre-existing frozen structural member scheme such as the Fix15 benchmark + Frozen OLS. This is not a claim that K15 or Fix15 is globally optimal.

Any renewed adaptive-learning attempt should use genuinely new forward observations, with Stage1-5 treated as frozen design evidence rather than another tuning set.
