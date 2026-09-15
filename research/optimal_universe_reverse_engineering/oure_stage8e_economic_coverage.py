#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

RESEARCH = Path(__file__).resolve().parents[1]
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import optimal_universe_reverse_engineering.oure_stage8a_opportunity30 as s8a
import optimal_universe_reverse_engineering.oure_stage8b_opportunity_k_frontier as s8b
import optimal_universe_reverse_engineering.oure_stage8c_marginal_opportunity_capture as s8c
from full_market_ols_storage import _db_url, build_features, load_daily_bars
from universe_size_then_composition.stage1_oracle_size_mc import build_wides

HIST_SESSIONS = 378
CASH = s8a.CASH
FIX15 = tuple(s8a.FIX15)
START_EXEC = pd.Timestamp("2021-01-01")

# Human-frozen economic taxonomy. These are structural identity rules only.
SLOT_ORDER = [
    "CN_BROAD_CORE","CN_MID_SMALL","CN_GROWTH_BETA","CN_TECH_DIGITAL","CN_HEALTHCARE",
    "CN_CONSUMER","CN_FINANCIALS","CN_INDUSTRIAL_DEFENSE","CN_RESOURCES_ENERGY","CN_VALUE_DEFENSIVE",
    "HK_OFFSHORE_BROAD_VALUE","HK_OFFSHORE_GROWTH",
    "US_BROAD","US_GROWTH_TECH","US_BIOTECH",
    "JAPAN","EUROPE","EMERGING_EX_CHINA","GLOBAL_RESOURCE_EQUITY",
    "GOLD","SILVER","CRUDE_OIL","AGRICULTURE","INDUSTRIAL_COMMODITY",
    "GOV_DURATION","CREDIT","CONVERTIBLE",
]

TECH = {
    "CHINA_COMMUNICATION","CHINA_CYBERSECURITY","CHINA_DIGITAL_ECONOMY","CHINA_ELECTRONICS",
    "CHINA_INFORMATION_TECH","CHINA_INDUSTRIAL_INTERNET","CHINA_INTERNET","CHINA_IOT",
    "CHINA_SEMICONDUCTOR","CHINA_SOFTWARE_AI","CHINA_TECH_BROAD","CHINA_TELECOM","CHINA_TMT","CHINA_VR",
}
HEALTH = {"CHINA_HEALTHCARE","CHINA_HEALTHCARE_PHARMA","CHINA_HEALTHCARE_TCM","CHINA_HEALTHCARE_VACCINE"}
CONSUMER = {"CHINA_CONSUMER","CHINA_DOMESTIC_BRANDS","CHINA_TOURISM","CHINA_MEDIA","CHINA_MEDIA_FILM","CHINA_AGRICULTURE_EQUITY"}
FIN = {"CHINA_BANKS","CHINA_FINANCIALS","CHINA_INSURANCE","CHINA_SECURITIES","CHINA_REAL_ESTATE"}
INDUSTRIAL = {
    "CHINA_ADVANCED_MANUFACTURING","CHINA_AEROSPACE_DEFENSE","CHINA_AUTOMOTIVE","CHINA_BELT_ROAD",
    "CHINA_DEFENSE","CHINA_ENVIRONMENTAL","CHINA_INFRASTRUCTURE","CHINA_LOW_CARBON","CHINA_MACHINERY",
    "CHINA_NEW_ENERGY","CHINA_POWER_GRID","CHINA_ROBOTICS","CHINA_TRANSPORTATION",
}
RESOURCES = {"CHINA_CHEMICAL","CHINA_ENERGY_EQUITY","CHINA_MATERIALS","CHINA_MINING","CHINA_OIL_GAS_EQUITY","CHINA_PETROCHEMICAL","CHINA_RARE_METALS","CHINA_RESOURCES_EQUITY"}
VALUE_DEF = {"CHINA_DIVIDEND","CHINA_SOE","CHINA_UTILITIES","CHINA_FACTOR_CASH_FLOW","CHINA_FACTOR_EQUAL_WEIGHT","CHINA_FACTOR_ESG","CHINA_FACTOR_FUNDAMENTAL","CHINA_FACTOR_QUALITY","CHINA_FACTOR_VALUE"}
HK_BROAD = {"HK_BROAD","HK_H_SHARE","HK_DIVIDEND","HK_SECURITIES","HK_SOE","HK_SOE_DIVIDEND"}
HK_GROWTH = {"HK_AUTOMOTIVE","HK_CONSUMER","HK_HEALTHCARE","HK_NEW_ECONOMY","HK_TECH","CHINA_OFFSHORE_INTERNET","GLOBAL_CHINA_EDUCATION"}
US_BROAD = {"US_SP500","US_DOW_JONES","US_LARGE_50","US_CONSUMER"}
US_GROWTH = {"US_NASDAQ100","US_TECH"}
GLOBAL_RESOURCE = {"US_ENERGY_EQUITY","US_OIL_GAS_EQUITY","GLOBAL_OIL_GAS_EQUITY","CHINA_HK_GOLD_MINERS"}
GOV_BONDS = {"CHINA_GOV_BOND","CHINA_LOCAL_GOV_BOND","CHINA_POLICY_BANK_BOND","CHINA_GOV_POLICY_BANK_BOND"}
CREDIT_BONDS = {"CHINA_CREDIT_BOND","CHINA_SHORT_CREDIT_BOND","CHINA_TECH_INNOVATION_BOND"}


