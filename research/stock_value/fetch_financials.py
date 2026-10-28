#!/usr/bin/env python3
"""Capture Tencent financial statements as *unverified* source snapshots.

This stage deliberately does not infer earnings from unknown vendor field names.
The resulting snapshots are not point-in-time safe until publication dates are checked.
"""
import gzip
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STOCKS=("002353","688059","300308","300502","300394","603986","001309")
PACKAGE="westock-data-skillhub@1.0.5"
OUT=Path("research/stock_value/data/finance")
REPORT=Path("research/stock_value/results/financial-source-status.json")

def run(code):
    market="sh" if code.startswith(("6","9")) else "sz"
    p=subprocess.run(["npx","-y",PACKAGE,"finance",market+code,"--num","8","--raw"],
                     capture_output=True,text=True,timeout=180)
    if p.returncode: raise RuntimeError((p.stderr or p.stdout)[-500:])
    data=json.loads(p.stdout)
    if isinstance(data,dict) and data.get("success") is False:
        raise RuntimeError(str(data.get("error")))
    if not isinstance(data,(list,dict)) or not data:
        raise ValueError("Empty or unexpected financial payload")
    OUT.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(data,ensure_ascii=False,separators=(",",":")).encode()
    path=OUT/(code+".json.gz")
    with path.open("wb") as f:
        with gzip.GzipFile(fileobj=f,mode="wb",filename="",mtime=0,compresslevel=9) as g:g.write(raw)
    if path.stat().st_size>2_000_000:
        path.unlink()
        raise ValueError("Financial snapshot exceeds 2MB cap")
    return {"symbol":code,"status":"RAW_CAPTURED_UNVERIFIED","compressed_bytes":path.stat().st_size}

def main():
    statuses=[]
    for code in STOCKS:
        try: statuses.append(run(code))
        except Exception as ex: statuses.append({"symbol":code,"status":"FAILED","error":str(ex)[:300]})
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps({"retrieved_at_utc":datetime.now(timezone.utc).isoformat(),
        "source":"Tencent Westock finance --num 8 --raw",
        "warning":"Raw vendor data only. Period, publication date, financial field mapping and as-of availability NOT VERIFIED.",
        "items":statuses},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"captured":sum(x["status"]=="RAW_CAPTURED_UNVERIFIED" for x in statuses),"total":len(statuses)}))
    return 0 if all(x["status"]=="RAW_CAPTURED_UNVERIFIED" for x in statuses) else 1
if __name__=="__main__":sys.exit(main())
