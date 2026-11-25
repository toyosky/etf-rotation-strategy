"""Research-only missing premium backfill. No production code changes.
Run per symbol. Only inserts missing pairs, never changes existing observations.
Historical NAV publication times unknown: pit_safe=False, backfilled=True.
"""
import argparse, json
from pathlib import Path
from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.dialects.postgresql import insert
from automation.premium_history_sync import db_url, load_universe, build_rows

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--symbol",required=True)
    p.add_argument("--start",default="20201201")
    p.add_argument("--end",default="20261120")
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
