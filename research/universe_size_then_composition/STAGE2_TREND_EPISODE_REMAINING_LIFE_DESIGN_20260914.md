# New Stage 2 — Intrinsic Trend Episode Remaining-Life Mechanism

Date: 2026-09-14
Parent: New Stage1 (frozen regime-dependent Universe-size effect)
Status: frozen design before outcome inspection

## Question

Stage1 found stable K geometry but era-dependent payoff. Stage2 tests one specific mechanism without selecting K:

K increases -> an ETF may first enter a sampled Universe's OLS Top1 later in its own trend episode -> Trend Age Ratio increases -> intrinsic remaining trend life / remaining trend return falls.

At the same time, small K lowers winner coverage. Stage2 therefore tests both the late-admission mechanism and the opposing coverage mechanism.

Stage2 is hindsight structural diagnosis only. It does not produce an executable K policy.

## Frozen intrinsic trend state

Do not invent a new trend threshold.

For every ETF/date, reuse exactly the Stage1 own-state that makes `pool_score` non-null in `stage1_oracle_size_mc.build_wides`:
- annual > 0
- r2 > 0
- score > 0
- recent_drop3 is false

This state is intrinsic to the ETF and independent of sampled Universe membership or Top1 identity.

## Intrinsic trend episode

For an ETF, a trend episode is a maximal run of consecutive market trading days for which its frozen Stage1 `pool_score` is non-null.

A missing/inactive market day terminates the episode. No gap filling, minimum episode length, smoothing or threshold tuning is allowed.

For each sampled-Universe/month/symbol, use only the **first Top1 admission** of that symbol in that Universe during the month. Later re-entries of the same symbol in the same Universe/month are not separate primary admissions.

The Top1 admission signal date must lie inside an intrinsic active episode by construction.

## Frozen remaining-life labels

At first Top1 admission date d:

- `episode_start`: first trading day of the current intrinsic active run.
- `episode_end`: last trading day of that same intrinsic active run.
- `age_days`: active trading days from episode_start through d, inclusive.
- `remaining_days`: active trading days strictly after d through episode_end.
- `total_episode_days = age_days + remaining_days`.
- `trend_age_ratio = age_days / total_episode_days`.

`trend_age_ratio` uses the future episode end and is therefore diagnostic/oracle information only. It must never become an executable feature in later walk-forward work.

Primary intrinsic remaining return:
- `remaining_close_return = close(episode_end) / close(d) - 1`.
- If d is episode_end, remaining_days = 0 and remaining_close_return = 0 when prices are valid.

This is deliberately an intrinsic episode label, not downstream strategy PnL and not observed consecutive Top1 tenure.

## Stage1 event source

Use the frozen Stage1 primary artifact from run `34772895471`:
- `top1_admission_events.parquet`
- `sampled_universe_detail.parquet`
- `monthly_k_distribution.csv`

Use only `source == same_k_mc` for primary Stage2 mechanism inference. Nested deletion events are not a separate primary sample.

The Monte Carlo seed is not changed in Stage2. Stage1 seed robustness is already frozen evidence.

## Analysis unit and pseudo-replication control

ETF-event rows are not independent observations.

Procedure:
1. Deduplicate to the first admission per `(month, universe_id, symbol)`.
2. Attach intrinsic episode labels.
3. Aggregate first to `(month, k, universe_id)` mechanism summaries.
4. Aggregate across universes to `(month, k)`.
5. Treat **month** as the effective inference unit for era comparisons and bootstrap/robustness.

Do not claim statistical strength from millions of event rows.

## Primary Stage2 tests

Across all months and separately for 2021–24 and 2025–26:

1. K -> first-admission `age_days`.
2. K -> first-admission `trend_age_ratio`.
3. K -> intrinsic `remaining_days`.
4. K -> intrinsic `remaining_close_return`.
5. `trend_age_ratio` -> remaining_days / remaining_close_return.
6. K -> Stage1 winner coverage, retained as the opposing small-K mechanism.

Primary shape diagnostics are month-level Spearman relations over K and the pre-existing K30-K3 contrast where both K exist. No new K endpoint or threshold is chosen.

Use month-cluster bootstrap for era-level K30-K3 contrasts. Report point estimates and uncertainty; do not tune the episode definition if an effect is weak.

## Competition linkage

Carry forward Stage1 switching and observed Top1 tenure only as downstream competition diagnostics. They must remain distinct from intrinsic remaining trend life.

The desired mechanistic decomposition is:

K up -> winner coverage up

and simultaneously

K up -> more competitors / switches -> admission timing distribution changes -> intrinsic trend age / remaining life changes

The Stage2 conclusion must say which links are supported and which are not.

## Branch rule

Proceed after Stage2 as follows:

- If late-admission / remaining-life structure is stable across eras and explains the Stage1 payoff reversal jointly with winner coverage, Stage3 may define a low-DoF conditional size state/range.
- If K affects competition but not intrinsic admission age/remaining life, reject this specific lifetime mechanism. Do not redefine lifetime to rescue it; Stage3 must use a weaker coverage-versus-competition state.
- If the mechanism itself reverses or is unstable, classify K choice as regime/identifiability limited and do not freeze a universal K range.

No member-selection model begins in Stage2.
