# W research ledger
W1/W2 first rounds completed in conversation; W3.1 conditional groups completed; W3a conditional incremental opportunity audit completed this run. W4-W6 pending. W1 historical downside/MAE and P-All pending. Premium10 PIT/minute execution not established; no production changes.
## W3a
Sources: prediction blob 3a93afe73e85448650ce0cd9f8c20ebe4b2bf304; baseline blob d373130b1ae56d6a3f60b22a7182c9ccfb5016d2. Join date and target, NON_VOID, risk set 159934,159985,161226,513100,159957,159509,513290,159529,159981,501018,513530,164824,511380,512800. 960 rows, warmup 60. Past 252 eligible observations, midrank ties. Stratify by score, vol, D/Dbase rank >=0.5 (8 cells). Compare pMfe5_full rank >=0.5 and separately full minus vol-only probability rank >=0. Within cell difference high minus low, require >=5 each, weight by smaller group size. No fitted parameters or future labels in grouping. Descriptive, not causal or independent OOS; overlapping labels. Results decimal returns:
```json
[
  {
    "scope": "all",
    "raw": {
      "n": 900,
      "matchedPerSide": 178,
      "cells": 5,
      "ret": 0.002046021397463264,
      "end": 0.005288519296597995,
      "mfe": 0.024015629729961283,
      "loss": 0.009973303931674726
    },
    "increment": {
      "n": 900,
      "matchedPerSide": 219,
      "cells": 6,
      "ret": -0.0005852196317700245,
      "end": -0.0038177056512239,
      "mfe": 0.00030104392061384094,
      "loss": 0.0036140763762986675
    }
  },
  {
    "scope": "ex26",
    "raw": {
      "n": 759,
      "matchedPerSide": 150,
      "cells": 5,
      "ret": 0.0013321025380126149,
      "end": 0.0008688590582298474,
      "mfe": 0.01465767810189978,
      "loss": 0.006349294074681905
    },
    "increment": {
      "n": 759,
      "matchedPerSide": 190,
      "cells": 6,
      "ret": -0.0020239701781267997,
      "end": -0.0005410933667090522,
      "mfe": 0.0021390215921713233,
      "loss": 0.004790637827377977
    }
  },
  {
    "scope": "exOilSilver",
    "raw": {
      "n": 712,
      "matchedPerSide": 140,
      "cells": 5,
      "ret": 0.0012836326417360678,
      "end": 0.0011604658621773686,
      "mfe": 0.01705753351511731,
      "loss": 0.006957143869269117
    },
    "increment": {
      "n": 712,
      "matchedPerSide": 190,
      "cells": 6,
      "ret": -0.0016529476349331352,
      "end": -0.0007982496338976154,
      "mfe": 0.0022405646217048413,
      "loss": 0.0037043485536120335
    }
  }
]
```
Next: W3a daily portfolio replay and block bootstrap; compare A/C and opportunity rank; avoid treating MFE as realized. P-All unavailable in this run.
## W3b
Completed daily open-proxy replay, 5pp band, 6/10bp, 1419 days, frozen routing, past-only 252 ranks, no future labels. F replaces Score rank with full opportunity rank, V with vol-only rank, I adds 0.25*(full rank-vol rank) to C. Fixed and C exposure matches and fixed volatility matches are ex-post attribution. See w3b_replay.mjs and w3b_results.json. Bootstrap 20-day circular blocks within years, 1200 replicates. Exclusions are attribution not rerouted backtests. Premium10 PIT, P-All and lot/minimum commission still pending. Next W4 unless W3b shows robust incremental evidence. No production change.

## W4a
W3b archived: F/V/I all lower CAGR than exposure-matched C at both fees; close opportunity branch for now. W4a executed center vs edge no-trade bands 0/5/10pp for A/C, 6/10bp, matched center/fixed exposure and fixed volatility, 20-day paired bootstrap. See w4a_execution.mjs and w4a_results.json. Continuous shares/open proxy, no minimum commission or lot sizes; Void routing unchanged. Next W4b audit asymmetric execution and minimum commission/lot data availability; do not optimize prediction. Premium10 PIT and P-All pending.

