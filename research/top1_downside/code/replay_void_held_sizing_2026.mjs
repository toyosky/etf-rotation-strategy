/**
 * 2026 Apr-Nov Void-frozen ETF sizing: 5 paired daily-open proxy policies.
 * Pure Node.js 18+, only archived inputs, no network, no live trades.
 *
 * node research/top1_downside/code/replay_void_held_sizing_2026.mjs \
 *   research/top1_downside/audit/20261122_void_2025_26_ohlc_part0.json \
 *   research/top1_downside/audit/20261122_void_2025_26_ohlc_part1.json \
 *   research/top1_downside/audit/20261120_prob_opportunity_oos_predictions.csv \
 *   research/top1_downside/audit/20261120_market_state_calibration_round1_results.json \
 *   data/state-map-history.json
 *
 * Important: risk proxy in Void is NOT original quarterly unified Q90:
 * normalize 120 mature actual-ETF L5 historical samples by their contemporary
 * vol20 and rescale by current vol20. Dbase=unscaled mature L5 q90,
 * Dproxy=quantile(L5/vol20,.90)*vol20_now, E=max(0,1-1.10 Dbase/Dproxy).
 * Historical information cutoff t-10 exchange sessions, no future leakage.
 * Original M1 (lambda=.65) is used ONLY outside Void, for archived raw Top1.
 */
