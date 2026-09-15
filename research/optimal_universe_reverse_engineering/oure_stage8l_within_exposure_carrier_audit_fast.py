#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import optimal_universe_reverse_engineering.oure_stage8l_within_exposure_carrier_audit as core


def fast_run_path(name: str, members: tuple[str,...], cal: pd.DatetimeIndex, score: pd.DataFrame, gross: pd.DataFrame,
                  start_signal: pd.Timestamp, last_signal_pos: int) -> pd.DataFrame:
    start_pos=max(0,int(cal.searchsorted(pd.Timestamp(start_signal),side="left")))
    dates=pd.DatetimeIndex(cal[start_pos:last_signal_pos+1])
    n=len(dates)
    if n==0:
        return pd.DataFrame(columns=["variant","signal_date","execution_date","return_end_date","target","sides","gross","net"])
    risk=[s for s in members if s!=core.CASH and s in score.columns]
    targets=np.empty(n,dtype=object); targets[:]=None
    gr=np.zeros(n,dtype=float)
    if risk:
        ss=score.reindex(index=dates,columns=risk).to_numpy(dtype=float)
        ff=np.where(np.isfinite(ss),ss,-np.inf)
        idx=np.argmax(ff,axis=1)
        rv=ff[np.arange(n),idx]
        cash=score.reindex(index=dates,columns=[core.CASH]).iloc[:,0].to_numpy(dtype=float)
        cash=np.where(np.isfinite(cash),cash,-np.inf)
        active=np.isfinite(rv) & (rv>cash)
        syms=np.asarray(risk,dtype=object)
        targets[active]=syms[idx[active]]
        gm=gross.reindex(index=dates,columns=risk).to_numpy(dtype=float)
        chosen=gm[np.arange(n),idx]
        chosen=np.where(np.isfinite(chosen),chosen,0.0)
        gr[active]=chosen[active]
    sides=np.zeros(n,dtype=np.int16)
    prev=None
    for i,t in enumerate(targets):
        if t==prev:
            s=0
        elif t is None or prev is None:
            s=1
        else:
            s=2
        sides[i]=s; prev=t
    net=(1.0+gr)*(1.0-core.COST*sides)-1.0
    pos=np.arange(start_pos,last_signal_pos+1)
    return pd.DataFrame({
        "variant":name,
        "signal_date":dates,
        "execution_date":pd.DatetimeIndex(cal[pos+1]),
        "return_end_date":pd.DatetimeIndex(cal[pos+2]),
        "target":targets,
        "sides":sides,
        "gross":gr,
        "net":net,
    })


core.run_path=fast_run_path

if __name__=="__main__":
    core.main()
