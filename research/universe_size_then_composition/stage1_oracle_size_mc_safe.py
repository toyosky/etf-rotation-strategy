#!/usr/bin/env python3
"""Mechanical persistence wrapper for New Stage 1.

The frozen Stage1 experiment computes math.comb(N, K) metadata that can exceed
Arrow/int64 range. Preserve the exact combinatorial count as text; do not alter
sampling, seeds, Universe construction, Frozen OLS evaluation, or statistics.
"""
from __future__ import annotations

import stage1_oracle_size_mc as base

_original_sample_combos = base.sample_combos


def sample_combos_serialization_safe(items: list[str], choose_n: int, n: int, seed: int):
    combos, exhaustive, total = _original_sample_combos(items, choose_n, n, seed)
    return combos, exhaustive, str(total)


base.sample_combos = sample_combos_serialization_safe


if __name__ == "__main__":
    base.main()