## W6b.1 — exit-rate control (2026-11-27)
W4b/W5a/W5b/W6a reported in conversation, not yet independently archived. This run: matched consecutive same-target NON_VOID days, full five-day calendar availability, compare target decline >5pp versus all other eligible days; first future Void/switch/mismatch, return through exit or five intervals. Weak = betaDelta3<0 and r2Delta3<0, exploratory only. No future state used for trading. Sources d373130b1ae56d6a3f60b22a7182c9ccfb5016d2 / 3a93afe73e85448650ce0cd9f8c20ebe4b2bf304. Historical open proxy, Premium10 PIT and P-All unresolved. Results:
```json
{
  "n": 748,
  "out": [
    {
      "scope": "all",
      "model": "A",
      "group": "cut",
      "n": 108,
      "hold": 32,
      "switch": 62,
      "void": 13,
      "missing": 1,
      "mean": 0.005285106219633306
    },
    {
      "scope": "all",
      "model": "A",
      "group": "other",
      "n": 640,
      "hold": 222,
      "switch": 257,
      "void": 155,
      "missing": 6,
      "mean": 0.01232570450209284
    },
    {
      "scope": "all",
      "model": "A",
      "group": "cutWeak",
      "n": 2,
      "hold": 0,
      "switch": 2,
      "void": 0,
      "missing": 0,
      "mean": -0.003246753248451806
    },
    {
      "scope": "all",
      "model": "A",
      "group": "cutNotWeak",
      "n": 106,
      "hold": 32,
      "switch": 60,
      "void": 13,
      "missing": 1,
      "mean": 0.005446084700163213
    },
    {
      "scope": "all",
      "model": "C",
      "group": "cut",
      "n": 105,
      "hold": 28,
      "switch": 52,
      "void": 24,
      "missing": 1,
      "mean": 0.007673667010352949
    },
    {
      "scope": "all",
      "model": "C",
      "group": "other",
      "n": 643,
      "hold": 226,
      "switch": 267,
      "void": 144,
      "missing": 6,
      "mean": 0.011902810757344876
    },
    {
      "scope": "all",
      "model": "C",
      "group": "cutWeak",
      "n": 33,
      "hold": 5,
      "switch": 17,
      "void": 11,
      "missing": 0,
      "mean": 0.000962644679665212
    },
    {
      "scope": "all",
      "model": "C",
      "group": "cutNotWeak",
      "n": 72,
      "hold": 23,
      "switch": 35,
      "void": 13,
      "missing": 1,
      "mean": 0.010749552245251495
    },
    {
      "scope": "ex26",
      "model": "A",
      "group": "cut",
      "n": 89,
      "hold": 30,
      "switch": 47,
      "void": 11,
      "missing": 1,
      "mean": 0.008219794522063012
    },
    {
      "scope": "ex26",
      "model": "A",
      "group": "other",
      "n": 561,
      "hold": 201,
      "switch": 215,
      "void": 139,
      "missing": 6,
      "mean": 0.008817426312392612
    },
    {
      "scope": "ex26",
      "model": "A",
      "group": "cutWeak",
      "n": 2,
      "hold": 0,
      "switch": 2,
      "void": 0,
      "missing": 0,
      "mean": -0.003246753248451806
    },
    {
      "scope": "ex26",
      "model": "A",
      "group": "cutNotWeak",
      "n": 87,
      "hold": 30,
      "switch": 45,
      "void": 11,
      "missing": 1,
      "mean": 0.008483393321385192
    },
    {
      "scope": "ex26",
      "model": "C",
      "group": "cut",
      "n": 95,
      "hold": 27,
      "switch": 45,
      "void": 22,
      "missing": 1,
      "mean": 0.007491446230533465
    },
    {
      "scope": "ex26",
      "model": "C",
      "group": "other",
      "n": 555,
      "hold": 204,
      "switch": 217,
      "void": 128,
      "missing": 6,
      "mean": 0.008948559426694033
    },
    {
      "scope": "ex26",
      "model": "C",
      "group": "cutWeak",
      "n": 32,
      "hold": 5,
      "switch": 16,
      "void": 11,
      "missing": 0,
      "mean": 0.00029828288224067676
    },
    {
      "scope": "ex26",
      "model": "C",
      "group": "cutNotWeak",
      "n": 63,
      "hold": 22,
      "switch": 29,
      "void": 11,
      "missing": 1,
      "mean": 0.011145116502682182
    },
    {
      "scope": "exOilSilver",
      "model": "A",
      "group": "cut",
      "n": 77,
      "hold": 23,
      "switch": 45,
      "void": 8,
      "missing": 1,
      "mean": -0.006576551957844097
    },
    {
      "scope": "exOilSilver",
      "model": "A",
      "group": "other",
      "n": 506,
      "hold": 189,
      "switch": 208,
      "void": 105,
      "missing": 4,
      "mean": 0.00806162761857783
    },
    {
      "scope": "exOilSilver",
      "model": "A",
      "group": "cutWeak",
      "n": 2,
      "hold": 0,
      "switch": 2,
      "void": 0,
      "missing": 0,
      "mean": -0.003246753248451806
    },
    {
      "scope": "exOilSilver",
      "model": "A",
      "group": "cutNotWeak",
      "n": 75,
      "hold": 23,
      "switch": 43,
      "void": 8,
      "missing": 1,
      "mean": -0.006665346590094558
    },
    {
      "scope": "exOilSilver",
      "model": "C",
      "group": "cut",
      "n": 80,
      "hold": 22,
      "switch": 40,
      "void": 17,
      "missing": 1,
      "mean": 0.0023169218063229025
    },
    {
      "scope": "exOilSilver",
      "model": "C",
      "group": "other",
      "n": 503,
      "hold": 190,
      "switch": 213,
      "void": 96,
      "missing": 4,
      "mean": 0.006734463876223776
    },
    {
      "scope": "exOilSilver",
      "model": "C",
      "group": "cutWeak",
      "n": 27,
      "hold": 5,
      "switch": 15,
      "void": 7,
      "missing": 0,
      "mean": 0.00046954280462157074
    },
    {
      "scope": "exOilSilver",
      "model": "C",
      "group": "cutNotWeak",
      "n": 53,
      "hold": 17,
      "switch": 25,
      "void": 10,
      "missing": 1,
      "mean": 0.0032580394109632035
    }
  ]
}
```
Reproduction function:
```js
function study(bs,qs){const parse=s=>{const [h,...a]=s.trim().split(/\r?\n/),k=h.split(",");return a.map(t=>Object.fromEntries(t.split(",").map((v,i)=>[k[i],v])))},qm=new Map(parse(qs).map(x=>[x.d,x])),risk=new Set("159934 159985 161226 513100 159957 159509 513290 159529 159981 501018 513530 164824 511380 512800".split(" ")),clip=x=>Math.max(0,Math.min(1,x)),rank=(a,x)=>(a.filter(v=>v<x).length+.5*a.filter(v=>v===x).length)/a.length;
const ds=parse(bs).filter(x=>qm.has(x.date.replace(/-/g,""))).map(x=>{const z=qm.get(x.date.replace(/-/g,""));return {...x,matched:x.state==="NON_VOID"&&risk.has(x.target)&&x.target===z.s,r:+z.D/+z.Dbase,score:+x.score,ret:x.missing==="1"&&x.target===z.s?+z.ret:+x.gross}});let h=[];for(const d of ds){if(!d.matched)continue;const p=h.slice(-252);d.A=clip(.9/Math.max(1,d.r));d.C=clip(.8+.5*(p.length<60?0:rank(p.map(x=>x.score),d.score)-rank(p.map(x=>x.r),d.r)));h.push(d);}
const rows=[];for(let i=1;i<ds.length-5;i++){const d=ds[i],p=ds[i-1];if(!d.matched||!p.matched||d.target!==p.target)continue;let type="hold",j=1;for(;j<=5;j++){const n=ds[i+j];if(n.state==="DEFENSIVE_VOID"){type="void";break}if(n.target!==d.target){type="switch";break}if(!n.matched){type="missing";break}}let ret=1;for(let k=0;k<Math.min(j,5);k++)ret*=1+ds[i+k].ret;rows.push({year:d.date.slice(0,4),asset:d.target,type,ret:ret-1,A:p.A-d.A>.05,C:p.C-d.C>.05,weak:+d.betaDelta3<0&&+d.r2Delta3<0});}
const out=[];for(const scope of ["all","ex26","exOilSilver"])for(const model of ["A","C"])for(const group of ["cut","other","cutWeak","cutNotWeak"]){const a=rows.filter(x=>(scope!=="ex26"||x.year!=="2026")&&(scope!=="exOilSilver"||!["161226","501018"].includes(x.asset))&&(group==="other"?!x[model]:x[model]&&(group==="cut"||x.weak===(group==="cutWeak"))));out.push({scope,model,group,n:a.length,hold:a.filter(x=>x.type==="hold").length,switch:a.filter(x=>x.type==="switch").length,void:a.filter(x=>x.type==="void").length,missing:a.filter(x=>x.type==="missing").length,mean:a.reduce((s,x)=>s+x.ret,0)/a.length});}return {n:rows.length,out};}
```
Next: full replay of predeclared weak-trend confirmation gate vs W5b, matched exposure/volatility and bootstrap; no production changes.

