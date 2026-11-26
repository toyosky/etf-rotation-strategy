"""Research-only missing premium backfill. No production code changes.
Run per symbol. Only inserts missing pairs, never changes existing observations.
Historical NAV publication times unknown: pit_safe=False, backfilled=True.
"""
import argparse, json
from pathlib import Path
from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.dialects.postgresql import insert
from automation import premium_history_sync as sync
from automation.premium_history_sync import db_url, load_universe, build_rows
import pandas as pd
import requests
import math
import time

def get_json(url, params, headers):
    last = None
    for i in range(3):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=(8,25))
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("invalid JSON object")
            return payload
        except (requests.RequestException, ValueError) as exc:
            last = type(exc).__name__
            if i < 2: time.sleep(2**i)
    raise RuntimeError("HTTP/JSON failure: " + str(last))

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"

def raw_price(symbol, instrument_type, start_date, end_date):
    lo, hi = [pd.to_datetime(x).date().isoformat() for x in (start_date,end_date)]
    code = sync.tencent_code(symbol)
    errors = []
    for host in ("web.ifzq.gtimg.cn", "web.ifzq.gtimg.com"):
        for param in (f"{code},day,{lo},{hi},640", f"{code},day,{lo},{hi},640,"):
            try:
                payload = get_json(f"https://{host}/appstock/app/fqkline/get",
                                   {"param":param},{"User-Agent":UA,"Referer":"https://gu.qq.com/"})
                if payload.get("code") not in (0,"0",None):
                    raise RuntimeError("Tencent error code")
                block = (payload.get("data") or {}).get(code) or {}
                raw = block.get("day")
                if not isinstance(raw,list):
                    raise RuntimeError("Tencent raw day missing; adjusted arrays rejected")
                rows = [{"nav_date":pd.to_datetime(x[0]).date(),"market_close":float(x[2])}
                        for x in raw if lo <= str(x[0]) <= hi]
                if not rows: raise RuntimeError("Tencent no raw bars in range")
                out = pd.DataFrame(rows)
                if not out.market_close.map(lambda x: math.isfinite(x) and x>0).all():
                    raise RuntimeError("Tencent invalid close")
                if out.nav_date.duplicated().any():
                    raise RuntimeError("Tencent duplicate dates")
                out.attrs["source_price"]="tencent_fqkline_raw_day"
                return out.sort_values("nav_date")
            except (RuntimeError,ValueError,TypeError,IndexError) as exc:
                errors.append(str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)
    raise RuntimeError("Tencent raw day: " + "; ".join(dict.fromkeys(errors)))

# Keep original Eastmoney DWJZ parser but disable alternate NAV source.
def fetch_dwjz(symbol, start_date, end_date):
    lo, hi = [pd.to_datetime(x).date().isoformat() for x in (start_date,end_date)]
    url = "https://api.fund.eastmoney.com/f10/lsjz"
    headers = {"User-Agent":UA,"Referer":f"https://fundf10.eastmoney.com/jjjz_{symbol}.html"}
    seen = set()
    rows = []
    # Endpoint can silently cap pageSize at 20; request exactly 20 and
    # advance until actual unique dates reach the reported TotalCount.
    for page in range(1,100):
        payload = get_json(url,{"fundCode":symbol,"pageIndex":page,"pageSize":20,
                               "startDate":lo,"endDate":hi,"_":int(time.time()*1000)},headers)
        if payload.get("ErrCode") not in (None,0,"0"):
            raise RuntimeError("Eastmoney NAV error code")
        block = payload.get("Data") or {}
        records = block.get("LSJZList") or []
        total = payload.get("TotalCount",block.get("TotalCount"))
        if not records:
            if total is not None and len(seen)<int(total):
                raise RuntimeError("NAV pagination ended before TotalCount")
            break
        new = 0
        for x in records:
            d = str(x.get("FSRQ",""))
            if not lo <= d <= hi: continue
            if d in seen: continue
            seen.add(d)
            new += 1
            nav = pd.to_numeric(x.get("DWJZ"),errors="coerce")
            if pd.isna(nav) or not math.isfinite(float(nav)) or nav<=0: continue
            rows.append({"nav_date":pd.to_datetime(d).date(),"unit_nav":float(nav),
                         "cumulative_nav":pd.to_numeric(x.get("LJJZ"),errors="coerce"),
                         "nav_daily_growth_pct":pd.to_numeric(x.get("JZZZL"),errors="coerce"),
                         "subscription_status":x.get("SGZT"),"redemption_status":x.get("SHZT")})
        if total is not None and len(seen)>=int(total): break
        if not new: raise RuntimeError("NAV pagination repeated a page")
        time.sleep(.15)
    else:
        raise RuntimeError("NAV pagination limit")
    return pd.DataFrame(rows).sort_values("nav_date") if rows else pd.DataFrame()

