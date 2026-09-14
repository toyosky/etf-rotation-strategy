#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sqlalchemy import create_engine, text

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import optimal_universe_reverse_engineering.oure_stage5_history_transfer as s5
import optimal_universe_reverse_engineering.oure_stage6c_fullmarket_2022_2024_k_frontier as s6c
import optimal_universe_reverse_engineering.oure_stage6f_rf_surrogate_value as s6g
import optimal_universe_reverse_engineering.oure_stage6e_rf_k30_rank as s6e
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

LOOKBACK = 126
FUTURE = 126
SEED = 20260914
RF_HIGH_Q = 0.80
PRED_STRATA = 5
RESID_TAIL = 0.30
CORR_CLUSTER = 0.80
SWAP_OUTSIDERS = 10

MEMBER_FEATURES = [
    "member_ret63_median", "member_ret63_iqr", "member_ret63_p10",
    "member_ret126_median", "member_ret126_iqr", "member_ret126_p10",
    "member_vol126_median", "member_vol126_iqr",
    "member_mdd126_median", "member_mdd126_p90_magnitude",
    "member_elig_share_median", "member_elig_share_iqr", "member_elig_share_p10",
    "member_leader_share_median", "member_leader_share_max", "member_leader_share_iqr",
]
PAIR_FEATURES = [
    "pair_corr_median", "pair_corr_iqr", "pair_corr_p90",
    "pair_elig_jaccard_median", "pair_elig_jaccard_iqr", "pair_elig_jaccard_p90",
    "pair_score_crossing_median", "pair_score_crossing_iqr", "pair_score_crossing_p90",
]
ROBUST_FEATURES = [
    "struct_active_leader_count", "struct_leader_hhi", "struct_effective_leader_count",
    "loo_log_loss_median", "loo_log_loss_p90", "loo_log_loss_max",
    "swap_best_improvement", "swap_median_best_per_outsider", "swap_positive_outsider_share",
    "corr_cluster_count", "corr_cluster_largest_share",
]
STRUCT_FEATURES = MEMBER_FEATURES + PAIR_FEATURES + ROBUST_FEATURES
FAMILY = {**{x:"member" for x in MEMBER_FEATURES}, **{x:"pair" for x in PAIR_FEATURES}, **{x:"robustness" for x in ROBUST_FEATURES}}


def spearman(a, b) -> float:
    v = s6g.spearman(a, b)
    return float(v) if np.isfinite(v) else np.nan


def q(x, p):
    a = np.asarray(x, float)
    a = a[np.isfinite(a)]
    return float(np.quantile(a, p)) if len(a) else np.nan


def iqr(x):
    return q(x, .75) - q(x, .25)


def fit_first_layer(train: pd.DataFrame, test: pd.DataFrame):
    med = train[s6g.FEATURES].replace([np.inf,-np.inf], np.nan).median(axis=0)
    xtr = train[s6g.FEATURES].replace([np.inf,-np.inf], np.nan).fillna(med).fillna(0.0)
    xte = test[s6g.FEATURES].replace([np.inf,-np.inf], np.nan).fillna(med).fillna(0.0)
    rf = RandomForestRegressor(**s6g.RF_PARAMS)
    rf.fit(xtr, train["future_log_growth"].astype(float))
    return rf.predict(xte)


def block_base(block_no, start_pos, cal, score, gross, close, meta, rng):
    d = int(start_pos)
    if d < max(252, LOOKBACK) or d + FUTURE > len(cal)-2:
        return None
    decision_date = pd.Timestamp(cal[d])
    pool = s5.available_pool(close, meta, cal, d)
    if len(pool) < s6g.K:
        raise RuntimeError(f"too few candidates at {decision_date.date()}: {len(pool)}")
    past_dates = pd.DatetimeIndex(cal[d-LOOKBACK:d])
    future_dates = pd.DatetimeIndex(cal[d:d+FUTURE])
    past_ev = s6c.Eval(score, gross, past_dates, pool)
    future_ev = s6c.Eval(score, gross, future_dates, pool)
    combo_family, _, _ = s6g.build_family_library(past_ev, pool, rng)
    rows=[]
    for u,fam in combo_family.items():
        fut=future_ev.evaluate(u)
        rows.append({
            "block":f"B{block_no:02d}", "block_no":block_no,
            "decision_date":str(decision_date.date()), "family_id":fam,
            "members":",".join(u), "pool_n":len(pool),
            "future_log_growth":float(fut["log_growth"]),
            **s6e.feature_row(past_ev,u),
        })
    return pd.DataFrame(rows), past_ev, pool


