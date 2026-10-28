#!/usr/bin/env python3
"""Cross-check Tencent financial fields against independently published company-report summaries.

Benchmark URLs and values are human-curated, not scraped or an official PDF audit.
"""
import json,sys
from pathlib import Path
ROOT=Path("research/stock_value")
RESULTS=ROOT/"results"
BENCH=ROOT/"financial-benchmarks-20261028.json"
def main():
    fin=json.loads((RESULTS/"financial-summary.json").read_text(encoding="utf-8"))
    bench=json.loads(BENCH.read_text(encoding="utf-8"))
    prices=json.loads((RESULTS/"latest.json").read_text(encoding="utf-8"))
    items={x["symbol"]:x for x in fin["items"]}
    checks=[]
    tolerance=float(bench["tolerance_100m_cny"])
    for code,expected in bench["benchmarks"].items():
        actual=items.get(code)
        reasons=[]
        if not actual:reasons.append("MISSING_TENCENT_REPORT")
        else:
            if actual["latest_report"]!=expected["period"]:reasons.append("PERIOD_MISMATCH")
            if expected["published"]>fin["as_of"]:reasons.append("BENCHMARK_PUBLISHED_AFTER_ASOF")
            for source_key,actual_key in (("deducted_profit_100m","deducted_net_profit_100m_cny"),
                                          ("operating_cash_flow_100m","operating_cash_flow_100m_cny")):
                value=actual.get(actual_key)
                if value is None or abs(value-expected[source_key])>tolerance+1e-8:
                    reasons.append(source_key+"_MISMATCH")
        checks.append({"symbol":code,"period":expected["period"],
                       "benchmark_url":expected["url"],"benchmark_published":expected["published"],
                       "deducted_profit_100m":expected["deducted_profit_100m"],
                       "operating_cash_flow_100m":expected["operating_cash_flow_100m"],
                       "status":"PASS" if not reasons else "FAIL","reasons":reasons})
    financial_pass=len(checks)==7 and all(c["status"]=="PASS" for c in checks)
    price_pass=bool(prices.get("price_full_acceptance",prices.get("full_acceptance",False)))
    payload={"as_of":fin["as_of"],"source":"Tencent raw mapped fields vs independent published financial summaries",
             "official_exchange_pdf_verified":False,"financial_crosscheck_pass":financial_pass,
             "price_crosscheck_pass":price_pass,"overall_pilot_acceptance":financial_pass and price_pass,
             "items":checks}
    (RESULTS/"financial-validation.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    prices["price_full_acceptance"]=price_pass
    prices["financial_data_status"]="INDEPENDENT_PUBLIC_REPORT_CROSSCHECK_PASS" if financial_pass else "FINANCIAL_CROSSCHECK_FAILED"
    prices["financial_validation_file"]="research/stock_value/results/financial-validation.json"
    prices["full_acceptance"]=financial_pass and price_pass
    (RESULTS/"latest.json").write_text(json.dumps(prices,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"financial_checks_passed":sum(x["status"]=="PASS" for x in checks),
                      "price_pass":price_pass,"overall_pilot_acceptance":payload["overall_pilot_acceptance"]}))
    return 0 if payload["overall_pilot_acceptance"] else 1
if __name__=="__main__":sys.exit(main())
