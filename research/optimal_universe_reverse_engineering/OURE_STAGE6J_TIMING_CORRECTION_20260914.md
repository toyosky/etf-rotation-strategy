# OURE Stage6J — Timing Correction

Date: 2026-09-14
Status: frozen_invalid_as_strict_XleT_evidence

Stage6J used calendar Jan/Jul decision points with a future126 target. That construction does not guarantee that the prior calendar half-year's future126 label has fully finished before the next Jul/Jan decision date. A January-start 126-trading-session target can extend several trading days beyond July 1.

Therefore Stage6J's `previous-period RF`, `last-3 RF ensemble`, and `last-3 unanimous-direction` results contain a small but material label-availability timing confound when interpreted as strict X<=t mapping transfer.

The numerical Stage6J results remain useful only as exploratory mapping-drift diagnostics. They are not chronological OOS evidence and cannot authorize a prospective rule or combinatorial search.

The corrected preregistered test is Stage6K `Strict Adjacent 126→126 RF Transfer`, which uses consecutive non-overlapping 126-session blocks. For every transition, the complete previous-block Y is realized before the next block decision point.