def member_total_return(r: np.ndarray) -> float:
    a=np.asarray(r,float); a=np.where(np.isfinite(a),a,0.0)
    return float(np.prod(1.0+a)-1.0)


def member_mdd(r: np.ndarray) -> float:
    a=np.asarray(r,float); a=np.where(np.isfinite(a),a,0.0)
    eq=np.cumprod(1.0+a)
    if not len(eq): return np.nan
    return float(np.min(eq/np.maximum.accumulate(eq)-1.0))


def components_from_corr(corr: np.ndarray, threshold: float):
    n=corr.shape[0]; seen=np.zeros(n,bool); sizes=[]
    for s in range(n):
        if seen[s]: continue
        stack=[s]; seen[s]=True; c=0
        while stack:
            a=stack.pop(); c+=1
            neigh=np.where(np.isfinite(corr[a]) & (corr[a]>=threshold))[0]
            for b in neigh:
                if not seen[b]: seen[b]=True; stack.append(int(b))
        sizes.append(c)
    return len(sizes), max(sizes)/n if n else np.nan


def structural_row(ev:s6c.Eval, members:tuple[str,...], pool:list[str]) -> dict:
    ids=[ev.idx[s] for s in members]
    sm=ev.score[:,ids]
    gr=ev.gross[:,ids]
    elig=np.isfinite(sm)

    ret126=[member_total_return(gr[:,j]) for j in range(len(ids))]
    ret63=[member_total_return(gr[-63:,j]) for j in range(len(ids))]
    vol=[float(np.nanstd(gr[:,j],ddof=1)) for j in range(len(ids))]
    mdd=[member_mdd(gr[:,j]) for j in range(len(ids))]
    es=elig.mean(axis=0)

    _,target=ev.target_state(members)
    leader_sh=[]
    denom=max(1,int(np.sum(target>=0)))
    for j in ids:
        leader_sh.append(float(np.sum(target==j)/denom))

    corrs=[]; jacs=[]; crossings=[]
    for a in range(len(ids)):
        for b in range(a+1,len(ids)):
            both=np.isfinite(gr[:,a])&np.isfinite(gr[:,b])
            if both.sum()>=10:
                corrs.append(float(np.corrcoef(gr[both,a],gr[both,b])[0,1]))
            u=np.sum(elig[:,a]|elig[:,b])
            jacs.append(float(np.sum(elig[:,a]&elig[:,b])/u) if u else np.nan)
            da=sm[:,a]-sm[:,b]
            valid=np.isfinite(da[:-1])&np.isfinite(da[1:])
            if valid.sum():
                crossings.append(float(np.mean((np.sign(da[:-1][valid])*np.sign(da[1:][valid]))<0)))
            else: crossings.append(np.nan)

    diag=ev.diagnostics(members)
    full=float(diag["log_growth"])
    loo=[]
    ms=set(members)
    for x in members:
        v=float(ev.evaluate(ms-{x})["log_growth"])
        loo.append(full-v)

    outsiders=[]
    for s in pool:
        if s in ms: continue
        outsiders.append((s,float(ev.evaluate({s})["log_growth"])))
    outsiders=sorted(outsiders,key=lambda z:(-z[1],z[0]))[:SWAP_OUTSIDERS]
    best_per=[]
    best_all=-np.inf
    for y,_ in outsiders:
        bv=-np.inf
        for x in members:
            cand=(ms-{x})|{y}
            imp=float(ev.evaluate(cand)["log_growth"])-full
            if imp>bv: bv=imp
            if imp>best_all: best_all=imp
        best_per.append(bv)

    corrmat=np.full((len(ids),len(ids)),np.nan)
    np.fill_diagonal(corrmat,1.0)
    for a in range(len(ids)):
        for b in range(a+1,len(ids)):
            both=np.isfinite(gr[:,a])&np.isfinite(gr[:,b])
            if both.sum()>=10:
                c=float(np.corrcoef(gr[both,a],gr[both,b])[0,1]); corrmat[a,b]=corrmat[b,a]=c
    cn,cl=components_from_corr(corrmat,CORR_CLUSTER)

    return {
        "member_ret63_median":q(ret63,.5),"member_ret63_iqr":iqr(ret63),"member_ret63_p10":q(ret63,.1),
        "member_ret126_median":q(ret126,.5),"member_ret126_iqr":iqr(ret126),"member_ret126_p10":q(ret126,.1),
        "member_vol126_median":q(vol,.5),"member_vol126_iqr":iqr(vol),
        "member_mdd126_median":q(mdd,.5),"member_mdd126_p90_magnitude":q([-x for x in mdd],.9),
        "member_elig_share_median":q(es,.5),"member_elig_share_iqr":iqr(es),"member_elig_share_p10":q(es,.1),
        "member_leader_share_median":q(leader_sh,.5),"member_leader_share_max":q(leader_sh,1),"member_leader_share_iqr":iqr(leader_sh),
        "pair_corr_median":q(corrs,.5),"pair_corr_iqr":iqr(corrs),"pair_corr_p90":q(corrs,.9),
        "pair_elig_jaccard_median":q(jacs,.5),"pair_elig_jaccard_iqr":iqr(jacs),"pair_elig_jaccard_p90":q(jacs,.9),
        "pair_score_crossing_median":q(crossings,.5),"pair_score_crossing_iqr":iqr(crossings),"pair_score_crossing_p90":q(crossings,.9),
        "struct_active_leader_count":float(diag.get("active_leader_count",np.nan)),
        "struct_leader_hhi":float(diag.get("leader_hhi",np.nan)),
        "struct_effective_leader_count":float(diag.get("effective_leader_count",np.nan)),
        "loo_log_loss_median":q(loo,.5),"loo_log_loss_p90":q(loo,.9),"loo_log_loss_max":q(loo,1),
        "swap_best_improvement":float(best_all) if np.isfinite(best_all) else np.nan,
        "swap_median_best_per_outsider":q(best_per,.5),
        "swap_positive_outsider_share":float(np.mean(np.asarray(best_per)>0)) if best_per else np.nan,
        "corr_cluster_count":float(cn),"corr_cluster_largest_share":float(cl),
    }


