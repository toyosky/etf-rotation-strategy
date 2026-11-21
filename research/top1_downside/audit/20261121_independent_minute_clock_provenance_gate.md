# 2026-11-21 post-fill label provenance gate (research-only)

Reviewed PR #7 head f490038b and `code/post_fill_excursion.mjs`. The helper now checks that supplied post-fill minute timestamps match `expectedPostFillMinuteTimes`, but **does not establish that this supplied clock is the independently verified full trading-session clock**. In the checked-in unit test the expected clock contains only `09:36`, and a single 09:36 bar passes for a 09:35 fill. This is acceptable as a synthetic unit test, **not** as evidence that a historical session is complete. A caller could supply a truncated expected list and silently obtain an understated MAE/MFE label.

## Mandatory gate before empirical OOS

1. Generate expected minute-end timestamps from an independent exchange/session calendar with the fund's actual listing, market, trading suspension and special-session metadata. Record source, as-of availability, timezone, session date, and a stable hash. Do not infer the expected set from observed market bars.
2. Explicitly verify morning and afternoon session coverage, session close, and any midday break. A complete regular mainland ETF minute-end clock for a 09:35 fill must include post-fill afternoon bars, not merely the first minute. Exceptional sessions must be documented, never silently accepted.
3. Validate that each minute bar is the intended bar-end timestamp, not a start timestamp; distinguish execution timestamp, price observation timestamp, and whether the fill price is executable. The fill-minute high/low remains excluded unless tick ordering proves it is after fill.
4. Reject labels where any expected minute bar is absent, timestamps are duplicated, out of session, nonmonotonic, or OHLC/price basis cannot be independently checked. Persist explicit rejection reasons and counts by ETF/year.
5. Separate `post_fill_price_path_proxy` from `routable_executable_holding`: PIT NAV/premium, order route, fill, and subsequent original-strategy exits/switches remain separate gates. Never upgrade the proxy merely because minute bars are complete.
6. Snapshot inputs and hash the calendar, minute files, daily files and original route configuration. Publish coverage denominators before training; retain all eligible Top1 exposure days including up/sideways/down states, with missingness and survivorship audits.

## Research status

This is a methodological audit, **not** a newly run backtest or a claim that the current code is defective for synthetic inputs. No OOS metrics or portfolio sizing result is established. Do not tune the exit function or change production rules until the data and prediction gates pass.
