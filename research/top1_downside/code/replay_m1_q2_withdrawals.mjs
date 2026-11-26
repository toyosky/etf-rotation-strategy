// Reproduce research-proxy 2026Q2 withdrawals using archived M1 probabilities.
// Usage:
// node research/top1_downside/code/replay_m1_q2_withdrawals.mjs \
//   research/top1_downside/audit/20261120_prob_opportunity_oos_predictions.csv \
//   research/top1_downside/audit/20261120_market_state_calibration_round1_results.json
// No Supabase/network calls. No production changes.
import fs from 'node:fs';

const [csvPath,calPath]=process.argv.slice(2);
if(!csvPath||!calPath)throw Error('Need OOS probability CSV and M1 results JSON');
const [header,...records]=fs.readFileSync(csvPath,'utf8').trim().split('\n');
const keys=header.split(',');
const rows=records.map(line=>{
 const cells=line.split(','),r={};
 keys.forEach((k,i)=>r[k]=['d','s','fold'].includes(k)?cells[i]:cells[i]===''?null:+cells[i]);
 return r;
}).sort((a,b)=>a.d.localeCompare(b.d));
const cal=JSON.parse(fs.readFileSync(calPath,'utf8'));
const byDate=new Map(cal.dailyPredictions.map(r=>[r.d,r]));
const clip=(v,min=0,max=1)=>Math.max(min,Math.min(max,v));
let verified=0;
for(const r of rows){
 const c=byDate.get(r.d);
 if(c){
  if(c.s!==r.s||Math.abs(c.p0-r.pLoss5_full)>1e-12)throw Error('M1 input mismatch at '+r.d);
  if(Math.abs(c.p1-clip(c.p0+clip(.65*c.recentErr,-.12,.12),.005,.995))>1e-12)throw Error('M1 formula mismatch '+r.d);
  verified++;
 }
 r.pm1=c?c.p1:r.pLoss5_full; // 2021 M1 warmup: comparator fallback only
 r.recentErr=c?.recentErr??null;
}
if(verified!==1147)throw Error('Unexpected matched test sample '+verified);
function weight(r,mode){
 if(!r.s||mode==='full')return 0;
 const eQ=clip(1-1.10*r.Dbase/r.D);
 if(mode==='q90')return eQ;
 const p=mode==='m1'?r.pm1:r.pLoss5_full;
 return clip(eQ*clip(1+2*(p-r.pLoss5_vol),0,1.8));
}
function simulate(mode){
 let nav=1,prevSymbol=null,prevW=0,remain=0,heldE=0;
 const days=[],events=[];
 for(let i=0;i<rows.length;i++){
  const r=rows[i];let w=r.s?1:0,action='no-new-exit';
  if(remain>0){
   if(r.s)w=1-heldE;
   remain--;action='5-session-locked';
  }else if(r.s&&mode!=='full'){
   const E=weight(r,mode);
   if(E>1e-4){
    action='start';w=1-E;heldE=E;remain=4;
    const prevEventWeight=prevSymbol===r.s?prevW:null;
    events.push({
     signal:r.d,execution:rows[i+1]?.d??null,baselineRestore:rows[i+6]?.d??null,symbol:r.s,
     previousSameSymbolWeight:prevEventWeight,physicalWeightChange:prevEventWeight===null?null:w-prevEventWeight,
     E,E_Q90:weight(r,'q90'),E_raw:weight(r,'raw'),targetRiskWeight:w,
     p0:r.pLoss5_full,pM1:r.pm1,pVol:r.pLoss5_vol,maturedResidual:r.recentErr,
     Q90:r.D,normal:r.Dbase,actualL5:r.loss,assetR5:r.endReturn
    });
   }else heldE=0;
  }
  const turnover=prevSymbol===r.s?Math.abs(prevW-w):prevW+w;
  const fee=turnover*.0006;
  const before=nav;
  nav*=(1+w*r.ret-fee);
  days.push({signal:r.d,symbol:r.s,w,action,fee,nav,prevNav:before,
   eCandidate:weight(r,mode),eQ:weight(r,'q90')});
  prevW=w;prevSymbol=r.s;
 }
 return {days,events};
}
const variants=Object.fromEntries(['full','q90','raw','m1'].map(mode=>[mode,simulate(mode)]));
const quarter=(r)=>r.signal>='20260401'&&r.signal<='20260630';
const performance=Object.fromEntries(Object.entries(variants).map(([name,o])=>{
 const ds=o.days.filter(quarter),init=ds[0].prevNav;
 let peak=init,mdd=0;
 for(const row of ds){peak=Math.max(peak,row.nav);mdd=Math.min(mdd,row.nav/peak-1);}
 const held=ds.filter(x=>x.symbol);
 const ev=o.events.filter(quarter);
 return [name,{days:ds.length,riskDays:held.length,eventCount:ev.length,
   netReturn:ds.at(-1).nav/init-1,maxDrawdown:mdd,
   averageExit:ev.length?ev.reduce((s,x)=>s+x.E,0)/ev.length:0,
   activeReducedDays:held.filter(x=>x.w<1-1e-5).length,
   meanRiskWeight:held.reduce((s,x)=>s+x.w,0)/held.length}];
}));
const events=variants.m1.events.filter(quarter);
const candidates=variants.m1.days.filter(d=>quarter(d)&&d.symbol&&d.eCandidate>1e-4);
const riskDays=rows.filter(r=>quarter({signal:r.d})&&r.s);
const actualHits=riskDays.filter(r=>r.loss>=.05);
const missedGate=actualHits.filter(r=>weight(r,'m1')<=1e-4);
const result={
 provenance:{type:'research-proxy only, not formal V1/Void/Q10 or actual 09:31/14:05 execution',inputDates:'2021-01-04 to 2026-11-12',testQuarter:'2026Q2',verifiedM1Rows:verified,
  frozenRule:'E=clip(E_Q * clip(1+2*(P_M1-P_vol),0,1.8),0,1); E_Q=clip(1-1.10*Dnormal/D90,0,1); 5-session locked cash; 6bp per side'},
 performance,events,
 diagnostic:{testRiskDays:riskDays.length,actualOver5PercentCount:actualHits.length,
 potentialPositiveSignals:candidates.length,suppressedByLock:candidates.filter(x=>x.action==='5-session-locked').length,
 actualOver5WithZeroSignal:missedGate.map(x=>({date:x.d,symbol:x.s,L5:x.loss,Q90:x.D,Dnormal:x.Dbase,P_M1:x.pm1})),
 potentialSuppressed:candidates.filter(x=>x.action==='5-session-locked').map(x=>({date:x.signal,symbol:x.symbol,potentialExit:x.eCandidate,currentRiskWeight:x.w,assetL5:rows.find(r=>r.d===x.signal)?.loss}))}
};
process.stdout.write(JSON.stringify(result,null,2)+'\n');
