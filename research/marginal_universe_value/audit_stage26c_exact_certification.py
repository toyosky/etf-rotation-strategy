#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

TOL = 1e-9

def stats(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"months": 0}
    return {
        "months": int(len(df)),
        "primary_exact_months": int((df.solver_primary_status == 0).sum()),
        "min_cardinality_exact_months": int(((df.solver_primary_status == 0) & (df.solver_secondary_status == 0)).sum()),
        "primary_exact_share": float((df.solver_primary_status == 0).mean()),
        "min_cardinality_exact_share": float(((df.solver_primary_status == 0) & (df.solver_secondary_status == 0)).mean()),
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--months", required=True)
    p.add_argument("--report", default="muv-stage26c-exact-certification-report.json")
    p.add_argument("--certified", default="muv-stage26c-certified-months.csv")
    a=p.parse_args()
    m=pd.read_csv(a.months)
    m["decision_date"]=pd.to_datetime(m["decision_date"])
    m["primary_exact_certified"]=(m.solver_primary_status==0)
    m["min_cardinality_certified"]=(m.solver_primary_status==0)&(m.solver_secondary_status==0)
    m["singleton_sanity_ok"]=m.oracle_log >= m.best_singleton_log - TOL
    cert=m[m.min_cardinality_certified].copy()
    violations=m[~m.singleton_sanity_ok].copy()
    cert_viol=cert[~cert.singleton_sanity_ok]
    era1=m[(m.decision_date>=pd.Timestamp('2021-01-01'))&(m.decision_date<=pd.Timestamp('2024-12-31'))]
    era2=m[(m.decision_date>=pd.Timestamp('2025-01-01'))&(m.decision_date<=pd.Timestamp('2026-12-31'))]
    cert_k={"months":int(len(cert))}
    if len(cert):
        cert_k.update({"mean":float(cert.oracle_k.mean()),"median":float(cert.oracle_k.median()),"p90":float(cert.oracle_k.quantile(.9)),"min":int(cert.oracle_k.min()),"max":int(cert.oracle_k.max())})
    both_eras = int(((era1.solver_primary_status==0)&(era1.solver_secondary_status==0)).sum())>0 and int(((era2.solver_primary_status==0)&(era2.solver_secondary_status==0)).sum())>0
    report={
      "stage":"26C","parent_stage":"stage26","label_version":"set_value_next20_fixed_ols_v2",
      "source_run_id":34755327797,"source_is_future_aware_oracle":True,
      "overall":stats(m),"era_2021_2024":stats(era1),"era_2025_2026":stats(era2),
      "certified_k":cert_k,
      "singleton_sanity_violations_all_incumbents":int(len(violations)),
      "singleton_sanity_violations_certified":int(len(cert_viol)),
      "violation_months":[d.strftime('%Y-%m-%d') for d in violations.decision_date],
      "certification_covers_both_eras":bool(both_eras),
      "decision":"support_exact_subset_only" if both_eras and len(cert_viol)==0 else "global_exact_unresolved_use_certified_subset_only",
      "stage27_constraint":"Do not claim all-month exact K*. Use certified exact months only for exact-vs-local validation; all other geometry must be labeled local/greedy or bounded/uncertified."
    }
    Path(a.report).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    cert.to_csv(a.certified,index=False)
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
