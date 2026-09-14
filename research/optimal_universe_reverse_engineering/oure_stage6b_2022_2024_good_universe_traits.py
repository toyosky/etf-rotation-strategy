#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, os, sys
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from full_market_ols_storage import _db_url, build_features, load_daily_bars
from validate_fixed15_vs_full_market import FIXED15
from walk_forward_candidate_pool import SIDE_COST
from universe_size_then_composition.stage1_oracle_size_mc import build_wides
from optimal_universe_reverse_engineering.oure_stage2_identity_free_architecture import (
    build_target_and_counts, architecture_rows, assoc_table
)

CASH = "511220"
START = pd.Timestamp("2021-01-01")


def period_log(targets, gross_m, exec_dates, start, end):
    em = np.asarray((exec_dates >= pd.Timestamp(start)) & (exec_dates <= pd.Timestamp(end)))
    idx = np.flatnonzero(em)
    nmasks = targets.shape[0]
    out = np.zeros(nmasks, float)
    rows = np.arange(len(exec_dates))
    for mask in range(nmasks):
        raw = targets[mask]
        pos = np.where(raw > 0, raw, -1).astype(np.int16)
        g = np.zeros(len(pos), float)
        active = pos > 0
        g[active] = gross_m[rows[active], pos[active]]
        sides = np.zeros(len(pos), np.int8)
        if len(pos):
            if pos[0] > 0: sides[0] = 1
            if len(pos) > 1:
                changed = pos[1:] != pos[:-1]
                one_cash = (pos[1:] < 0) | (pos[:-1] < 0)
                sides[1:] = np.where(changed, np.where(one_cash, 1, 2), 0)
        net = (1.0 + g) * (1.0 - SIDE_COST * sides) - 1.0
        out[mask] = float(np.log1p(net[idx]).sum())
    return out, em


def member_stats(logv, noncash):
    nmasks = len(logv); n = len(noncash)
    masks = np.arange(nmasks, dtype=int)
    ranks = pd.Series(logv).rank(pct=True, method="average").to_numpy()
    top1 = masks[ranks >= .99]
    top10 = masks[ranks >= .90]
    rows = []
    for b, sym in enumerate(noncash):
        bit = 1 << b
        without = masks[(masks & bit) == 0]
        delta = logv[without | bit] - logv[without]
        rows.append({
            "symbol": sym,
            "top1pct_inclusion_rate": float(np.mean((top1 & bit) != 0)),
            "top10pct_inclusion_rate": float(np.mean((top10 & bit) != 0)),
            "banzhaf_mean_log_delta": float(delta.mean()),
            "banzhaf_median_log_delta": float(np.median(delta)),
            "banzhaf_positive_share": float((delta > 0).mean()),
        })
    return pd.DataFrame(rows).sort_values("banzhaf_mean_log_delta", ascending=False)


def best_by_k(logv, noncash):
    rows=[]
    for k_non in range(len(noncash)+1):
        cand=np.array([m for m in range(len(logv)) if int(m).bit_count()==k_non],dtype=int)
        b=int(cand[np.argmax(logv[cand])])
        members=[noncash[i] for i in range(len(noncash)) if b & (1<<i)]
        rows.append({"k_including_cash":k_non+1,"mask":b,"log_growth":float(logv[b]),"total_return":float(np.exp(logv[b])-1),"members":",".join([CASH,*members])})
    return pd.DataFrame(rows)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--database-url",default=os.getenv("ETF_DAILY_BARS_DATABASE_URL")); ap.add_argument("--output-dir",default="oure-stage6b-output")
    args=ap.parse_args()
    if not args.database_url: raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    eng=create_engine(_db_url(args.database_url),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars["symbol"]=bars["symbol"].astype(str)
    feat=build_features(bars); feat["symbol"]=feat["symbol"].astype(str)
    cal,score,r2,slope,close,op,gross,ret=build_wides(bars,feat)
    fixed=sorted(str(x) for x in FIXED15); noncash=sorted(x for x in fixed if x!=CASH); symbols=[CASH]+noncash
    start_i=int(cal.searchsorted(START,side="left")); spos=np.arange(start_i,len(cal)-2,dtype=int)
    signal_dates=pd.DatetimeIndex(cal[spos]); exec_dates=pd.DatetimeIndex(cal[spos+1])
    sm=score.loc[signal_dates,symbols].to_numpy(float); gm=gross.loc[signal_dates,symbols].to_numpy(float); gm=np.where(np.isfinite(gm),gm,0.0)
    targets,counts=build_target_and_counts(sm,len(noncash)); elig=np.isfinite(sm[:,1:]); masks=np.arange(1<<len(noncash),dtype=int)

    log22, em22=period_log(targets,gm,exec_dates,"2022-01-01","2024-12-31")
    log25, em25=period_log(targets,gm,exec_dates,"2025-01-01",str(exec_dates[-1].date()))
    pd.DataFrame({"mask":masks,"k_including_cash":[1+int(m).bit_count() for m in masks],"log_growth_2022_2024":log22,"return_2022_2024":np.exp(log22)-1,"log_growth_2025_2026":log25,"return_2025_2026":np.exp(log25)-1}).to_csv(out/"subset_period_returns.csv",index=False)

    arch=[]
    arch.extend(architecture_rows(masks,noncash,targets,counts,elig,em22,"2022_2024"))
    arch.extend(architecture_rows(masks,noncash,targets,counts,elig,em25,"2025_2026"))
    adf=pd.DataFrame(arch)
    labels=[]
    for m in masks:
        labels.append({"era":"2022_2024","mask":int(m),"log_growth":float(log22[m])})
        labels.append({"era":"2025_2026","mask":int(m),"log_growth":float(log25[m])})
    merged=adf.merge(pd.DataFrame(labels),on=["era","mask"],how="left",validate="one_to_one")
    merged.to_csv(out/"architecture_by_period.csv",index=False)
    features=["coverage_share","mean_eligible_count","mean_competitors_when_covered","coverage_efficiency","selected_noncash_share","leader_switch_rate","mean_top1_tenure","median_top1_tenure","short_run_le2_share","leader_hhi","active_member_share","mean_pair_trend_jaccard","max_pair_trend_jaccard","mean_member_trend_episode_length"]
    assoc=assoc_table(merged,features); assoc.to_csv(out/"feature_association_by_period.csv",index=False)
    member_stats(log22,noncash).to_csv(out/"member_traits_2022_2024.csv",index=False)
    best_by_k(log22,noncash).to_csv(out/"best_by_k_2022_2024.csv",index=False)
    best=int(np.argmax(log22)); members=[noncash[i] for i in range(len(noncash)) if best&(1<<i)]
    a22=assoc[assoc.era=="2022_2024"].copy(); a22["abs_corr"]=a22["within_k_rank_corr"].abs(); top=a22.sort_values("abs_corr",ascending=False).head(8)
    summary={"best_mask":best,"best_members":[CASH,*members],"best_total_return_2022_2024":float(np.exp(log22[best])-1),"best_k_including_cash":1+best.bit_count(),"top_architecture_associations_2022_2024":top.drop(columns="abs_corr").to_dict(orient="records")}
    (out/"stage6b_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
