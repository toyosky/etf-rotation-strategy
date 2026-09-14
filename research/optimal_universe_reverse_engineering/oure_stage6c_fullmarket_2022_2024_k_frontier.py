#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
from walk_forward_candidate_pool import SIDE_COST

CASH = "511220"
START = pd.Timestamp("2022-01-01")
END = pd.Timestamp("2024-12-31")
MAX_K = 60
GREEDY_SEEDS = 12
SWAP_SHORTLIST = 120
REFINE_ROUNDS = 3
ANCHORS = (5, 10, 15, 20, 25, 30, 40, 50, 60)
STOCH_STARTS = 5
STOCH_STEPS = 4000
RANDOM_N = 100
SEED = 20260914
TOL = 1e-12


def keyify(xs) -> tuple[str, ...]:
    return tuple(sorted(set(str(x) for x in xs if str(x) != CASH)))


class Eval:
    def __init__(self, score: pd.DataFrame, gross: pd.DataFrame, dates: pd.DatetimeIndex, candidates: list[str]):
        self.dates = pd.DatetimeIndex(dates)
        self.cands = list(candidates)
        self.idx = {s:i for i,s in enumerate(self.cands)}
        self.cash = score.loc[self.dates, CASH].to_numpy(float)
        self.score = score.loc[self.dates, self.cands].to_numpy(float)
        self.gross = gross.loc[self.dates, self.cands].to_numpy(float)
        self.gross = np.where(np.isfinite(self.gross), self.gross, 0.0)
        self.cache: dict[tuple[str,...], dict] = {}
        self.state_cache: dict[tuple[str,...], tuple[np.ndarray,np.ndarray]] = {}

    def target_state(self, members) -> tuple[np.ndarray, np.ndarray]:
        k = keyify(members)
        if k in self.state_cache:
            return self.state_cache[k]
        t = len(self.dates)
        if not k:
            best = np.where(np.isfinite(self.cash), self.cash, -np.inf).astype(float)
            target = np.full(t, -1, dtype=np.int32)
            self.state_cache[k] = (best, target)
            return best, target
        ids = [self.idx[s] for s in k]
        sm = self.score[:, ids]
        safe = np.where(np.isfinite(sm), sm, -np.inf)
        loc = np.argmax(safe, axis=1)
        best_risk = safe[np.arange(t), loc]
        cashv = np.where(np.isfinite(self.cash), self.cash, -np.inf)
        active = np.isfinite(best_risk) & (best_risk > cashv)
        target = np.full(t, -1, dtype=np.int32)
        arrids = np.asarray(ids, dtype=np.int32)
        target[active] = arrids[loc[active]]
        best = np.where(active, best_risk, cashv)
        self.state_cache[k] = (best, target)
        return best, target

    def log_from_target(self, target: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
        t = len(target); rows = np.arange(t)
        active = target >= 0
        g = np.zeros(t, dtype=float)
        if active.any(): g[active] = self.gross[rows[active], target[active]]
        sides = np.zeros(t, dtype=np.int8)
        if t:
            if target[0] >= 0: sides[0] = 1
            if t > 1:
                changed = target[1:] != target[:-1]
                one_cash = (target[1:] < 0) | (target[:-1] < 0)
                sides[1:] = np.where(changed, np.where(one_cash, 1, 2), 0)
        net = (1.0 + g) * (1.0 - SIDE_COST * sides) - 1.0
        lg = np.log1p(net)
        return float(lg.sum()), lg, sides

    def quick_add_log(self, members, y: str) -> float:
        k = keyify(members)
        best, target = self.target_state(k)
        j = self.idx[y]
        v = self.score[:, j]
        choose = np.isfinite(v) & (v > best)
        nt = target.copy(); nt[choose] = j
        return self.log_from_target(nt)[0]

    def evaluate(self, members) -> dict:
        k = keyify(members)
        if k in self.cache: return self.cache[k]
        if len(k) > MAX_K: raise ValueError("K > MAX_K")
        _, target = self.target_state(k)
        logg, lg, sides = self.log_from_target(target)
        eq = np.exp(np.cumsum(lg)) if len(lg) else np.array([1.0])
        dd = eq / np.maximum.accumulate(eq) - 1.0
        lens=[]; cur=-2; n=0
        for z in target:
            z=int(z)
            if z < 0:
                if cur >= 0: lens.append(n)
                cur=-2; n=0
            elif z == cur: n += 1
            else:
                if cur >= 0: lens.append(n)
                cur=z; n=1
        if cur >= 0: lens.append(n)
        rec={
            "members": k, "k_noncash": len(k), "log_growth": logg,
            "total_return": float(np.exp(logg)-1),
            "max_drawdown": float(dd.min()) if len(dd) else 0.0,
            "switch_events": int(np.count_nonzero(sides)),
            "turnover_sides": int(sides.sum()),
            "invested_ratio": float(np.mean(target>=0)) if len(target) else 0.0,
            "mean_top1_tenure": float(np.mean(lens)) if lens else np.nan,
            "median_top1_tenure": float(np.median(lens)) if lens else np.nan,
            "short_run_le2_share": float(np.mean(np.asarray(lens)<=2)) if lens else np.nan,
        }
        self.cache[k]=rec
        return rec

    def diagnostics(self, members) -> dict:
        k=keyify(members); rec=dict(self.evaluate(k)); ids=[self.idx[s] for s in k]
        sm=self.score[:,ids] if ids else np.empty((len(self.dates),0))
        elig=np.isfinite(sm); counts=elig.sum(axis=1) if len(ids) else np.zeros(len(self.dates),int)
        covered=counts>0
        rec["coverage_share"]=float(covered.mean()) if len(counts) else np.nan
        rec["mean_eligible_count"]=float(counts.mean()) if len(counts) else np.nan
        rec["mean_competitors_when_covered"]=float(counts[covered].mean()) if covered.any() else np.nan
        rec["coverage_efficiency"]=float(rec["coverage_share"]/rec["mean_eligible_count"]) if rec["mean_eligible_count"]>0 else np.nan
        # pair trend Jaccard
        js=[]
        for a in range(len(ids)):
            for b in range(a+1,len(ids)):
                u=np.sum(elig[:,a] | elig[:,b])
                if u: js.append(float(np.sum(elig[:,a] & elig[:,b])/u))
        rec["mean_pair_trend_jaccard"]=float(np.mean(js)) if js else np.nan
        rec["max_pair_trend_jaccard"]=float(np.max(js)) if js else np.nan
        _, target=self.target_state(k)
        active=target[target>=0]
        if len(active):
            vals,cnt=np.unique(active,return_counts=True); sh=cnt/cnt.sum(); hhi=float(np.square(sh).sum())
            rec["active_leader_count"]=int(len(vals)); rec["leader_hhi"]=hhi; rec["effective_leader_count"]=float(1/hhi)
        else:
            rec["active_leader_count"]=0; rec["leader_hhi"]=np.nan; rec["effective_leader_count"]=np.nan
        # switch quality: new leader next-period gross versus old leader counterfactual on switch day
        alpha=[]; prod=[]
        for t in range(1,len(target)):
            old,new=int(target[t-1]),int(target[t])
            if old==new: continue
            nr=0.0 if new<0 else float(self.gross[t,new])
            orr=0.0 if old<0 else float(self.gross[t,old])
            a=nr-orr; alpha.append(a); prod.append(a>0)
        rec["productive_switch_share"]=float(np.mean(prod)) if prod else np.nan
        rec["switch_counterfactual_gain_mean"]=float(np.mean(alpha)) if alpha else np.nan
        rec["switch_rate"]=float(rec["switch_events"]/len(self.dates)) if len(self.dates) else np.nan
        return rec


def greedy_path(ev: Eval, seed: str, all_syms: list[str], collector: set[tuple[str,...]]) -> dict[int,tuple[str,...]]:
    cur={seed}; out={1:keyify(cur)}; collector.add(keyify(cur))
    while len(cur)<MAX_K:
        bestv=-np.inf; besty=None
        for y in all_syms:
            if y in cur: continue
            v=ev.quick_add_log(cur,y)
            if v>bestv+TOL or (abs(v-bestv)<=TOL and (besty is None or y<besty)):
                bestv,besty=v,y
        if besty is None: break
        cur.add(besty); kk=keyify(cur); out[len(cur)]=kk; collector.add(kk)
    return out


def refine_fixed_k(ev: Eval, start: tuple[str,...], swap_pool: list[str], collector:set[tuple[str,...]]) -> tuple[str,...]:
    cur=set(start)
    for _ in range(REFINE_ROUNDS):
        base=ev.evaluate(cur)["log_growth"]; bestv=base; best=None
        for x in sorted(cur):
            base_minus=cur-{x}
            for y in swap_pool:
                if y in cur: continue
                cand=keyify(base_minus|{y}); v=ev.evaluate(cand)["log_growth"]; collector.add(cand)
                if v>bestv+TOL:
                    bestv=v; best=set(cand)
        if best is None: break
        cur=best
    return keyify(cur)


def stochastic_fixed_k(ev: Eval, start: tuple[str,...], all_syms:list[str], steps:int, rng:np.random.Generator, collector:set[tuple[str,...]]) -> tuple[str,...]:
    cur=set(start); curv=ev.evaluate(cur)["log_growth"]; best=set(cur); bestv=curv
    for st in range(steps):
        x=str(rng.choice(sorted(cur))); outside=[z for z in all_syms if z not in cur]
        y=str(rng.choice(outside)); cand=(cur-{x})|{y}; ck=keyify(cand); v=ev.evaluate(ck)["log_growth"]; collector.add(ck)
        temp=0.06*max(0.02,1-st/max(1,steps))
        if v>=curv or rng.random()<math.exp(min(0.0,(v-curv)/temp)):
            cur=set(ck); curv=v
        if v>bestv+TOL: best=set(ck); bestv=v
    return keyify(best)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--database-url",default=os.getenv("ETF_DAILY_BARS_DATABASE_URL")); ap.add_argument("--output-dir",default="oure-stage6c-output")
    args=ap.parse_args()
    if not args.database_url: raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    eng=create_engine(_db_url(args.database_url),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars["symbol"]=bars["symbol"].astype(str)
    feat=build_features(bars); feat["symbol"]=feat["symbol"].astype(str)
    cal,score,r2,slope,close,op,gross,ret=build_wides(bars,feat); cal=pd.DatetimeIndex(cal)
    if CASH not in score.columns: raise RuntimeError("cash missing")
    meta=pd.read_sql_query(text("select symbol,has_daily_bars,leveraged_flag,inverse_flag from public.instrument_metadata_current"),eng); meta["symbol"]=meta["symbol"].astype(str)
    guarded=set(meta.loc[meta["has_daily_bars"].fillna(False).astype(bool)&(~meta["leveraged_flag"].fillna(False).astype(bool))&(~meta["inverse_flag"].fillna(False).astype(bool)),"symbol"].astype(str))
    s0=int(cal.searchsorted(START,side="left")); pre=cal[max(0,s0-252):s0]
    candidates=[]
    for s in sorted(set(score.columns.astype(str)) & guarded):
        if s==CASH: continue
        x=close.loc[pre,s].to_numpy(float) if s in close.columns else np.array([])
        if len(x)>=240 and np.isfinite(x).sum()>=240 and np.isfinite(x[-1]): candidates.append(s)
    sigpos=np.flatnonzero((cal>=START)&(cal<=END))
    sigpos=sigpos[sigpos < len(cal)-2]
    dates=cal[sigpos]
    ev=Eval(score,gross,dates,candidates)
    singles=[]
    for s in candidates:
        r=ev.evaluate({s}); singles.append((s,r["log_growth"]))
    singles=sorted(singles,key=lambda z:(-z[1],z[0])); top=[s for s,_ in singles]
    pd.DataFrame(singles,columns=["symbol","log_growth"]).to_csv(out/"singleton_values.csv",index=False)
    collector:set[tuple[str,...]]=set(); paths=[]
    for seed in top[:min(GREEDY_SEEDS,len(top))]: paths.append(greedy_path(ev,seed,candidates,collector))
    best_by_k={}
    for k in range(1,min(MAX_K,len(candidates))+1):
        opts=[p[k] for p in paths if k in p]
        if not opts: continue
        incumbent=max(opts,key=lambda z:ev.evaluate(z)["log_growth"])
        incumbent=refine_fixed_k(ev,incumbent,top[:min(SWAP_SHORTLIST,len(top))],collector)
        best_by_k[k]=incumbent; collector.add(incumbent)
    rng=np.random.default_rng(SEED)
    for k in ANCHORS:
        if k not in best_by_k or k>len(candidates): continue
        starts=[best_by_k[k]]
        for _ in range(STOCH_STARTS-1): starts.append(keyify(rng.choice(candidates,size=k,replace=False).tolist()))
        opts=[]
        for st in starts: opts.append(stochastic_fixed_k(ev,st,candidates,STOCH_STEPS,rng,collector))
        best=max(opts+[best_by_k[k]],key=lambda z:ev.evaluate(z)["log_growth"])
        best=refine_fixed_k(ev,best,top[:min(SWAP_SHORTLIST,len(top))],collector)
        best_by_k[k]=best; collector.add(best)
    # propagate no assumptions: non-anchor K retain their independently refined greedy frontier
    frontier=[]
    for k in sorted(best_by_k):
        d=ev.diagnostics(best_by_k[k]); d["members"]=",".join(best_by_k[k]); d["k_including_cash"]=k+1; frontier.append(d)
    fdf=pd.DataFrame(frontier).sort_values("k_noncash"); fdf.to_csv(out/"best_searched_frontier_by_k.csv",index=False)
    # elite discovered sets at each anchor, top25
    erows=[]
    for k in ANCHORS:
        sets=[z for z in collector if len(z)==k]
        sets=sorted(sets,key=lambda z:ev.evaluate(z)["log_growth"],reverse=True)[:25]
        for rank,z in enumerate(sets,1):
            d=ev.diagnostics(z); d.update({"anchor_k":k,"rank":rank,"members":",".join(z)}); erows.append(d)
    pd.DataFrame(erows).to_csv(out/"anchor_elite_sets.csv",index=False)
    # same-K random controls at anchors
    rrows=[]
    for k in ANCHORS:
        if k>len(candidates): continue
        seen=set()
        while len(seen)<RANDOM_N:
            seen.add(keyify(rng.choice(candidates,size=k,replace=False).tolist()))
        for z in seen:
            d=ev.diagnostics(z); d.update({"anchor_k":k,"members":",".join(z)}); rrows.append(d)
    rdf=pd.DataFrame(rrows); rdf.to_csv(out/"same_k_random_controls.csv",index=False)
    # compact summary
    bestrow=fdf.loc[fdf["log_growth"].idxmax()].to_dict()
    anchor_cmp=[]
    for k in ANCHORS:
        if k not in best_by_k: continue
        e=ev.evaluate(best_by_k[k]); rr=rdf[rdf["anchor_k"]==k]
        anchor_cmp.append({"k_noncash":k,"searched_total_return":e["total_return"],"searched_log_growth":e["log_growth"],"random_median_total_return":float(rr["total_return"].median()),"random_p90_total_return":float(rr["total_return"].quantile(.9))})
    summary={"study":"OURE Stage6C full-market 2022-24 K frontier","status":"completed","candidate_count":len(candidates),"period_start":str(dates.min().date()),"period_end":str(dates.max().date()),"searched_best":bestrow,"anchor_comparison":anchor_cmp,"warning":"heuristic searched frontier, not exact/global optimum"}
    (out/"stage6c_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2,default=str))

if __name__=="__main__": main()
