"""Cache official exchange lists, fail visibly on incomplete pagination.

SSE INDEX_NAME is the tracked-index field, SZSE nhzs is the fitted index code.
These are current snapshots, NOT evidence for past tracking mandates.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import requests

SSE = "https://query.sse.com.cn/commonQuery.do"
SZSE = "https://www.szse.cn/api/report/ShowReport/data"


def get(cache: Path, key: str, url: str, params: dict, referer: str):
    path = cache / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    r = requests.get(url, params=params, headers={"Referer": referer}, timeout=(8, 30))
    r.raise_for_status()
    payload = r.json()
    obj = dict(source_url=r.url, observed_at=datetime.now(timezone.utc).isoformat(),
               sha256=hashlib.sha256(r.content).hexdigest(), payload=payload)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    tmp.replace(path)
    return obj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, required=True)
    args = ap.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    sse = get(args.cache, "sse", SSE,
              dict(sqlId="COMMON_JJZWZ_JJLB_L", type="inParams", CATEGORY="F000"),
              "https://etf.sse.com.cn/")
    if not sse["payload"].get("result"):
        raise RuntimeError("SSE returned no funds")
    def page(n):
        return get(args.cache, f"szse-{n:03d}", SZSE,
                   dict(SHOWTYPE="JSON", CATALOGID="1945", TABKEY="tab1", tab1PAGENO=n),
                   "https://www.szse.cn/")
    first = page(1)
    meta = first["payload"][0]["metadata"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        rest = list(pool.map(page, range(2, int(meta["pagecount"])+1)))
    rows = [r for p in [first]+rest for r in p["payload"][0]["data"]]
    if len(rows) != int(meta["recordcount"]):
        raise RuntimeError(f"SZSE partial response {len(rows)} != {meta['recordcount']}")
    if len({r['sys_key'] for r in rows}) != len(rows):
        raise RuntimeError("SZSE duplicate pages/symbols")
    def lof_page(n):
        return get(args.cache, f"szse-lof-{n:03d}", SZSE,
                   dict(SHOWTYPE="JSON", CATALOGID="1945_LOF", TABKEY="tab1", tab1PAGENO=n),
                   "https://www.szse.cn/")
    first_lof = lof_page(1)
    lof_meta = first_lof['payload'][0]['metadata']
    with ThreadPoolExecutor(max_workers=4) as pool:
        lof_rest = list(pool.map(lof_page, range(2, int(lof_meta['pagecount'])+1)))
    lof_rows = [r for p in [first_lof]+lof_rest for r in p['payload'][0]['data']]
    if len(lof_rows) != int(lof_meta['recordcount']) or len({r['sys_key'] for r in lof_rows}) != len(lof_rows):
        raise RuntimeError('SZSE incomplete/duplicate LOF pages')
    def listing_page(n):
        return get(args.cache, f"listings-{n:03d}", SZSE,
                   dict(SHOWTYPE="JSON", CATALOGID="1105", TABKEY="tab1", tab1PAGENO=n),
                   "https://www.szse.cn/")
    first_listing = listing_page(1)
    listing_meta = first_listing['payload'][0]['metadata']
    with ThreadPoolExecutor(max_workers=4) as pool:
        listing_rest = list(pool.map(listing_page, range(2, int(listing_meta['pagecount'])+1)))
    listing_rows = [r for p in [first_listing]+listing_rest for r in p['payload'][0]['data']]
    if len(listing_rows) != int(listing_meta['recordcount']) or len({r['sys_key'] for r in listing_rows}) != len(listing_rows):
        raise RuntimeError('SZSE incomplete/duplicate listing pages')
    get(args.cache, "sse-indices", "https://query.sse.com.cn/commonSoaQuery.do",
        dict(sqlId="DB_SZZSLB_ZSLB", isPagination="false"), "https://etf.sse.com.cn/")
    registry = get(args.cache, "cnindex-indices", "https://www.cnindex.com.cn/index/selectOnlineIndexCode",
                   {}, "https://www.cnindex.com.cn/")
    known = {r['indexcode'] for r in registry['payload']['data']}
    codes = sorted({r['nhzs'].strip().split()[0] for r in rows+lof_rows if r['nhzs'].strip()} & known)
    def detail(code):
        return get(args.cache, f"cnindex-{code}", "https://www.cnindex.com.cn/index/selectIndexByCode",
                   dict(codeValue=code), "https://www.cnindex.com.cn/")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(detail, codes))
    print(json.dumps(dict(sse=len(sse["payload"]["result"]), szse_etf=len(rows), szse_lof=len(lof_rows))))


if __name__ == "__main__":
    main()
