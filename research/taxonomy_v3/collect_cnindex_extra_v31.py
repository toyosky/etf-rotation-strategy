#!/usr/bin/env python3
"""Evidence-only optional CNIndex (Guozheng/Shenzhen) registry enrichment.

Reads unresolved *official fitted* codes from a frozen V3.1 snapshot. Queries
only the publisher's code endpoint, and persists valid code-full-name objects
in the same schema used by research/taxonomy_v3/build.py's registry_inputs.
No fund name guessing and no historical retroactive 'known' labels.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

import requests

URL="https://www.cnindex.com.cn/index/selectIndexByCode"

def parse_fitted(record:dict)->str:
    fitted=str(record.get("official_fitted_index_code") or "").strip()
    if not fitted:return ""
    return fitted.split()[0]

def candidate_code(code:str)->bool:
    # CNI index families; exclude CNI-like numeric codes from other providers
    # and avoid presenting guessed index vendor identity as confirmed.
    return bool(re.fullmatch(r"(?:39\d{4}|97\d{4}|98\d{4}|CN\d{4})",code))

def extract(response:requests.Response,code:str):
    response.raise_for_status()
    body=response.json()
    data=body.get("data",{}) if isinstance(body,dict) else {}
    if not isinstance(data,dict):return None
    returned=str(data.get("indexcode") or "").strip()
    fullname=str(data.get("indexfullcname") or "").strip()
    if returned!=code or not fullname or fullname in ("-", "--"):
        return None
    return {"source_url":response.url,
            "observed_at":datetime.now(timezone.utc).isoformat(),
            "sha256":hashlib.sha256(response.content).hexdigest(),
            "payload":body}

def fetch(code:str,timeout:float):
    s=requests.Session()
    try:
        for i in range(2):
            try:
                r=s.get(URL,params={"codeValue":code},
                        headers={"Referer":"https://www.cnindex.com.cn/","User-Agent":"Mozilla/5.0"},
                        timeout=(8,timeout))
                return extract(r,code),None
            except Exception as e:
                error=str(e)
                if i<1:time.sleep(1.5)
        return None,error
    finally:s.close()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--classifications",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True,
                    help="same official directory that registry_inputs reads")
    ap.add_argument("--max-workers",type=int,default=5)
    ap.add_argument("--timeout",type=float,default=18)
    args=ap.parse_args()
    rows=json.loads(args.classifications.read_text())
    codes=sorted(set(parse_fitted(x) for x in rows
        if "OFFICIAL_CODE_NAME_LINK_NOT_VERIFIED" in (x.get("classification_reason") or [])
        and candidate_code(parse_fitted(x))))
    args.output.mkdir(parents=True,exist_ok=True)
    done=[];missing=[];failed=[]
    with ThreadPoolExecutor(max_workers=max(1,min(args.max_workers,8))) as pool:
        futs={pool.submit(fetch,code,args.timeout):code for code in codes}
        for fut in as_completed(futs):
            code=futs[fut]
            try:record,error=fut.result()
            except Exception as e:record,error=None,str(e)
            if record:
                p=args.output/f"cnindex-{code}.json"
                p.write_text(json.dumps(record,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8")
                done.append(code)
            elif error:failed.append({"code":code,"error":error[:200]})
            else:missing.append(code)
    outcome={"capture_as_of":datetime.now(timezone.utc).date().isoformat(),
        "official_endpoint":URL,"requested":len(codes),
        "verified_matches":sorted(done),"unresolved_official_response":sorted(missing),
        "request_errors":sorted(failed,key=lambda x:x["code"]),
        "not_requested":"Non-CNI/unknown provider codes never guessed; current-only snapshots"}
    (args.output.parent/"capture-cnindex-extra-status.json").write_text(
        json.dumps(outcome,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"requested":len(codes),"verified":len(done),
        "not_found":len(missing),"errors":len(failed)},ensure_ascii=False))
if __name__=="__main__":
    main()
