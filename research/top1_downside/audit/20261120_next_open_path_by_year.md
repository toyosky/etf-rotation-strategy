# 2026-11-20 follow-up: next-open path-by-year sensitivity

Status: exploratory only; no predictive model trained.

This check extends the prior next-open MAE screen by splitting on prior 5-session decline (<=-3% versus >-3%) and calendar year, rather than pooling 2021–24 against 2025–26. The data source is Supabase public.daily_bars, 19-symbol restricted pool, signal-day fall >=2%, prior 20-day traded-amount normalization, t+1 open denominator, minimum daily low over t+1...t+5 numerator. The t+1 intraday low is included, and therefore a result can be negative even when price initially rallies; it is not an actual 14:05 entry fill. Events overlap.

Representative contrasts:
- 2022, prior five sessions NOT down >=3%: low amount n=29, future >=5% downside 3.45%; high amount n=33, 21.21%.
- 2025, prior five sessions down >=3%: low n=20, 30.00%; high n=28, 14.29%.
- 2026, prior five sessions down >=3%: low n=85, 25.88%; high n=37, 21.62%.
- 2026, prior five sessions NOT down >=3%: low n=43, 34.88%; high n=44, 38.64%.
- Some cells are tiny (e.g. 2023 prior-down low n=2) and unsuitable for generalization.

Result: the sign of a low-versus-high amount association changes across calendar years and prior-price-path regimes. The 2025 difference is not consistently reproduced in 2026. The exercise further argues against a simple universal volume filter; it does not rule out conditional predictive value after proper PIT Top1 position reconstruction and purged walk-forward evaluation.

Reproducibility: see sql/next_open_path_by_year.sql. Neither risk estimates nor hypothetical execution results should be treated as actionable. No production changes.

Priority remains obtaining a historical executable position trace (including premium and intraday gates), validating full-market archive and fitting the prespecified five-block OOS ablations. Existing source audit notes that minute bars only begin in September 2026 and historical premium records are not PIT-safe.
