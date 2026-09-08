#!/usr/bin/env python3
"""Run Asset Health V1 against the current ACTIVE asset registry.

This wrapper deliberately leaves the frozen ASSET_HEALTH_V1 calculations in
asset_health.py unchanged. It only changes universe selection: current monitor
membership comes from public.asset_universe, not from the historical strategy
run's embedded pool.

Market data may continue to exist for RETIRED, CANDIDATE and CASH_PROXY assets;
those rows are retained for research/audit but do not receive new formal health
snapshots through this entry point.
"""

from __future__ import annotations

from typing import Any

import asset_health as monitor
from supabase import Client

ACTIVE_STATUS = "ACTIVE"


def get_active_pool(client: Client, strategy_version: str) -> list[str]:
    """Return the current formal risk-asset pool from asset_universe.

    strategy_version is accepted to preserve asset_health.get_strategy_pool's
    call signature. Universe governance is intentionally independent from the
    immutable historical strategy_runs.parameters payload.
    """
    del strategy_version
    response = (
        client.table("asset_universe")
        .select("symbol,name,universe_status")
        .eq("universe_status", ACTIVE_STATUS)
        .order("symbol")
        .execute()
    )
    rows: list[dict[str, Any]] = response.data or []
    symbols = [str(row["symbol"]) for row in rows if row.get("symbol")]
    if not symbols:
        raise RuntimeError("asset_universe contains no ACTIVE assets")
    invalid = [s for s in symbols if len(s) != 6 or not s.isdigit()]
    if invalid:
        raise RuntimeError(f"invalid ACTIVE symbols in asset_universe: {invalid}")
    return sorted(set(symbols))


def main() -> None:
    # Keep the frozen V1 feature/threshold implementation intact while replacing
    # only its universe-provider boundary.
    monitor.get_strategy_pool = get_active_pool
    monitor.run(monitor.build_parser().parse_args())


if __name__ == "__main__":
    main()