import fs from 'node:fs';
const inputs=process.argv.slice(2);
if(inputs.length!==5)throw Error('Expected two OHLC, raw OOS csv, M1 result, State Map');
const [p0,p1,rawCsv,m1Raw,stateRaw]=inputs.map((p,i)=>i===2?fs.readFileSync(p,'utf8'):JSON.parse(fs.readFileSync(p,'utf8')));
const barArray=[...p0.rows,...p1.rows],by={};
for(const r of barArray)(by[r.symbol]??=[]).push(r);
const idx=Object.fromEntries(Object.entries(by).map(([s,a])=>[s,new Map(a.map((r,i)=>[r.date,i]))]));
const cols=rawCsv.trim().split('\n'),header=cols.shift().split(',');
const all=cols.map(line=>{const v=line.split(','),r={};header.forEach((k,i)=>r[k]=['d','s','fold'].includes(k)?v[i]:v[i]===''?null:+v[i]);return r;});
const rows=all.filter(r=>r.d>='20260401'&&r.d<='20261112');
const m1=new Map(m1Raw.dailyPredictions.map(x=>[x.d,x]));
const states=new Map(stateRaw.map(x=>[x.date.replaceAll('-',''),x]));
const sessions=by['511220'].map(x=>x.date);
const date=d=>d.slice(0,4)+'-'+d.slice(4,6)+'-'+d.slice(6,8);
const clamp=(x,l=0,h=1)=>Math.max(l,Math.min(h,x));
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
const quant=(a,p)=>a.slice().sort((x,y)=>x-y)[Math.ceil(a.length*p)-1];
const open=(s,d)=>{if(!s)return null;const i=idx[s]?.get(d);if(i==null)throw Error('Price missing '+s+' '+d);return by[s][i].open;};
const riskCache=new Map();
function vol20(a,i){const ret=[];for(let j=i-19;j<=i;j++)ret.push(Math.log(a[j].close/a[j-1].close));const m=mean(ret);return Math.sqrt(ret.reduce((s,x)=>s+(x-m)**2,0)/19);}
function heldRisk(sym,d){
 const key=sym+'|'+d;if(riskCache.has(key))return riskCache.get(key);
 const a=by[sym],i=idx[sym]?.get(d);if(i==null||i<150||i+5>=a.length)throw Error('Insufficient own OHLC '+key);
 const matured=[];for(let j=i-129;j<=i-10;j++){const five=a.slice(j+1,j+6);matured.push({loss:Math.max(0,1-Math.min(...five.map(x=>x.low))/five[0].open),v:vol20(a,j)});}
 const base=quant(matured.map(x=>x.loss),.9);
 const predicted=quant(matured.map(x=>x.loss/x.v),.9)*vol20(a,i);
 const out={base,predicted,E:clamp(1-1.1*base/predicted)};riskCache.set(key,out);return out;
}
function score(s,d){
 if(!s)return null;const a=by[s],i=idx[s]?.get(d);if(i==null||i<25)return null;
 const p=a.slice(i-25,i+1).map((r,j)=>({t:j,y:Math.log(r.close),w:Math.pow(.5,2*(25-j)/10)})),sw=p.reduce((s,x)=>s+x.w,0);
 const mx=p.reduce((s,x)=>s+x.w*x.t,0)/sw,my=p.reduce((s,x)=>s+x.w*x.y,0)/sw;
 const beta=p.reduce((s,x)=>s+x.w*(x.t-mx)*(x.y-my),0)/p.reduce((s,x)=>s+x.w*(x.t-mx)**2,0);
 const alpha=my-beta*mx,ss=p.reduce((s,x)=>s+x.w*(x.y-alpha-beta*x.t)**2,0),tot=p.reduce((s,x)=>s+x.w*(x.y-my)**2,0);
 return Math.max(0,Math.expm1(beta*250)*(tot?clamp(1-ss/tot):0));
}
function origE(r){
 if(!r.s)return 0;const c=m1.get(r.d);
 if(!c||c.s!==r.s||Math.abs(c.p0-r.pLoss5_full)>1e-10)throw Error('M1 alignment '+r.d);
 const eq=clamp(1-1.1*r.Dbase/r.D);
 return clamp(eq*clamp(1+2*(c.p1-r.pLoss5_vol),0,1.8)); // do not clamp multiplier at 1!
}
function simulate(mode){
 let cash=1,shares=0,held=null,episode=null,route=null;
 const ledger=[];
 for(const r of rows){
  const d=date(r.d),ix=sessions.indexOf(d),exec=sessions[ix+1],next=sessions[ix+2],st=states.get(r.d);
  if(!st||!exec||!next)throw Error('Missing state/clock '+r.d);
  const prior=held,nav0=cash+(held?shares*open(held,exec):0);
  const beforeW=held?shares*open(held,exec)/nav0:0;
  let target=null,w=0,event='NORMAL',forecast=null,deepen=null,valid=null;
  if(st.quadrant!=='DEFENSIVE_VOID'){episode=null;route=null;target=r.s||null;w=target?1-origE(r):0;}
  else {
   if(!episode){episode={held,entryB:st.breadth_pct,entryG:st.gap_percentile};route=null;target=held;event='VOID_ENTER';}
   else if(route){target=route;event='VOID_HOLD_ROUTE';}
   else {
    deepen=st.breadth_pct<episode.entryB&&st.gap_percentile<episode.entryG;
    const debt=score('511220',d),inc=score(episode.held,d);
    valid=episode.held!=null&&inc!=null&&debt!=null&&inc>debt;
    if(deepen&&!valid){const carrier=score('513500',d);route=carrier!=null&&debt!=null&&carrier>debt?'513500':'511220';target=route;event='VOID_ROUTE';}
    else{target=episode.held;event='VOID_HOLD';}
   }
   w=target===held?beforeW:target?1:0;
   // A Void route always outranks sizing; only original frozen ETF can be cut.
   if(target&&target===held&&!['513500','511220'].includes(target)&&mode!=='freeze'){
    forecast=heldRisk(target,d);
    if(mode==='downOnly')w=Math.min(beforeW,1-forecast.E);
    else if(mode==='twoWay')w=1-forecast.E;
    else if(mode==='fixed20'&&event==='VOID_ENTER')w=.8*beforeW;
    else if(mode==='fixed50'&&event==='VOID_ENTER')w=.5*beforeW;
   }
  }
  const oldVal=held?shares*open(held,exec):0;
  const invested=target?nav0*w:0,turn=target===held?Math.abs(invested-oldVal):invested+oldVal,fee=.0006*turn;
  cash=(nav0-fee)*(1-w);shares=target?(nav0-fee)*w/open(target,exec):0;held=target;
  const nav=cash+(held?shares*open(held,next):0);
  ledger.push({d:r.d,exec,asset:held,event,void:st.quadrant==='DEFENSIVE_VOID',
   prevAsset:prior,oldW:beforeW,w,turn,fee,ret:nav/nav0-1,nav,forecast,valid,deepen});
 }
 let peak=1,mdd=0;for(const r of ledger){peak=Math.max(peak,r.nav);mdd=Math.min(mdd,r.nav/peak-1);}
 return {summary:{n:ledger.length,net:ledger.at(-1).nav-1,mdd,
  voidDays:ledger.filter(x=>x.void).length,
  voidCuts:ledger.filter(x=>x.void&&x.asset===x.prevAsset&&x.w<x.oldW-1e-6).length,
  voidBuys:ledger.filter(x=>x.void&&x.asset===x.prevAsset&&x.w>x.oldW+1e-6).length,
  voidRoutes:ledger.filter(x=>x.event==='VOID_ROUTE').map(x=>({d:x.d,s:x.asset}))},
  ledger};
}
const modes=['freeze','downOnly','twoWay','fixed20','fixed50'];
const result=Object.fromEntries(modes.map(k=>[k,simulate(k)]));
const period=(log,a,b)=>{const x=log.filter(r=>r.d>=a&&r.d<=b),first=x[0].nav/(1+x[0].ret);let peak=first,mdd=0;for(const r of x){peak=Math.max(peak,r.nav);mdd=Math.min(mdd,r.nav/peak-1)}return{n:x.length,ret:x.at(-1).nav/first-1,mdd}};
const summaries=Object.fromEntries(modes.map(k=>[k,{...result[k].summary,q2:period(result[k].ledger,'20260401','20260630'),
  q3:period(result[k].ledger,'20260701','20260930'),
  q4:period(result[k].ledger,'20261001','20261112')}]));
if(result.freeze.summary.n!==151||Math.abs(summaries.freeze.q2.ret-.1278806344874277)>1e-7)throw Error('Frozen Q2 baseline mismatch');
process.stdout.write(JSON.stringify(summaries,null,2)+'\n');
