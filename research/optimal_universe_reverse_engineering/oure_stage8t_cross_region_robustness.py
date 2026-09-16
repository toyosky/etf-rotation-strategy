#!/usr/bin/env python3
from __future__ import annotations
import os,sys
from pathlib import Path
import numpy as np,pandas as pd
from sqlalchemy import create_engine
RESEARCH=Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path: sys.path.insert(0,str(RESEARCH))
from full_market_ols_storage import _db_url,build_features,load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
import optimal_universe_reverse_engineering.oure_stage8m_fixv2_v1_long_horizon as s8m
import optimal_universe_reverse_engineering.oure_stage8q_map_comparator_robustness as s8q
CASH='511220'; H=(5,10,20,40)
REGIONS={'US_SP500':'513500','JAPAN_NIKKEI':'513520','GERMANY_DAX':'513030','FRANCE_CAC40':'513080','INDIA':'164824','BRAZIL':'520870'}
COSTS=(0.0006,0.0012,0.0020,0.0030)
def main():
 db=os.getenv('ETF_DAILY_BARS_DATABASE_URL'); out=Path(os.getenv('OUTPUT_DIR','stage8t-output')); out.mkdir(parents=True,exist_ok=True)
 eng=create_engine(_db_url(db),pool_pre_ping=True); bars=load_daily_bars(eng); bars.symbol=bars.symbol.astype(str).str.zfill(6); bars.date=pd.to_datetime(bars.date)
 feat=build_features(bars); feat.symbol=feat.symbol.astype(str).str.zfill(6); feat.date=pd.to_datetime(feat.date)
 cal,score,r2,slope,close,op,gross,ret=build_wides(bars,feat); cal=pd.DatetimeIndex(cal); raw=s8m.raw_score_wide(feat,cal,list(score.columns.astype(str)))
 panel=s8q.build_map_panel(cal,score,feat,pd.DataFrame({'signal_date':cal})); q=panel.quadrant_511220.astype(object); ev=panel[(q=='DEFENSIVE_VOID')&(q.shift(1)!='DEFENSIVE_VOID')]
 elig=feat.pivot(index='date',columns='symbol',values='universe_eligible').reindex(cal).fillna(False)
 variants={'ALL':set(REGIONS)}
 for r in REGIONS: variants['DROP_'+r]=set(REGIONS)-{r}
 variants['CORE4']={'US_SP500','JAPAN_NIKKEI','GERMANY_DAX','INDIA'}
 rows=[]
 for name,allowed in variants.items():
  for e in ev.itertuples(index=False):
   d=pd.Timestamp(e.signal_date); i=cal.get_loc(d)
   if not isinstance(i,(int,np.integer)) or i+41>=len(cal): continue
   cs=raw.at[d,CASH] if CASH in raw.columns else np.nan; cand=[]
   for r in allowed:
    s=REGIONS[r]
    if s in raw.columns and s in elig.columns:
     v=raw.at[d,s]
     if bool(elig.at[d,s]) and pd.notna(v) and np.isfinite(v) and v>0:cand.append((float(v),r,s))
   cand.sort(reverse=True); route='CASH'; sym=CASH; rs=float(cs) if pd.notna(cs) else np.nan
   if cand and (not np.isfinite(rs) or cand[0][0]>rs):rs,route,sym=cand[0]
   ex=cal[i+1]
   for cost in COSTS:
    rec={'variant':name,'date':d,'year':d.year,'cost':cost,'route':route}
    for h in H:
     end=cal[i+h]
     def rr(s):
      a=op.at[ex,s] if s in op.columns else np.nan; b=close.at[end,s] if s in close.columns else np.nan
      return float(b/a-1-cost) if pd.notna(a) and pd.notna(b) and a>0 else np.nan
     sr,cr=rr(sym),rr(CASH); rec[f'ex{h}']=sr-cr if np.isfinite(sr) and np.isfinite(cr) else np.nan
    rows.append(rec)
 z=pd.DataFrame(rows); z.to_csv(out/'stage8t_events.csv',index=False)
 sm=[]
 for (v,c),x in z.groupby(['variant','cost']):
  for seg,m in [('2019_2022',(x.year>=2019)&(x.year<=2022)),('2023_2026',x.year>=2023)]:
   y=x[m]
   for h in H:
    a=y[f'ex{h}'].dropna(); sm.append({'variant':v,'cost':c,'segment':seg,'h':h,'n':len(a),'mean':a.mean(),'median':a.median(),'win':(a>0).mean(),'p10':a.quantile(.1) if len(a) else np.nan})
 sm=pd.DataFrame(sm); sm.to_csv(out/'stage8t_summary.csv',index=False)
 focus=sm[(sm.cost==0.0006)&(sm.h.isin([20,40]))]
 md=['# Stage8T — Cross-region robustness audit','','Leave-one-region-out + CORE4 + transaction-cost stress. Same frozen Stage8Q state and weighted 26d OLS router as Stage8S.','','## Base-cost 20/40d robustness','',focus.to_markdown(index=False),'','Interpretation: a robust router should survive region deletion, recent-era split, and higher costs; zero-excess cash routes are retained in medians/win rates.']
 (out/'stage8t_summary.md').write_text('\n'.join(md),encoding='utf-8'); print('\n'.join(md))
if __name__=='__main__':main()
