#!/usr/bin/env python3
"""Synchronize instrument_metadata identity sequence with the table's max(id).

The metadata table has been restored/backfilled during research work, so the
identity sequence can lag the actual primary-key maximum. Running this before a
metadata rebuild prevents duplicate-id failures while preserving all rows.
"""
from __future__ import annotations

import argparse
import os
from sqlalchemy import create_engine, text


def db_url(raw: str) -> str:
    if raw.startswith("postgres://"):
        return "postgresql+psycopg2://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg2://" + raw[len("postgresql://"):]
    return raw


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    a = p.parse_args()
    if not a.database_url:
        raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")

    engine = create_engine(db_url(a.database_url), pool_pre_ping=True)
    with engine.begin() as conn:
        row = conn.execute(text("""
            select max(id) as max_id,
                   pg_get_serial_sequence('public.instrument_metadata','id') as seq_name
            from public.instrument_metadata
        """)).mappings().one()
        if not row["seq_name"]:
            raise RuntimeError("No identity/serial sequence found for instrument_metadata.id")
        max_id = row["max_id"]
        if max_id is None:
            conn.execute(text("select setval(:seq, 1, false)"), {"seq": row["seq_name"]})
        else:
            conn.execute(text("select setval(:seq, :v, true)"), {"seq": row["seq_name"], "v": int(max_id)})
        nxt = conn.execute(text("select last_value from public.instrument_metadata_id_seq")).scalar_one()
    print({"max_id": max_id, "sequence_last_value": nxt})


if __name__ == "__main__":
    main()
