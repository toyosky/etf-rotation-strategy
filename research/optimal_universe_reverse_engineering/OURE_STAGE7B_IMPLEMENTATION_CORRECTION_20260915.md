# OURE Stage7B implementation correction

Date: 2026-09-15
Invalidated run: `34921217226`

The first completed Stage7B run is invalid for the intended H63-vs-frozen-H126 comparison because the implementation changed the candidate-family RNG from frozen Stage7A semantics. It used `SEED=20260915` and an additional horizon-specific seed offset, so the H126 candidate libraries did not reproduce Stage7A.

This is an implementation mismatch, not a model-result decision. The invalid run must not be used for inference.

Correction frozen before re-execution:
- inherit Stage7A seed exactly: `SEED=20260914`;
- target library seed exactly `SEED + block_no * 1009` for both horizons, with no horizon-specific offset;
- H126 must reproduce the Stage7A selected independent-block returns/member choices subject only to the new chained-cost accounting;
- H63 uses the same deterministic generator rule on its own 63-session block numbering;
- no robust weights, K, pool rules, horizons, gates, costs, or other parameters change.