def make_pairs(g:pd.DataFrame):
    out=[]
    # deterministic quantile strata; duplicates='drop' can only reduce strata, not threshold.
    try: strata=pd.qcut(g["rf_pred"].rank(method="first"),PRED_STRATA,labels=False)
    except Exception: strata=pd.Series(np.zeros(len(g),int),index=g.index)
    gg=g.copy(); gg["pred_stratum"]=strata
    for st,h in gg.groupby("pred_stratum"):
        n=max(1,int(np.floor(len(h)*RESID_TAIL)))
        good=h.nlargest(n,"residual").copy(); bad=h.nsmallest(n,"residual").copy()
        avail=set(bad.index.tolist())
        for gi,gr in good.sort_values(["rf_pred","members"]).iterrows():
            if not avail: break
            bi=min(avail,key=lambda z:(abs(float(h.loc[z,"rf_pred"])-float(gr["rf_pred"])),str(h.loc[z,"members"])))
            avail.remove(bi)
            br=h.loc[bi]
            out.append({"block":gr["block"],"good_idx":int(gi),"bad_idx":int(bi),"pred_abs_diff":abs(float(gr["rf_pred"])-float(br["rf_pred"]))})
    return out


def scale_for_feature(g:pd.DataFrame,f:str)->float:
    z=g[f].astype(float).replace([np.inf,-np.inf],np.nan).dropna()
    if len(z)<3:return 1.0
    sc=float(z.quantile(.75)-z.quantile(.25))
    if not np.isfinite(sc) or sc<=1e-12: sc=float(z.std(ddof=1))
    return sc if np.isfinite(sc) and sc>1e-12 else 1.0


def audit_features(high:pd.DataFrame,pairs:pd.DataFrame):
    rows=[]; block_rows=[]
    for f in STRUCT_FEATURES:
        valid_blocks=[]; signs=[]; std_abs=[]; rdirs=[]
        for b,g in high.groupby("block"):
            pb=pairs[pairs["block"]==b]
            dif=[]
            for _,p in pb.iterrows():
                a=high.loc[int(p["good_idx"]),f]; z=high.loc[int(p["bad_idx"]),f]
                if np.isfinite(a) and np.isfinite(z): dif.append(float(a-z))
            if not dif: continue
            md=float(np.median(dif)); sc=scale_for_feature(g,f); rs=spearman(g[f],g["residual"])
            valid_blocks.append(b); signs.append(np.sign(md)); std_abs.append(abs(md/sc)); rdirs.append(np.sign(rs) if np.isfinite(rs) else 0)
            block_rows.append({"feature":f,"family":FAMILY[f],"block":b,"pair_n":len(dif),"median_good_minus_bad":md,"standardized_abs_effect":abs(md/sc),"residual_spearman":rs})
        if valid_blocks:
            overall=float(np.median([r["median_good_minus_bad"] for r in block_rows if r["feature"]==f]))
            od=np.sign(overall)
            sign_agree=float(np.mean([x==od for x in signs])) if od!=0 else 0.0
            corr_agree=float(np.mean([x==od for x in rdirs])) if od!=0 else 0.0
            med_std=float(np.median(std_abs))
        else:
            overall=np.nan; od=0; sign_agree=corr_agree=med_std=0.0
        stable=bool(len(valid_blocks)>=6 and sign_agree>=.75 and med_std>=.15 and corr_agree>=.75)
        rows.append({"feature":f,"family":FAMILY[f],"valid_blocks":len(valid_blocks),"overall_median_good_minus_bad":overall,"direction":int(od),"block_sign_agreement":sign_agree,"median_abs_standardized_effect":med_std,"residual_spearman_direction_agreement":corr_agree,"stable":stable})
    return pd.DataFrame(rows),pd.DataFrame(block_rows)


