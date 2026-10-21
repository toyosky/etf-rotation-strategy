#!/usr/bin/env python3
"""Build an explicitly dated Premium10 notification snapshot from synchronized NAV/BFQ rows.
No quote, missing NAV, or stale NAV is ever converted into a zero premium.
"""
import argparse
import json
import os
from pathlib import Path
from sqlalchemy import create_engine, text

LIMIT = 0.10

def build(database_url, day, symbol):
    result = {"symbol":symbol,"signal_date":day,"threshold_pct":10.0,
              "status":"UNVERIFIED","reason":"NO_MATCHED_NAV_AND_BFQ",
              "premium_pct":None,"nav_date":None,"price_date":None}
    if not symbol:
        result["reason"]="NO_MODEL_CANDIDATE"
        return result
    if not database_url:
        result["reason"]="DATABASE_URL_MISSING"
        return result
    from sqlalchemy.engine import make_url
    url=database_url
    if url.startswith("postgres://"):
        url="postgresql://"+url[len("postgres://"):]
    engine=create_engine(url,pool_pre_ping=True,connect_args={"connect_timeout":10})
    with engine.connect() as connection:
        rows=connection.execute(text("""
          SELECT nav_date,unit_nav,market_close,source_nav,source_price,
                 first_seen_at,pit_safe,backfilled
          FROM public.fund_premium_history
          WHERE symbol=:symbol AND nav_date<=CAST(:day AS DATE)
          ORDER BY nav_date DESC LIMIT 1
        """),{"symbol":symbol,"day":day}).mappings().all()
    if not rows:
        return result
    r=rows[0]
    result.update({"nav_date":str(r["nav_date"]),"price_date":str(r["nav_date"]),
                   "source_nav":r["source_nav"],"source_price":r["source_price"],
                   "observed_at":str(r["first_seen_at"]) if r["first_seen_at"] else None,
                   "pit_safe":bool(r["pit_safe"]),"backfilled":bool(r["backfilled"])})
    close,nav=r["market_close"],r["unit_nav"]
    if not close or not nav or close<=0 or nav<=0:
        result["reason"]="INVALID_BFQ_OR_NAV"
        return result
    premium=(float(close)/float(nav)-1)*100
    result["premium_pct"]=round(premium,4)
    if str(r["nav_date"]) != day:
        result.update(status="STALE_OBSERVATION",reason="LATEST_MATCHED_PRICE_AND_NAV_NOT_SIGNAL_DATE")
    else:
        result.update(status="MATCHED_HISTORY",reason="MATCHED_DATE_BUT_NOT_LIVE_EXECUTION_CLEARANCE")
    result["threshold_comparison"]="OVER_10" if premium>10 else "BELOW_OR_EQUAL_10"
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--current",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    current=json.loads(Path(args.current).read_text(encoding="utf-8"))
    day=current["market_data_date"]
    symbol=str((current.get("next_strategy_target") or {}).get("model_target") or "")
    try:
        result=build(os.getenv("ETF_DAILY_BARS_DATABASE_URL",""),day,symbol)
    except Exception as exc:
        result={"symbol":symbol,"signal_date":day,"threshold_pct":10.0,
                "status":"UNVERIFIED","reason":"DATABASE_QUERY_FAILED:"+type(exc).__name__,
                "premium_pct":None}
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":
    main()