sync.fetch_nav = fetch_dwjz
sync.tencent_nav_fallback = lambda *args: pd.DataFrame()
sync.fetch_unadjusted_price = raw_price


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--symbol",required=True)
    p.add_argument("--start",default="20140101")
    p.add_argument("--end",default="20261125")
    p.add_argument("--output",required=True)
    args=p.parse_args()
    eng=create_engine(db_url(),pool_pre_ping=True)
    meta=load_universe(eng,{args.symbol},True)[0]
    tab=Table("fund_premium_history",MetaData(),schema="public",autoload_with=eng)
    report={"symbol":args.symbol,"range":[args.start,args.end],"segments":[]}
    # Year segments avoid single request limits and oversized inserts.
    for yr in range(int(args.start[:4]),int(args.end[:4])+1):
        lo=max(args.start,f"{yr}0101"); hi=min(args.end,f"{yr}1231")
        with eng.connect() as conn:
            missing=conn.execute(text("""
              SELECT count(*) FROM public.daily_bars d
              LEFT JOIN public.fund_premium_history p ON p.symbol=d.symbol AND p.nav_date=d.date
              WHERE d.symbol=:s AND d.date BETWEEN to_date(:lo,'YYYYMMDD') AND to_date(:hi,'YYYYMMDD') AND p.nav_date IS NULL
            """),{"s":args.symbol,"lo":lo,"hi":hi}).scalar_one()
        seg={"year":yr,"expected_missing":missing}
        try:
            if missing:
                rows=build_rows(meta,lo,hi,"backfill")
                for r in rows: r["source_nav"]="eastmoney_f10_lsjz_dwjz"
                assert all(r["symbol"]==args.symbol and r["market_close"]>0 and r["unit_nav"]>0 and not r["pit_safe"] and r["backfilled"] and r["first_seen_at"] is None for r in rows)
                inserted=0
                with eng.begin() as conn:
                    for i in range(0,len(rows),200):
                        stmt=insert(tab).values(rows[i:i+200]).on_conflict_do_nothing(index_elements=[tab.c.symbol,tab.c.nav_date])
                        inserted+=conn.execute(stmt).rowcount
                seg.update(fetched=len(rows),inserted=inserted)
            else: seg.update(fetched=0,inserted=0)
        except Exception as exc:
            # Do not echo exception URLs or database secrets.
            seg["error_type"]=type(exc).__name__
            if isinstance(exc,RuntimeError):
                seg["error_detail"]=str(exc)[:300] if "://" not in str(exc) else "runtime error (URL suppressed)"
        report["segments"].append(seg)
        Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(seg,ensure_ascii=False),flush=True)
    with eng.connect() as conn:
        report["coverage"]=dict(conn.execute(text("""
          SELECT count(*) bars,count(p.nav_date) matched,
          count(*) FILTER (WHERE p.pit_safe) pit_safe
          FROM public.daily_bars d LEFT JOIN public.fund_premium_history p
          ON d.symbol=p.symbol AND d.date=p.nav_date
          WHERE d.symbol=:s AND d.date BETWEEN to_date(:lo,'YYYYMMDD') AND to_date(:hi,'YYYYMMDD')
        """),{"s":args.symbol,"lo":args.start,"hi":args.end}).mappings().one())
    Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return 1 if any("error_type" in x for x in report["segments"]) or report["coverage"]["matched"]<report["coverage"]["bars"]*.95 else 0
if __name__=="__main__":
    raise SystemExit(main())
