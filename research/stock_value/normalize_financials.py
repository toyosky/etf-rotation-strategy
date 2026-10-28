#!/usr/bin/env python3
"""Normalize as-of Tencent financial snapshots; do not infer unreleased Q3 reports."""
import argparse,gzip,json,sys
from datetime import date
from pathlib import Path

CODES=("002353","688059","300308","300502","300394","603986","001309")
ROOT=Path("research/stock_value")
FIN=ROOT/"data"/"finance"
OUT=ROOT/"results"/"financial-summary.json"

def number(obj,key):
    v=obj.get(key)
    return float(v) if v not in (None,"","--") else None

def hundred_million(v):
    return round(v/1e8,3) if v is not None else None

def parse(code,asof):
    with gzip.open(FIN/(code+".json.gz"),"rt",encoding="utf-8") as f:raw=json.load(f)
    groups=raw.get("sections")
    if not isinstance(groups,list) or len(groups)<3:raise ValueError("Missing 3 Tencent financial sections")
    indexes=[{str(row.get("EndDate",row.get("date"))):row for row in group} for group in groups]
    valid=[]
    for period in indexes[0]:
        if period not in indexes[1] or period not in indexes[2]:continue
        pubs=[str(indexes[i][period].get("InfoPublDate",""))[:10] for i in range(3)]
        if not all(p and p<="9999-12-31" for p in pubs):continue
        if period<=asof and max(pubs)<=asof:valid.append(period)
    if not valid:raise ValueError("No jointly available published financial period")
    latest=max(valid)
    def metrics(period):
        a,b,c=(idx[period] for idx in indexes)
        return {"period_end":period,"publication_date":max(str(x.get("InfoPublDate",""))[:10] for x in (a,b,c)),
                "revenue":number(a,"OperatingRevenue"),
                "net_profit_parent":number(a,"NPParentCompanyOwners"),
                "net_profit_ex_nonrecurring":number(b,"NPDeductNonRecurringPL"),
                "operating_cash_flow":number(c,"NetOperateCashFlow")}
    cur=metrics(latest)
    prior=str(int(latest[:4])-1)+latest[4:]
    previous=metrics(prior) if prior in valid else None
    def yoy(key):
        if not previous or previous[key] in (None,0) or cur[key] is None:return None
        return round((cur[key]/abs(previous[key])-1)*100,2) if previous[key]>0 else None
    np=cur["net_profit_parent"];cfo=cur["operating_cash_flow"]
    ratio=round(cfo/np,3) if np and cfo is not None and np>0 else None
    flags=[]
    if cfo is not None and cfo<0:flags.append("NEGATIVE_OPERATING_CASH_FLOW")
    if ratio is not None and ratio<0.5:flags.append("LOW_CASH_CONVERSION")
    if cur["net_profit_ex_nonrecurring"] is None:flags.append("MISSING_DEDUCTED_PROFIT")
    if latest[:4]=="2026" and latest[5:]!="09-30":flags.append("2026_Q3_NOT_YET_PUBLISHED_AS_OF_DATE")
    return {"symbol":code,"latest_report":latest,"publication_date":cur["publication_date"],
            "revenue_100m_cny":hundred_million(cur["revenue"]),
            "net_profit_parent_100m_cny":hundred_million(np),
            "deducted_net_profit_100m_cny":hundred_million(cur["net_profit_ex_nonrecurring"]),
            "operating_cash_flow_100m_cny":hundred_million(cfo),
            "operating_cash_flow_to_net_profit":ratio,
            "same_period_last_year":prior if previous else None,
            "net_profit_yoy_pct":yoy("net_profit_parent"),
            "deducted_profit_yoy_pct":yoy("net_profit_ex_nonrecurring"),
            "operating_cash_flow_yoy_pct":yoy("operating_cash_flow"),
            "flags":flags,"source":"Tencent Westock finance sections[0,1,2]",
            "verification":"TENCENT_FIELD_MAPPED_NOT_INDEPENDENTLY_CROSSCHECKED"}

def main():
    p=argparse.ArgumentParser();p.add_argument("--as-of",default="2026-10-28")
    args=p.parse_args();date.fromisoformat(args.as_of)
    rows=[];failures=[]
    for code in CODES:
        try:rows.append(parse(code,args.as_of))
        except Exception as exc:failures.append({"symbol":code,"error":str(exc)[:250]})
    OUT.parent.mkdir(parents=True,exist_ok=True)
    data={"as_of":args.as_of,"data_status":"TENCENT_FIELD_MAPPED_NOT_OFFICIAL_REPORT_VERIFIED",
          "unit":"100 million CNY for monetary values",
          "method":"latest report with InfoPublDate <= as_of, compare same report period last year; YTD data not quarterly",
          "items":rows,"failures":failures}
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"financials_mapped":len(rows),"failed":len(failures)},ensure_ascii=False))
    return 0 if len(rows)==len(CODES) and not failures else 1
if __name__=="__main__":sys.exit(main())
