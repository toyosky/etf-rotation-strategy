// Pre-registered Top1 ex-ante model reliability and 20% conservative shield audit.
// Node 18+, no dependencies. Inputs: original OOS CSV, PIT volatility snapshot, round1 calibrated predictions.
// node uncertainty_shield_audit.mjs <oos.csv> <uncertainty_features.json> <round1_results.json>
import fs from 'node:fs';
const uncertaintyShieldAudit=function uncertaintyShieldAudit(csv, snapshot, round1) {
 const lines=csv.trim().split("\n"),columns=lines.shift().split(",");
 const idx=Object.fromEntries(columns.map((k,i)=>[k,i]));
 const rows=lines.map((ln,t)=>{const a=ln.split(","),r={t};for(let j=0;j<columns.length;j++)r[columns[j]]=["d","s","fold"].includes(columns[j])?a[j]:a[j]===""?null:+a[j];return r;});
 const fmap=new Map(snapshot.features.map(x=>[x.d+"|"+x.s,x]));
 const oldDaily=new Map(round1.dailyPredictions.map(x=>[x.d,x]));
 const clamp=(x,l=0,h=1)=>Math.max(l,Math.min(h,x));
 const ln=Math.log, exp=Math.exp;
 for(const r of rows){
  r.y=Number(r.loss>=.05);
  r.hasRisk=Boolean(r.s);
  if(!r.hasRisk){r.U1=r.U2=r.U3=r.U=false;r.oldExit=0;r.residualFlag=false;continue;}
  const f=fmap.get(r.d+"|"+r.s);if(!f)throw Error("missing feature for "+r.d+" "+r.s);
  r.volRecorded=f.vol20;
  r.volHistoryN=f.n252;
  r.volPct=f.pct252;
  r.volAnalog=f.analog756;
  r.analogHistN=f.n756;
  r.U1=f.n252>=120&&f.pct252>=.95;
  r.U2=f.n756>=120&&f.analog756<15;
  r.U3=Math.abs(r.pLoss5_full-r.pLoss5_vol)>=.10;
  r.U=r.U1||r.U2;
  const S=ln(r.D/(1.1*r.Dbase)),pDelta=r.pLoss5_full-r.pLoss5_vol;
  r.oldExit=clamp((1-exp(-Math.max(S,0)))*clamp(1+2*pDelta,0,1.8));
  const prior=oldDaily.get(r.d);
  r.residualFlag=Boolean(prior&&prior.nRecent>=40&&prior.recentErr>=.05);
  r.residualMean=prior?.recentErr??null;
 }
 const risk=rows.filter(r=>r.hasRisk),years=[...new Set(rows.map(r=>r.d.slice(0,4)))],markers=["U1","U2","U3","U"];
 function fstat(ar){
  const n=ar.length;
  if(!n)return {n:0};
  const actual=ar.reduce((s,r)=>s+r.y,0)/n,forecast=ar.reduce((s,r)=>s+r.pLoss5_full,0)/n;
  const pVol=ar.reduce((s,r)=>s+r.pLoss5_vol,0)/n;
  const brier=ar.reduce((s,r)=>s+(r.y-r.pLoss5_full)**2,0)/n;
  return {n,eventN:ar.reduce((s,r)=>s+r.y,0),actual,forecast,gap:actual-forecast,brier,cover90:ar.reduce((s,r)=>s+(r.loss<=r.D),0)/n,
   volMean:ar.reduce((s,r)=>s+r.volRecorded,0)/n,volPercentile:ar.reduce((s,r)=>s+r.volPct,0)/n,
   meanMAE:ar.reduce((s,r)=>s+r.loss,0)/n};
 }
 function groupStats(ar){
  const all=fstat(ar),byFlag=Object.fromEntries(markers.map(k=>[k,{flagged:fstat(ar.filter(r=>r[k])),unflagged:fstat(ar.filter(r=>!r[k])),share:ar.length?ar.filter(r=>r[k]).length/ar.length:0}]));
  return {all,...byFlag};
 }
 const year=Object.fromEntries(years.map(y=>[y,groupStats(risk.filter(r=>r.d.startsWith(y)))]));
 const quarter=Object.fromEntries([...new Set(risk.map(r=>r.fold))].map(q=>[q,groupStats(risk.filter(r=>r.fold===q))]));
 const overall=groupStats(risk),test=groupStats(risk.filter(r=>r.d>="20220101"));
 const noOil2026=groupStats(risk.filter(r=>r.d.startsWith("2026")&&r.s!=="501018"));
 const oil2026=groupStats(risk.filter(r=>r.d.startsWith("2026")&&r.s==="501018"));
 const cumulative={};
 for(const m of markers){
  cumulative[m]={all:risk.filter(r=>r[m]).length,post2026:risk.filter(r=>r.d.startsWith("2026")&&r[m]).length,
   byTicker:Object.entries(risk.filter(r=>r[m]).reduce((a,r)=>(a[r.s]=(a[r.s]||0)+1,a),{})).sort((a,b)=>b[1]-a[1])};
 }
 const policyNames=["full","old","u1","u2","combined","residual","combinedNoOil"];
 function runPolicy(policy){
  let nav=1,peak=1,mdd=0,mddDate=null,prevSymbol=null,prevW=0,remaining=0,held=0;
  let starts=0,newStarts=0,shieldDays=0,cash=0,totalTrade=0,avoided=0,missed=0;
  const logs=[],weights=[],startEntries=[],byYear={},drawdownByYear={};
  for(const r of rows){
   let w=r.hasRisk?1:0,begin=false,withdraw=0,extra=false;
   if(remaining>0){
    if(r.hasRisk)w=1-held;
    remaining--;
   }else if(r.hasRisk&&policy!=="full"){
    const old=r.oldExit;
    const doShield=policy==="u1"?r.U1:policy==="u2"?r.U2:policy==="combined"?r.U:policy==="residual"?r.residualFlag:policy==="combinedNoOil"?r.U&&r.s!=="501018":false;
    withdraw=doShield?Math.max(old,.2):old;
    extra=doShield&&old<.2-1e-10;
    if(withdraw>1e-5){
     w=1-withdraw;held=withdraw;remaining=4;begin=true;
     starts++;if(extra)newStarts++;
     startEntries.push({d:r.d,s:r.s,withdraw,priorOld:old,extra,flags:[r.U1,r.U2,r.U3,r.residualFlag],futureMAE:r.loss,ret:r.ret});
    }else held=0;
   }
   if(!r.hasRisk)w=0;
   const turnover=r.s===prevSymbol?Math.abs(w-prevW):w+prevW;
   const cost=.0006*turnover;
   const f=1+w*r.ret-cost;if(!Number.isFinite(f)||f<=0)throw Error("bad pnl");
   const before=nav;nav*=f;peak=Math.max(peak,nav);
   const currDD=nav/peak-1;if(currDD<mdd){mdd=currDD;mddDate=r.d;}
   const y=r.d.slice(0,4);
   const yy=byYear[y]??(byYear[y]={startNav:before,endNav:nav,peakLocal:before,mddLocal:0,starts:0,newStarts:0,cashUnits:0,avoided:0,missed:0});
   yy.endNav=nav;yy.peakLocal=Math.max(yy.peakLocal,nav);yy.mddLocal=Math.min(yy.mddLocal,nav/yy.peakLocal-1);
   yy.starts+=begin;yy.newStarts+=begin&&extra;yy.cashUnits+=r.hasRisk?1-w:0;
   if(r.hasRisk&&w<1){
    yy.avoided+=(1-w)*Math.max(0,-r.ret);yy.missed+=(1-w)*Math.max(0,r.ret);
    avoided+=(1-w)*Math.max(0,-r.ret);missed+=(1-w)*Math.max(0,r.ret);
    cash+=1-w;shieldDays+=1;
   }
   if(begin&&extra) yy.newStarts+=0;
   totalTrade+=turnover;logs.push(Math.log(f));weights.push(w);prevW=w;prevSymbol=r.s;
  }
  const CAGR=nav**(244/rows.length)-1;
  return {CAGR,mdd,mddDate,calmar:CAGR/(-mdd),totalReturn:nav-1,starts,newStarts,shieldDays,cashUnits:cash,cashPctRiskDays:cash/risk.length,totalTrade,
   avoided,missed,netExAntePriceGainProxy:avoided-missed,
   byYear:Object.fromEntries(Object.entries(byYear).map(([k,v])=>[k,{annualReturn:v.endNav/v.startNav-1,localMDD:v.mddLocal,starts:v.starts,newStarts:v.newStarts,cashUnits:v.cashUnits,avoided:v.avoided,missed:v.missed}])),
   entries:startEntries.slice(-18),logs,weights};
 }
 const perf=Object.fromEntries(policyNames.map(p=>[p,runPolicy(p)]));
 const contrasts=["u1","u2","combined","residual","combinedNoOil"];
 const dateIds=Object.fromEntries(years.map(y=>[y,rows.map((r,i)=>r.d.startsWith(y)?i:-1).filter(i=>i>=0)]));
 function bootstrapPolicies(block,reps){
  const result=Object.fromEntries(contrasts.map(p=>[p,[]]));
  let seed=0x20261121+block;
  function rand(){seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return (seed>>>0)/4294967296;}
  for(let z=0;z<reps;z++){
   let sums=Object.fromEntries(contrasts.map(x=>[x,0]));
   for(const y of years){
    const a=dateIds[y];let n=0;
    while(n<a.length){
     const first=Math.floor(rand()*a.length);
     for(let j=0;j<block&&n<a.length;j++,n++){
      const ind=a[(first+j)%a.length];
      for(const p of contrasts)sums[p]+=perf[p].logs[ind]-perf.old.logs[ind];
     }
    }
   }
   for(const p of contrasts)result[p].push(sums[p]/rows.length*244);
  }
  const q=(a,p)=>{const b=a.slice().sort((u,v)=>u-v),x=(b.length-1)*p,i=Math.floor(x);return b[i]+(b[Math.min(i+1,b.length-1)]-b[i])*(x-i)};
  return {block,reps,
   annualizedPairedLogExcess:Object.fromEntries(contrasts.map(p=>[p,{
    point:perf[p].logs.reduce((s,x,i)=>s+(x-perf.old.logs[i]),0)/rows.length*244,
    ci95:[q(result[p],.025),q(result[p],.975)],positiveShare:result[p].filter(x=>x>0).length/reps
   }]))};
 }
 const boot20=bootstrapPolicies(20,1600),boot10=bootstrapPolicies(10,800),boot40=bootstrapPolicies(40,800);
 function bootUncertainty(block,reps){
  let seed=0x44009100+block;function rand(){seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return (seed>>>0)/4294967296;}
  const from2022=risk.filter(r=>r.d>="20220101");
  const yearGroups=Object.fromEntries(["2022","2023","2024","2025","2026"].map(y=>[y,from2022.filter(r=>r.d.startsWith(y))]));
  const names=["U1","U2","U3","U"],samples=Object.fromEntries(names.map(k=>[k,[]]));
  for(let b=0;b<reps;b++){
   const select=[];
   for(const yy of Object.values(yearGroups)){
    let n=0;
    while(n<yy.length){const st=Math.floor(rand()*yy.length);for(let j=0;j<block&&n<yy.length;j++,n++)select.push(yy[(st+j)%yy.length]);}
   }
   for(const k of names){
    const hits=select.filter(r=>r[k]),base=select.filter(r=>!r[k]);
    if(!hits.length||!base.length)continue;
    const gap=x=>x.reduce((s,r)=>s+(r.y-r.pLoss5_full),0)/x.length;
    const brier=x=>x.reduce((s,r)=>s+(r.y-r.pLoss5_full)**2,0)/x.length;
    samples[k].push({gap:gap(hits)-gap(base),brier:brier(hits)-brier(base)});
   }
  }
  const q=(arr,p)=>{if(!arr.length)return null;const v=arr.slice().sort((a,b)=>a-b),x=(v.length-1)*p,i=Math.floor(x);return v[i]+(v[Math.min(i+1,v.length-1)]-v[i])*(x-i);};
  const answer={block,reps,byFlag:{}};
  for(const k of names){
   const v=samples[k],a=v.map(x=>x.gap),b=v.map(x=>x.brier);
   answer.byFlag[k]={valid:v.length,gapDiffCI95:[q(a,.025),q(a,.975)],brierDiffCI95:[q(b,.025),q(b,.975)]};
  }
  return answer;
 }
 const unc20=bootUncertainty(20,1600),unc10=bootUncertainty(10,800),unc40=bootUncertainty(40,800);
 const byOffset=[];
 for(let off=0;off<5;off++){
  const rs=risk.filter(r=>r.t%5===off);
  const rr=rs.filter(r=>r.d.startsWith("2026"));
  byOffset.push({off,all:groupStats(rs),y2026:groupStats(rr)});
 }
 const compactPolicy=o=>{const {logs,weights,...x}=o;return x;};
 return {meta:{nSignals:rows.length,nRisk:risk.length,from:rows[0].d,to:rows.at(-1).d,feePerSide:.0006,holdDays:5,confidenceIndicators:["U1 vol20 percentile>=95% in last252 after 120 history","U2 fewer than15 +/-0.3pp analog days in prior756 with >=120 history","U3 original P5 vs vol-only >=10pp difference"],riskShield:"minimum 20% withdrawn when warning fires, fixed 5 trading days, original Q90-gate+P sizing otherwise",noLiveChange:true},firstStage:{overall,test2022plus:test,year,quarter,noOil2026,oil2026,countByTicker:cumulative},
  policy:Object.fromEntries(Object.entries(perf).map(([k,v])=>[k,compactPolicy(v)])),
  block20:boot20,block10:boot10,block40:boot40,uncertainty20:unc20,uncertainty10:unc10,uncertainty40:unc40,offsets:byOffset,
  daily:rows.map(r=>({d:r.d,s:r.s,volPct:r.volPct??null,volAnalog:r.volAnalog??null,U1:r.U1,U2:r.U2,U3:r.U3,U:r.U,
   residualFlag:r.residualFlag,loss:r.loss,ret:r.ret,p:r.pLoss5_full,oldExit:r.oldExit,
   exposureOld:perf.old.weights[r.t],exposureU1:perf.u1.weights[r.t],exposureU2:perf.u2.weights[r.t],
   exposureCombined:perf.combined.weights[r.t],exposureResidual:perf.residual.weights[r.t]}))
 };
};
if(process.argv.length<5)throw Error("requires oos.csv uncertaintyFeatures.json round1.json");
console.log(JSON.stringify(uncertaintyShieldAudit(fs.readFileSync(process.argv[2],"utf8"),JSON.parse(fs.readFileSync(process.argv[3],"utf8")),JSON.parse(fs.readFileSync(process.argv[4],"utf8"))),null,2));
