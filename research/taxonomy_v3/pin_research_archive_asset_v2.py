#!/usr/bin/env python3
"""Research-only immutable-source acquisition gate.

Never accepts a mutable release tag as the identity of a frozen research dataset.
Download a specific GitHub release asset ID, verify its bytes, and emit provenance.
Requires GH_TOKEN and pyarrow. Does not change production data or strategy.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
import pyarrow.parquet as pq

REPO = "toyosky/etf-rotation-strategy"
ASSET_ID = 741069813
SHA256 = "7a218407280309b475998668ccd3d232cfc67efda307f97db3f76fef7324b644"
BYTES = 17166998
OLD_SHA256 = "9d55f6e0a511be72609e799b19d04c1b44e2555374298bceef102a0481a067fb"


def verify(data, expected_hash=SHA256, expected_size=BYTES):
    actual = hashlib.sha256(data).hexdigest()
    if len(data) != expected_size or actual != expected_hash:
        raise ValueError(f"source mismatch bytes={len(data)} hash={actual}; expected bytes={expected_size} hash={expected_hash}")
    return actual


def fetch(url, accept, token):
    headers = {"Accept": accept, "Authorization": f"Bearer {token}",
               "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "etf-research-provenance"}
    with urlopen(Request(url, headers=headers), timeout=120) as r:
        return r.read()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        assert hashlib.sha256(b"test").hexdigest() != SHA256
        try:
            verify(b"test")
            raise AssertionError("bad bytes passed integrity gate")
        except ValueError:
            print("SELF_TEST_PASS")
        return
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("GH_TOKEN required")
    meta = json.loads(fetch(f"https://api.github.com/repos/{REPO}/releases/assets/{ASSET_ID}",
                            "application/vnd.github+json", token))
    assert meta["id"] == ASSET_ID and meta["name"] == "refreshed_daily_bars.parquet"
    assert meta["size"] == BYTES and meta["digest"] == "sha256:" + SHA256
    raw = fetch(f"https://api.github.com/repos/{REPO}/releases/assets/{ASSET_ID}",
                "application/octet-stream", token)
    verify(raw)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(raw)
    pf = pq.ParquetFile(a.output)
    schema = pf.schema_arrow
    required = {"symbol", "date", "open", "high", "low", "close", "amount"}
    assert required.issubset(set(schema.names)), f"missing columns: {required-set(schema.names)}"
    import pyarrow.compute as pc
    dates = pq.read_table(a.output, columns=["date"]).column("date")
    dates = pc.cast(dates, "timestamp[ns]")
    dmin = str(pc.min(dates).as_py())
    dmax = str(pc.max(dates).as_py())
    manifest = {
        "contract": "RESEARCH_MARKET_ARCHIVE_V2_CANDIDATE",
        "repo": REPO, "asset_id": ASSET_ID, "asset_created_at": meta["created_at"],
        "sha256": SHA256, "bytes": BYTES, "rows": pf.metadata.num_rows,
        "date_min": dmin, "date_max": dmax, "columns": schema.names,
        "old_archive_sha256": OLD_SHA256,
        "old_archive_restored": False,
        "pit_taxonomy": False,
        "warning": "New candidate version only. Do not splice with old V2 results or use in production."
    }
    a.manifest.parent.mkdir(parents=True, exist_ok=True)
    a.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
