# OURE Stage6K calendar-H2 prospective draft — INVALIDATED

Date: 2026-09-14
Status: frozen_invalid_timing_leakage

This preregistration is invalid and must not be used as OOS evidence or as a future promotion test.

Reason: the proposed 2026H2 decision date was 2026-07-01, while the immediately preceding 2026H1 target was defined as the next 126 trading sessions from the January decision point. That future126 label is not guaranteed to be fully realized by July 1. Therefore using 2026H1 feature->Y correlations or an RF trained on 2026H1 at the July 1 decision creates a small but real timing/label-availability leak.

The first lock run 34864518145 and its prediction artifact are preserved only as an invalidated audit trail. They must never be evaluated, promoted, regenerated as evidence, or used to authorize search.

The corrected experiment is `OURE_STAGE6K_ADJACENT_126_TRANSFER_DESIGN_20260914.md`, which uses consecutive non-overlapping 126-session blocks so every training label is fully realized before the next decision point.