## 2026-11-28 — archival reconciliation and current research cursor
Supersedes the outdated pending-status statements above, but does not replace original evidence.
- [W_RESEARCH_BACKFILL_20261128.md](W_RESEARCH_BACKFILL_20261128.md): recovered W1/W2, W4b/W5a/W5b/W6a, W7a and W8d.1/1b numerical summaries, provenance, limits, candidate rules, and current queue. Historical summaries are NOT independently re-run; full original scripts/results remain to be recovered where noted.
- [w8a_early_history_quality.sql](w8a_early_history_quality.sql) and [w8a_early_history_quality_20261128.csv](w8a_early_history_quality_20261128.csv): archived actual query and transcribed results of completed 2026-11-28 13:06 UTC read-only run. 10,284 rows, 11 symbols, zero reported duplicate dates/invalid OHLC; 511220 six internal calendar gaps and 164824 one. Date-union calendar is not official. Adjustment, dividends, suspension, listing, turnover, PIT premium and preheat validation remain pending.
- W1–W6 first round reported complete (some results summary-only), W7a exact Q10 reproduction reported complete, W8d.1 fixed control reported complete. W7b and W8d.2 dynamic replay remain blocked/incomplete; W7c/d, W8b, W8c (partial), W8e/f/g and remaining W8a items pending. P-All and PIT Premium10 not established.
- Next: finish W7b/W8d.2 with original frozen models and common daily paths; if blocked, advance W8b/e or remaining W8a independently and return. Do not repeat fixed controls or structural audit without a specific discrepancy. Freeze model rules and evaluation before new sample results; 2013–14 warmup, 2015–20 historical backward validation, 2021–25 original sample, 2026 separate stress only. No re-optimization or production changes. Maintain exact evidence links and statuses after each completed run.
- End condition: W7b/c/d, W8a–g and material branches completed or explicitly non-verifiable; final report and task stop only then.


## W8a PIT premium audit — 2026-11-28
See [w8a_premium_pit_20261128.md](w8a_premium_pit_20261128.md). Actual read-only query: 35,744 backfilled rows, zero PIT-safe; all 28,999 pre-2026 rows lack first_seen_at. Exact Premium10 unavailable from this table alone; continue daily proxy with explicit caveat. W7b/W8d.2 remain pending, no dynamic replay this run. Advance W8e/W8b independently if original specifications unavailable; do not repeat PIT count absent new data.
