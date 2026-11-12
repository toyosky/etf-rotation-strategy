#!/usr/bin/env python3
"""Fetch the *official CSI* current index catalog, without inventing identities.

CSI's published exportExcel/indexAll/CH is also used by AKShare's
index_csindex_all. This collector stores raw workbook and a normalized JSON
snapshot with SHA-256 and observation time. If unavailable, exits nonzero.
The result is a CURRENT snapshot only; not a historical index rulebook.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import time

import pandas as pd
import requests

ENDPOINT = "https://www.csindex.com.cn/csindex-home/exportExcel/indexAll/CH"
PAYLOAD = {
    "sorter": {"sortField": "null", "sortOrder": None},
    "pager": {"pageNum": 1, "pageSize": 10},
    "indexFilter": {
        "ifCustomized": None, "ifTracked": None, "ifWeightCapped": None,
        "indexCompliance": None, "hotSpot": None, "indexClassify": None,
        "currency": None, "region": None, "indexSeries": ["1"],
        "undefined": None
    }
}


def read_catalog(data: bytes) -> list[dict]:
    if len(data) < 10000 or not data.startswith(b"PK"):
        raise ValueError("CSI response was not a nonempty XLSX workbook")
    t = pd.read_excel(BytesIO(data), dtype=str)
    # CSI calls columns 指数代码, 指数名称 in its public current master.
    # Never guess an unknown schema or convert codes to integers.
    required={"指数代码","指数名称"}
    if not required.issubset(set(t.columns)):
        raise ValueError(f"CSI export changed schema; columns={list(t.columns)}")
    records=[]
    for _,r in t.iterrows():
        code=str(r["指数代码"] if pd.notna(r["指数代码"]) else "").strip()
        name=str(r["指数名称"] if pd.notna(r["指数名称"]) else "").strip()
        if code and name and code.lower()!="nan" and name.lower()!="nan":
            code=code.zfill(6) if code.isdigit() else code
            records.append({"index_code":code,"index_name":name})
    if len(records) < 500:
        raise ValueError(f"CSI catalog suspiciously incomplete: {len(records)}")
    # Do not turn collisions into arbitrary first-row wins; quarantine
    # ambiguous codes and reject repeated identical rows separately.
    by_code={}
    for r in records:
        by_code.setdefault(r["index_code"],set()).add(r["index_name"])
    conflicts={k:sorted(v) for k,v in by_code.items() if len(v)>1}
    if conflicts:
        raise ValueError(f"Official CSI catalog has conflicting names for {len(conflicts)} codes, sample={list(conflicts.items())[:8]}")
    return [dict(index_code=k,index_name=next(iter(v))) for k,v in sorted(by_code.items())]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path,required=True,
                    help="JSON inside official snapshot directory, e.g. csindex-catalog.json")
    ap.add_argument("--raw",type=Path,required=True,
                    help="Raw official .xlsx, retained for evidence")
    ap.add_argument("--offline-raw",type=Path,
                    help="Reparse an existing frozen raw XLSX without a network call")
    ap.add_argument("--observed-at",help="Only for trusted prior offline captures; prohibited for live mode")
    args=ap.parse_args()
    if args.offline_raw:
        if not args.observed_at:
            ap.error("--offline-raw requires an existing evidence observation timestamp")
        raw=args.offline_raw.read_bytes()
        observed=args.observed_at
    else:
        if args.observed_at:
            ap.error("Cannot backdate a fresh HTTP capture")
        session=requests.Session()
        last=None
        for i in range(3):
            try:
                resp=session.post(ENDPOINT,json=PAYLOAD,
                    headers={"Content-Type":"application/json;charset=UTF-8",
                             "User-Agent":"Mozilla/5.0 (ETF research, official catalog capture)"},
                    timeout=(15,90))
                resp.raise_for_status()
                raw=resp.content
                records=read_catalog(raw)
                break
            except Exception as e:
                last=e
                if i<2:time.sleep(2*(i+1))
        else:
            raise RuntimeError(f"Official CSI catalog download failed; no data promoted: {last}") from last
        observed=datetime.now(timezone.utc).isoformat()
    records=read_catalog(raw)
    result={"source_url":ENDPOINT,"observed_at":observed,
            "raw_sha256":hashlib.sha256(raw).hexdigest(),
            "raw_bytes":len(raw),
            "provider":"CSI",
            "index_count":len(records),
            "payload":{"indices":records}}
    args.raw.parent.mkdir(parents=True,exist_ok=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.raw.write_bytes(raw)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":"OK","index_count":len(records),"source":ENDPOINT,
                      "observed_at":observed,"sha256":result["raw_sha256"]},ensure_ascii=False))


if __name__=="__main__":
    main()