def score_metrics(g:pd.DataFrame,score_col:str):
    ic=spearman(g[score_col],g["future_log_growth"])
    n=min(50,len(g)); top=g.nlargest(n,score_col)
    dec=max(1,int(np.ceil(len(g)*.10))); td=g.nlargest(dec,score_col)
    return ic,float(top["future_rank_pct"].mean()),float(td["future_rank_pct"].mean())


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--database-url",default=os.getenv("ETF_DAILY_BARS_DATABASE_URL")); ap.add_argument("--output-dir",default="oure-stage6l-output")
    args=ap.parse_args()
    if not args.database_url: raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    eng=create_engine(_db_url(args.database_url),pool_pre_ping=True)
    bars=load_daily_bars(eng); bars["symbol"]=bars["symbol"].astype(str)
    feat=build_features(bars); feat["symbol"]=feat["symbol"].astype(str)
    cal,score,r2,slope,close,op,gross,ret=build_wides(bars,feat); cal=pd.DatetimeIndex(cal)
    meta=pd.read_sql_query(text("select symbol,has_daily_bars,leveraged_flag,inverse_flag from public.instrument_metadata_current"),eng); meta["symbol"]=meta["symbol"].astype(str)

    start0=int(cal.searchsorted(pd.Timestamp("2022-01-01"),side="left")); rng=np.random.default_rng(SEED)
    blocks=[]; evs={}; pools={}; pos=start0; b=1
    while True:
        pack=block_base(b,pos,cal,score,gross,close,meta,rng)
        if pack is None: break
        df,ev,pool=pack; blocks.append(df); evs[f"B{b:02d}"]=ev; pools[f"B{b:02d}"]=pool
        b+=1; pos+=FUTURE
    data=pd.concat(blocks,ignore_index=True)
    bids=list(data[["block","block_no"]].drop_duplicates().sort_values("block_no")["block"])
    high_frames=[]; pair_rows=[]
    for j in range(1,len(bids)):
        prev=data[data.block==bids[j-1]].reset_index(drop=True); test=data[data.block==bids[j]].copy().reset_index(drop=True)
        test["rf_pred"]=fit_first_layer(prev,test); test["residual"]=test["future_log_growth"]-test["rf_pred"]
        test["future_rank_pct"]=s6g.rank_pct(test["future_log_growth"])
        cutoff=float(test["rf_pred"].quantile(RF_HIGH_Q))
        h=test[test["rf_pred"]>=cutoff].copy().reset_index(drop=True)
        ev=evs[bids[j]]; pool=pools[bids[j]]
        structs=[]
        for _,r in h.iterrows():
            u=tuple(x for x in str(r["members"]).split(",") if x)
            structs.append(structural_row(ev,u,pool))
        h=pd.concat([h.reset_index(drop=True),pd.DataFrame(structs)],axis=1)
        offset=sum(len(x) for x in high_frames); h.index=np.arange(offset,offset+len(h)); high_frames.append(h)
        pair_rows.extend(make_pairs(h))
    high=pd.concat(high_frames,axis=0); pairs=pd.DataFrame(pair_rows)
    high.to_csv(out/"stage6l_rf_high_structural_samples.csv",index=True,index_label="row_id")
    pairs.to_csv(out/"stage6l_matched_pairs.csv",index=False)

    audit,blockaudit=audit_features(high,pairs)
    audit.to_csv(out/"stage6l_structural_audit_summary.csv",index=False); blockaudit.to_csv(out/"stage6l_structural_audit_by_block.csv",index=False)
    stable=audit[audit.stable]["feature"].tolist(); fams=sorted(set(FAMILY[x] for x in stable))
    audit_pass=bool(len(stable)>=3 and len(fams)>=2)

    stage2=[]
    if audit_pass:
        ordered=sorted(high["block"].unique())
        for j in range(2,len(ordered)):
            train=high[high.block.isin(ordered[:j])].copy(); test=high[high.block==ordered[j]].copy()
            meds=train[stable].replace([np.inf,-np.inf],np.nan).median(); xtr=train[stable].replace([np.inf,-np.inf],np.nan).fillna(meds).fillna(0.0); xte=test[stable].replace([np.inf,-np.inf],np.nan).fillna(meds).fillna(0.0)
            mu=xtr.mean(); sd=xtr.std(ddof=0).replace(0,1).fillna(1); xtr=(xtr-mu)/sd; xte=(xte-mu)/sd
            model=Ridge(alpha=1.0); model.fit(xtr,train["residual"].astype(float)); test["pred_residual"]=model.predict(xte); test["final_score"]=test["rf_pred"]+test["pred_residual"]
            # Baseline past126-set return, inside RF-high.
            for col in ["rf_pred","final_score","past126_log_growth"]:
                ic,top50,topdec=score_metrics(test,col); stage2.append({"block":ordered[j],"decision_date":str(test.decision_date.iloc[0]),"rule":col,"spearman":ic,"top50_actual_percentile":top50,"top_decile_actual_percentile":topdec})
            stage2.append({"block":ordered[j],"decision_date":str(test.decision_date.iloc[0]),"rule":"residual_diagnostic","spearman":spearman(test["pred_residual"],test["residual"]),"top50_actual_percentile":np.nan,"top_decile_actual_percentile":np.nan})
    s2=pd.DataFrame(stage2); s2.to_csv(out/"stage6l_stage2_chronological_metrics.csv",index=False)

    stage2_pass=False; stage2_gate={}; era={}
    if audit_pass and not s2.empty:
        piv=s2[s2.rule.isin(["rf_pred","final_score"])].pivot(index=["block","decision_date"],columns="rule",values=["spearman","top50_actual_percentile","top_decile_actual_percentile"])
        delta_ic=(piv[("spearman","final_score")]-piv[("spearman","rf_pred")])
        delta_top=(piv[("top50_actual_percentile","final_score")]-piv[("top50_actual_percentile","rf_pred")])
        delta_dec=(piv[("top_decile_actual_percentile","final_score")]-piv[("top_decile_actual_percentile","rf_pred")])
        resid=s2[s2.rule=="residual_diagnostic"].set_index(["block","decision_date"])["spearman"]
        for key in piv.index:
            y=int(str(key[1])[:4]); er="2022-24" if y<=2024 else "2025-26"
            era.setdefault(er,[]).append(float(delta_ic.loc[key]))
        era_ok=True
        for er,v in era.items():
            if len(v)>=2 and float(np.nanmedian(v))<0: era_ok=False
        stage2_gate={
            "median_spearman_improves":bool(np.nanmedian(piv[("spearman","final_score")])>np.nanmedian(piv[("spearman","rf_pred")])),
            "spearman_win_share_gt_half":bool(np.nanmean(delta_ic>0)>.5),
            "median_top50_delta_ge_0_03":bool(np.nanmedian(delta_top)>=.03),
            "median_topdecile_delta_ge_0_03":bool(np.nanmedian(delta_dec)>=.03),
            "median_residual_ic_gt_zero":bool(np.nanmedian(resid)>0),
            "no_era_direction_reversal":bool(era_ok),
        }; stage2_pass=bool(all(stage2_gate.values()))

    summary={
        "study":"OURE Stage6L RF false-positive matched structural audit",
        "status":"completed",
        "target_block_n":int(high.block.nunique()),
        "rf_high_quantile":RF_HIGH_Q,"matched_pair_n":int(len(pairs)),
        "structural_feature_n":len(STRUCT_FEATURES),"stable_features":stable,"stable_feature_families":fams,
        "audit_gate":{"stable_feature_n_ge_3":len(stable)>=3,"families_ge_2":len(fams)>=2},"audit_pass":audit_pass,
        "stage2_evaluated":bool(audit_pass),"stage2_gate":stage2_gate,"stage2_pass":bool(stage2_pass),
        "decision":"second_layer_residual_ranker_supported" if stage2_pass else ("matched_structure_exists_but_not_chronologically_exploitable" if audit_pass else "no_stable_matched_false_positive_structure"),
        "warning":"Frozen first-layer RF and top20% cohort. Future outcomes only define residual labels/evaluation; all structural X are trailing126 past-only. No feature/gate tuning after preregistration."
    }
    (out/"oure_stage6l_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