def economic_slot(bucket: str | None) -> str | None:
    b = str(bucket or "")
    if b.startswith("CHINA_BROAD_") or b.startswith("CHINA_LARGE_") or b.startswith("CHINA_REGIONAL_"):
        return "CN_BROAD_CORE"
    if b.startswith("CHINA_MID_") or b.startswith("CHINA_SMALL_") or b.startswith("CHINA_MICRO_") or b == "CHINA_SPECIALIZED_SME":
        return "CN_MID_SMALL"
    if b.startswith("CHINA_GROWTH_") or b in {"CHINA_INNOVATION_GROWTH","CHINA_NEW_ECONOMY","CHINA_FACTOR_GROWTH"}:
        return "CN_GROWTH_BETA"
    if b in TECH: return "CN_TECH_DIGITAL"
    if b in HEALTH: return "CN_HEALTHCARE"
    if b in CONSUMER: return "CN_CONSUMER"
    if b in FIN: return "CN_FINANCIALS"
    if b in INDUSTRIAL: return "CN_INDUSTRIAL_DEFENSE"
    if b in RESOURCES: return "CN_RESOURCES_ENERGY"
    if b in VALUE_DEF: return "CN_VALUE_DEFENSIVE"
    if b in HK_BROAD: return "HK_OFFSHORE_BROAD_VALUE"
    if b in HK_GROWTH: return "HK_OFFSHORE_GROWTH"
    if b in US_BROAD: return "US_BROAD"
    if b in US_GROWTH: return "US_GROWTH_TECH"
    if b == "US_BIOTECH": return "US_BIOTECH"
    if b == "JAPAN_EQUITY": return "JAPAN"
    if b in {"GERMANY_EQUITY","FRANCE_EQUITY"}: return "EUROPE"
    if b in {"INDIA_EQUITY","BRAZIL_EQUITY","SA_EQUITY","ASIA_EQUITY"}: return "EMERGING_EX_CHINA"
    if b in GLOBAL_RESOURCE: return "GLOBAL_RESOURCE_EQUITY"
    if b == "PRECIOUS_METALS_GOLD": return "GOLD"
    if b == "PRECIOUS_METALS_SILVER": return "SILVER"
    if b == "ENERGY_CRUDE_OIL": return "CRUDE_OIL"
    if b == "AGRICULTURE_SOYMEAL": return "AGRICULTURE"
    if b == "ENERGY_CHEMICAL": return "INDUSTRIAL_COMMODITY"
    if b in GOV_BONDS: return "GOV_DURATION"
    if b in CREDIT_BONDS: return "CREDIT"
    if b == "CHINA_CONVERTIBLE_BOND": return "CONVERTIBLE"
    return None


