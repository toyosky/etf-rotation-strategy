"""Resumable auxiliary fund profiles. Never promote these to official evidence.

python -m research.taxonomy_v3.collect --universe ... --cache /.../profiles
Each successful response is saved atomically with parsed facts, URL and SHA256.
Errors are saved too; --retry-errors explicitly retries them. No database writes.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import requests
from bs4 import BeautifulSoup


def parse_profile(html: str, symbol: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    facts = {}
    # Some responses omit </td> before the next <th>. Walk headers rather
    # than assuming well-formed sibling pairs (the fund-type cell is nested).
    for th in soup.select("th"):
        td = th.find_next_sibling("td")
        if td is not None:
            key = th.get_text(" ", strip=True)
            if key in {"基金代码", "基金全称", "基金简称", "基金类型", "基金管理人",
                       "业绩比较基准", "跟踪标的", "发行日期", "成立日期/规模"}:
                facts[key] = td.get_text(" ", strip=True)
    if not re.match(re.escape(symbol) + r"(?:\D|$)", facts.get("基金代码", "")):
        raise ValueError("profile symbol missing/mismatch; blocked or changed HTML")
    if not facts.get("基金全称"):
        raise ValueError("missing legal fund name")
    return facts


def collect_one(symbol: str, cache: Path, retry_errors: bool = False) -> dict:
    path = cache / f"{symbol}.json"
    if path.exists():
        old = json.loads(path.read_text())
        if old.get("status") == "ok" or not retry_errors:
            return old
    url = f"https://fundf10.eastmoney.com/jbgk_{symbol}.html"
    row = dict(symbol=symbol, source_url=url, source_kind="AUXILIARY",
               observed_at=datetime.now(timezone.utc).isoformat())
    try:
        r = requests.get(url, timeout=(8, 20))
        r.raise_for_status()
        # This endpoint declares UTF-8 in HTML; do not use ISO-8859-1 default.
        r.encoding = "utf-8"
        row.update(status="ok", sha256=hashlib.sha256(r.content).hexdigest(),
                   facts=parse_profile(r.text, symbol))
        import gzip
        with gzip.open(cache / f"{symbol}.html.gz", "wb") as f:
            f.write(r.content)
    except Exception as exc:
        row.update(status="error", error=f"{type(exc).__name__}: {exc}")
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(row, ensure_ascii=False, indent=2))
    tmp.replace(path)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", type=Path, required=True)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--retry-errors", action="store_true")
    args = ap.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    symbols = sorted({r["symbol"] for r in json.loads(args.universe.read_text())})
    counts = {"ok": 0, "error": 0}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(collect_one, s, args.cache, args.retry_errors) for s in symbols]
        for i, f in enumerate(as_completed(futures), 1):
            row = f.result()
            counts[row["status"]] += 1
            if i % 100 == 0 or i == len(symbols):
                print(json.dumps(dict(completed=i, total=len(symbols), **counts)), flush=True)


if __name__ == "__main__":
    main()
