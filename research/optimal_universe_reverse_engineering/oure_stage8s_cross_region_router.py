#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

RESEARCH=Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path: sys.path.insert(0,str(RESEARCH))
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
import optimal_universe_reverse_engineering.oure_stage8m_fixv2_v1_long_horizon as s8m
import optimal_universe_reverse_engineering.oure_stage8q_map_comparator_robustness as s8q

CASH='511220'; COST=0.0006; H=(5,10,20,40)
# One broad, economically distinct carrier per region. Historical availability is enforced daily.
REGIONS={
 'US_SP500':'513500',
 'JAPAN_NIKKEI':'513520',
 'GERMANY_DAX':'513030',
 'FRANCE_CAC40':'513080',
 'INDIA':'164824',
 'BRAZIL':'520870',
}

def event_rows(panel):
    q=panel['quadrant_511220'].astype(object)
    return panel[(q=='DEFENSIVE_VOID') & (q.shift(1)!='DEFENSIVE_VOID')].copy()

def maxdd(vals):
    a=np.asarray(vals,float); a=a[np.isfinite(a)]
    if len(a)<2:return np.nan
    p=np.maximum.accumulate(a); return float(np.min(a/p-1))

def main():
    db=os.getenv('ETF_DAILY_BARS_DATABASE_URL')
    if not db: raise SystemExit('Missing ETF_DAILY_BARS_DATABASE_URL')
    out=Path(os.getenv('OUTPUT_DIR','stage8s-cross-region-output')); out.mkdir(parents=True,exist_ok=True)
    eng=create_engine(_db_url(db),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars['symbol']=bars.symbol.astype(str).str.zfill(6); bars['date']=pd.to_datetime(bars.date)
    feat=build_features(bars); feat['symbol']=feat.symbol.astype(str).str.zfill(6); feat['date']=pd.to_datetime(feat.date)
    cal,score,r2,slope,close,op,gross,ret=build_wides(bars,feat); cal=pd.DatetimeIndex(cal)
    raw=s8m.raw_score_wide(feat,cal,list(score.columns.astype(str)))
    # Rebuild the frozen website state map exactly: raw weighted 26d OLS, 511220 breadth hurdle, 252d gap percentile.
    labels=pd.DataFrame({'signal_date':cal})
    panel=s8q.build_map_panel(cal,score,feat,labels)
    ev=event_rows(panel)
    elig=feat.pivot(index='date',columns='symbol',values='universe_eligible').reindex(cal).fillna(False)
    rows=[]
    for e in ev.itertuples(index=False):
        d=pd.Timestamp(e.signal_date)
        if d not in cal: continue
        i=cal.get_loc(d)
        if not isinstance(i,(int,np.integer)) or i+41>=len(cal): continue
        cashscore=raw.at[d,CASH] if CASH in raw.columns else np.nan
        cand=[]
        for region,s in REGIONS.items():
            if s not in raw.columns or s not in elig.columns: continue
            v=raw.at[d,s]
            if bool(elig.at[d,s]) and pd.notna(v) and np.isfinite(v) and v>0:
                cand.append((float(v),region,s))
        cand.sort(reverse=True)
        route='CASH'; sym=CASH; route_score=float(cashscore) if pd.notna(cashscore) else np.nan
        if cand and (not np.isfinite(route_score) or cand[0][0]>route_score):
            route_score,route,sym=cand[0]
        ex=cal[i+1]
        rec={'signal_date':d,'execution_date':ex,'route':route,'symbol':sym,'route_score':route_score,'cash_score':cashscore,'available_regions':len(cand)}
        for h in H:
            end=cal[i+h]
            def rr(s):
                if s not in op.columns or s not in close.columns:return np.nan
                a=op.at[ex,s]; b=close.at[end,s]
                if pd.isna(a) or pd.isna(b) or a<=0:return np.nan
                return float(b/a-1-COST)
            sr=rr(sym); cr=rr(CASH)
            rec[f'ret{h}']=sr; rec[f'cash{h}']=cr; rec[f'excess{h}']=sr-cr if np.isfinite(sr) and np.isfinite(cr) else np.nan
            path=close.loc[ex:end,sym] if sym in close.columns else pd.Series(dtype=float)
            rec[f'mdd{h}']=maxdd(path.values)
        rows.append(rec)
    z=pd.DataFrame(rows); z.to_csv(out/'stage8s_events.csv',index=False)
    summary=[]
    for seg,mask in [('FULL',pd.Series(True,index=z.index)),('2015_2022',z.signal_date.dt.year<=2022),('2023_2026',z.signal_date.dt.year>=2023)]:
        x=z.loc[mask]
        for h in H:
            y=x[f'excess{h}'].dropna()
            summary.append({'segment':seg,'horizon':h,'n':len(y),'mean_excess':y.mean(),'median_excess':y.median(),'win_rate':(y>0).mean(),'p10':y.quantile(.1) if len(y) else np.nan,'mean_mdd':x[f'mdd{h}'].mean()})
    sm=pd.DataFrame(summary); sm.to_csv(out/'stage8s_summary.csv',index=False)
    yearly=[]
    for yr,x in z.groupby(z.signal_date.dt.year):
        r={'year':int(yr),'n':len(x),'cash_routes':int((x.route=='CASH').sum())}
        for h in H:r[f'excess{h}']=x[f'excess{h}'].mean()
        yearly.append(r)
    yd=pd.DataFrame(yearly); yd.to_csv(out/'stage8s_yearly.csv',index=False)
    routes=z.route.value_counts().rename_axis('route').reset_index(name='n'); routes.to_csv(out/'stage8s_routes.csv',index=False)
    md=['# Stage8S — Defensive/Void Cross-Region Router','', 'Frozen state definition: Stage8Q website raw weighted-OLS map. Router uses the same weighted 26-day OLS score; only historically eligible regional carriers may compete; 511220 is the hurdle.','', '## Segment results','',sm.to_markdown(index=False),'','## Yearly','',yd.to_markdown(index=False),'','## Route counts','',routes.to_markdown(index=False),'', 'Diagnostic stage only. Brazil is admitted only after its own 365-day/200-bar eligibility gate, preventing retrospective use before listing.']
    (out/'stage8s_summary.md').write_text('\n'.join(md),encoding='utf-8')
    (out/'stage8s_summary.json').write_text(json.dumps({'regions':REGIONS,'events':len(z)},ensure_ascii=False,indent=2),encoding='utf-8')
    print('\n'.join(md))
if __name__=='__main__':main()