def build_amount_wide(bars: pd.DataFrame, cal: pd.DatetimeIndex) -> pd.DataFrame:
    col = next((c for c in ("amount","money","turnover") if c in bars.columns), None)
    if col is None:
        raise RuntimeError("daily bars have no amount/money/turnover column")
    x = bars[["date","symbol",col]].copy()
    x["date"] = pd.to_datetime(x["date"])
    x["symbol"] = x["symbol"].astype(str)
    w = x.pivot_table(index="date", columns="symbol", values=col, aggfunc="last")
    return w.reindex(cal)


def select_economic(common: list[str], pos: int, cal: pd.DatetimeIndex, amount: pd.DataFrame, meta: pd.DataFrame):
    hist = pd.DatetimeIndex(cal[max(0,pos-60):pos])
    mm = meta.set_index("symbol", drop=False)
    rows=[]; members=[]
    for slot in SLOT_ORDER:
        cand=[]
        for s in common:
            if s not in mm.index: continue
            if economic_slot(mm.at[s,"risk_bucket"]) != slot: continue
            v = amount.loc[hist, s] if s in amount.columns else pd.Series(dtype=float)
            med = float(np.nanmedian(pd.to_numeric(v, errors="coerce").to_numpy(float))) if len(v) else np.nan
            if np.isfinite(med) and med > 0:
                cand.append((med, s))
        if not cand:
            continue
        cand.sort(key=lambda z:(-z[0], z[1]))
        med,s = cand[0]
        members.append(s)
        r=mm.loc[s]
        rows.append({"slot":slot,"symbol":s,"name":r.get("name"),"risk_bucket":r.get("risk_bucket"),"underlying_key":r.get("underlying_key"),"median_amount_60":med,"slot_candidate_n":len(cand)})
    return tuple(sorted(set(members))), rows


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.getenv("ETF_DAILY_BARS_DATABASE_URL"))
    ap.add_argument("--output-dir", default="oure-stage8e-output")
    args=ap.parse_args()
    if not args.database_url: raise SystemExit("Missing ETF_DAILY_BARS_DATABASE_URL")
    out=Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    eng=create_engine(_db_url(args.database_url), pool_pre_ping=True)
    bars=load_daily_bars(eng); bars["symbol"]=bars["symbol"].astype(str); bars["date"]=pd.to_datetime(bars["date"])
    feat=build_features(bars); feat["symbol"]=feat["symbol"].astype(str)
    cal,score,r2,slope,close,op,gross,ret=build_wides(bars,feat); cal=pd.DatetimeIndex(cal)
    amount=build_amount_wide(bars,cal)
    meta=pd.read_sql_query(text("""select symbol,name,asset_class,region_primary,exposure_level1,exposure_level2,underlying_key,risk_bucket,style_sector,is_qdii,has_daily_bars,leveraged_flag,inverse_flag from public.instrument_metadata_current"""),eng)
    meta["symbol"]=meta["symbol"].astype(str).str.zfill(6)

    start0=int(cal.searchsorted(pd.Timestamp("2022-01-01"),side="left"))
    starts=s8a.extended_starts(cal,start0); starts_map={b:p for b,p in starts}
    first_exec_pos=int(cal.searchsorted(START_EXEC,side="left")); first_signal=max(0,first_exec_pos-1); last_signal=len(cal)-3
    need=[]
    for b,p in starts:
        next_p=starts_map.get(b+1,len(cal))
        if next_p<=first_signal or p>last_signal: continue
        if p-HIST_SESSIONS<0: continue
        if all((b-j) in starts_map for j in (1,2,3)): need.append((b,p))
    if not need: raise RuntimeError("no blocks")

    eco_by={}; old15_by={}; old30_by={}; selection_rows=[]
    for bno,pos in need:
        common=s8a.common_pool_for_block(bno,pos,starts_map,cal,close,meta)
        order,_,safe_dates=s8c.old_order_point_in_time(score,gross,cal,pos,common,30)
        old15_by[bno]=tuple(sorted(common[j] for j in order[:15]))
        old30_by[bno]=tuple(sorted(common[j] for j in order[:30]))
        eco,rows=select_economic(common,pos,cal,amount,meta)
        eco_by[bno]=eco
        for r in rows:
            r.update({"block_no":bno,"decision_date":str(pd.Timestamp(cal[pos]).date()),"economic_k":len(eco),"common_pool_n":len(common)})
            selection_rows.append(r)

    fix_by={b:FIX15 for b,_ in need}
    parts=[
        s8a.build_variant_daily("ECONOMIC_COVERAGE",eco_by,starts_map,cal,score,gross,first_signal,last_signal),
        s8a.build_variant_daily("OLD_SAFE_K15",old15_by,starts_map,cal,score,gross,first_signal,last_signal),
        s8a.build_variant_daily("OLD_SAFE_K30",old30_by,starts_map,cal,score,gross,first_signal,last_signal),
        s8a.build_variant_daily("FIX15_BENCHMARK",fix_by,starts_map,cal,score,gross,first_signal,last_signal),
    ]
    daily=pd.concat(parts,ignore_index=True)
    daily=daily.loc[daily["execution_date"]>=START_EXEC].copy()
    ann,_=s8a.summarize(daily)
    full=[]
    for variant,g in daily.groupby("variant"):
        full.append({"variant":variant,**s8b.path_stats(g)})
    full=pd.DataFrame(full)

    sel=pd.DataFrame(selection_rows)
    k_by=(sel.groupby(["block_no","decision_date"],as_index=False).agg(economic_k=("economic_k","first"),filled_slots=("slot","nunique")))

    # Add slot identity to economic daily path and produce usage/contribution diagnostics.
    slot_lookup={(int(r.block_no),str(r.symbol)):str(r.slot) for r in sel.itertuples()}
    eco_daily=daily[daily["variant"]=="ECONOMIC_COVERAGE"].copy()
    eco_daily["slot"]= [slot_lookup.get((int(b),str(t)),"CASH") if pd.notna(t) else "CASH" for b,t in zip(eco_daily["block_no"],eco_daily["target"])]
    eco_daily["log_net"]=np.log1p(np.maximum(eco_daily["net"].astype(float),-0.999999999))
    usage=(eco_daily.groupby("slot",as_index=False).agg(target_days=("target","size"), invested_days=("target",lambda x:int(x.notna().sum())), log_net=("log_net","sum"), turnover_sides=("sides","sum")))
    usage["approx_compounded_contribution"]=np.expm1(usage["log_net"])

    # Coverage audit of metadata buckets not represented by the human map.
    m2=meta.copy(); m2["slot"]=m2["risk_bucket"].map(economic_slot)
    unmapped=(m2[m2["slot"].isna() & m2["has_daily_bars"].fillna(False)].groupby(["asset_class","region_primary","risk_bucket"],dropna=False).size().reset_index(name="n").sort_values("n",ascending=False))

    sel.to_csv(out/"stage8e_selections.csv",index=False)
    k_by.to_csv(out/"stage8e_k_by_block.csv",index=False)
    daily.to_csv(out/"stage8e_daily.csv",index=False)
    ann.to_csv(out/"stage8e_annual.csv",index=False)
    full.to_csv(out/"stage8e_full.csv",index=False)
    usage.to_csv(out/"stage8e_slot_usage.csv",index=False)
    unmapped.to_csv(out/"stage8e_unmapped_buckets.csv",index=False)
    summary={"study":"OURE Stage8E human economic coverage","status":"completed","slot_count_frozen":len(SLOT_ORDER),"blocks":len(need),"economic_k_mean":float(k_by["economic_k"].mean()),"economic_k_min":int(k_by["economic_k"].min()),"economic_k_max":int(k_by["economic_k"].max()),"full":full.to_dict(orient="records")}
    (out/"stage8e_summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    print(full.to_string(index=False))
    print(k_by.to_string(index=False))
    print(usage.sort_values("log_net",ascending=False).to_string(index=False))

if __name__=="__main__": main()
