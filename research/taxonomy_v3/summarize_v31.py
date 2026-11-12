#!/usr/bin/env python3
"""V3.1 verified identity bridging audit against frozen V3 results."""
from __future__ import annotations
from collections import Counter,defaultdict
import argparse,json
from pathlib import Path

def load(p):return json.loads(Path(p).read_text())
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--baseline",type=Path,required=True)
    ap.add_argument("--new",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    old=load(args.baseline/"classifications.json")
    new=load(args.new/"classifications.json")
    orig={r["symbol"]:r for r in old}
    revised={r["symbol"]:r for r in new}
    if set(orig)!=set(revised):raise RuntimeError("Symbol coverage mismatch")
    changes=[]
    for code in sorted(orig):
        a,b=orig[code],revised[code]
        if (a["exact_index_verified"] and not b["exact_index_verified"]) or (
            not a["needs_review"] and b["needs_review"]):
            raise RuntimeError(f"Lost previously approved classification: {code}")
        if a["exact_index_key"] != b["exact_index_key"] or a["needs_review"] != b["needs_review"]:
            changes.append(dict(symbol=code,name=b["name"],old_exact=a["exact_index_key"],
              new_exact=b["exact_index_key"],old_index_name=a["index_name"],
              new_index_name=b["index_name"],old_needs_review=a["needs_review"],
              new_needs_review=b["needs_review"],new_reasons=[x for x in b["classification_reason"]
                                            if "VERIFIED" in x or "REVIEW" in x]))
    oldsummary=load(args.baseline/"summary.json")
    newsum=load(args.new/"summary.json")
    if newsum["total_funds"]!=oldsummary["total_funds"]:
        raise RuntimeError("Classification count changed unrelated to index resolution")
    def overlap_counts(x):
        return {"name_only":sum(bool(r["exact_index_verified"] and r["index_name"] and not r["index_code"]) for r in x),
                "verified":sum(bool(r["exact_index_verified"]) for r in x),
                "approved":sum(not r["needs_review"] for r in x)}
    result=dict(baseline=oldsummary,now=newsum,overlap_before=overlap_counts(old),
      overlap_after=overlap_counts(new),
      previously_approved_regressions=0,
      changed_count=len(changes),
      moved_from_review=sum(a["needs_review"] and not revised[sym]["needs_review"] for sym,a in orig.items()),
      newly_approved_in_archive=sum(a["needs_review"] and not revised[sym]["needs_review"] and revised[sym]["bar_count"]
                                      for sym,a in orig.items()),
      changes=changes,
      alert="Exact-index equivalence only. Cross-index exposure overlap, historical PIT and execution certification remain unresolved.")
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"diff_v31.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    reasons_old=oldsummary["review_reasons"];reasons_new=newsum["review_reasons"]
    lines=["# ETF/LOF 分类 V3.1 官方 CSI 指数目录补证","",
       "目标：只用官方当前指数代码—全称登记，修复 V3 的指数身份候选；不根据价格收益和 ETF 简称自动融合。",
       "","## 实际冻结覆盖变化","",
       "| 指标 | V3 | V3.1 |","|---|---:|---:|",
       f"| 总基金数 | {oldsummary['total_funds']} | {newsum['total_funds']} |",
       f"| 官方完整名称或代码—全称 | {oldsummary['official_full_name_count']} | {newsum['official_full_name_count']} |",
       f"| 当前分类通过 | {oldsummary['fully_classified_current']} | {newsum['fully_classified_current']} |",
       f"| 待复核 | {oldsummary['needs_review']} | {newsum['needs_review']} |",
       f"| 其中官方代码—全称未核实 | {reasons_old.get('OFFICIAL_CODE_NAME_LINK_NOT_VERIFIED',0)} | {reasons_new.get('OFFICIAL_CODE_NAME_LINK_NOT_VERIFIED',0)} |",
       f"| 行情内当前分类通过 | {oldsummary['dedup_comparison']['approved_archive_symbols']} | {newsum['dedup_comparison']['approved_archive_symbols']} |",
       f"| 行情内精确指数组 | {oldsummary['dedup_comparison']['exact_index_groups']} | {newsum['dedup_comparison']['exact_index_groups']} |",
       f"| 分类身份/状态变动产品 | — | {len(changes)} |",
       "","## 代表标的现状","",
       "| 代码 | V3.1 身份 | 分类批准 | 待复核原因 |","|---|---|---|---|"]
    for s in ["159981","159883","512170","516060","513290","501018","510300","510330","159100","520870"]:
        r=revised.get(s)
        if r:
            reason=[x for x in r["classification_reason"] if x in reasons_new]
            lines.append(f"| {s} | {r['index_name'] or '无官方跟踪指数'} | {'是' if not r['needs_review'] else '否'} | {','.join(reason) or '无'} |")
    lines.extend(["","## 尚未完成","",
        "- 不同指数可能存在持仓高度重叠；本轮没有做未经证实的跨指数合并。",
        "- 当前官方索引及基金资料 2026-11-12 才采集，不能覆盖其之前的历史效力。",
        "- 执行属性（币种、结算、溢价披露时点等）仍需单独核实；本轮不批准交易池。",
        "- LOF 非指数策略不得根据比较基准或拟合指数制造被动跟踪身份。",
        "- 保留 Draft PR，不修改生产数据库/OLS/站点。",
        "","## 典型更新（前 25 项）",""])
    for ch in changes[:25]:
        lines.append(f"- {ch['symbol']} {ch['name']}: {ch['old_exact']} → {ch['new_exact']}；分类 {'待审' if ch['old_needs_review'] else '通过'} → {'待审' if ch['new_needs_review'] else '通过'}")
    (args.output/"REPORT_V31.md").write_text("\n".join(lines)+"\n",encoding="utf8")
    print(json.dumps({"updated":len(changes),"approved":newsum["fully_classified_current"],
       "review":newsum["needs_review"],"bridge_pending":reasons_new.get("OFFICIAL_CODE_NAME_LINK_NOT_VERIFIED"),
       "approved_archive":newsum["dedup_comparison"]["approved_archive_symbols"],
       "diff":str(args.output/"REPORT_V31.md")},ensure_ascii=False))
if __name__=="__main__":
    main()
