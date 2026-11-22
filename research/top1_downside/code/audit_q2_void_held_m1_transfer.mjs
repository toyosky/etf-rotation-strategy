// 2026 Q2 Void-frozen ETF risk and M1 transfer diagnostic.
// No network and no parameter fitting. No production changes.
//
// Usage:
// node research/top1_downside/code/audit_q2_void_held_m1_transfer.mjs \
//   research/top1_downside/audit/20261122_q2_frozen_incumbent_ohlc_snapshot.json \
//   research/top1_downside/audit/20261122_q2_m1_voidfirst_proxy_replay.json \
//   research/top1_downside/audit/20261120_market_state_calibration_round1_results.json \
//   research/top1_downside/audit/20261120_prob_opportunity_oos_predictions.csv
//
// WARNING: empirical asset prior below is NOT the originally trained P0;
// only three Void days have original P0 for the exact frozen ETF.
import fs from 'node:fs';

const args=process.argv.slice(2);
if(args.length!==4)throw Error('Requires OHLC, Void replay, M1 results and original OOS CSV');
const [ohlc,replay,cal,rawCsv]=args.map((path,i)=>i===3?fs.readFileSync(path,'utf8'):JSON.parse(fs.readFileSync(path,'utf8')));
const byAsset=Object.groupBy(ohlc.rows,x=>x.symbol);
const m1ByDate=new Map(cal.dailyPredictions.map(x=>[x.d,x]));
const [header,...rawLines]=rawCsv.trim().split('\n');
const fields=header.split(',');
const rawRows=rawLines.map(s=>{
 const vals=s.split(','),r={};
 fields.forEach((k,i)=>r[k]=['d','s','fold'].includes(k)?vals[i]:vals[i]===''?null:+vals[i]);
 return r;
});
const topByDate=new Map(rawRows.map(x=>[x.d,x]));
const clip=(v,lo=.005,hi=.995)=>Math.max(lo,Math.min(hi,v));
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
const episodeLastDay={'159509':'2026-06-17','159957':'2026-06-30'};
function dated(x){return x.slice(0,4)+'-'+x.slice(4,6)+'-'+x.slice(6);}
function getFuture(sym,d){
 const rows=byAsset[sym],i=rows.findIndex(x=>x.date===d);
 if(i<0||i+5>=rows.length)throw Error('Missing full 5-day OHLC: '+sym+' '+d);
 return rows.slice(i+1,i+6);
}
function label(sym,d,through=null){
 const bars=getFuture(sym,d),keep=through?bars.filter(x=>x.date<=through):bars;
 if(!keep.length)throw Error('Zero-day exposure '+sym+' '+d);
 return {loss:Math.max(0,1-Math.min(...keep.map(x=>x.low))/bars[0].open),sessions:keep.length};
}
function history(sym,d){
 const rows=byAsset[sym],i=rows.findIndex(x=>x.date===d);
 const matureEnd=i-10,from=matureEnd-119;
 if(from<0)throw Error('Insufficient 120-day/10-lag own fund history '+sym+' '+d);
 const xs=rows.slice(from,matureEnd+1).map(x=>label(sym,x.date).loss).sort((a,b)=>a-b);
 return {n:xs.length,p:xs.filter(x=>x>=.05).length/xs.length,q90:xs[Math.ceil(.9*xs.length)-1]};
}
const cases=replay.q2Daily.filter(x=>x.quadrant==='DEFENSIVE_VOID').map(x=>{
 const s=x.actualSymbol,d=dated(x.signal),m=m1ByDate.get(x.signal),top=topByDate.get(x.signal),
 hist=history(s,d),full=label(s,d),exposed=label(s,d,episodeLastDay[s]);
 if(m&&(m.s!==top.s || Math.abs(m.p0-top.pLoss5_full)>1e-11))
  throw Error('M1 stored input mismatch '+d);
 if(top?.s===s && Math.abs(full.loss-top.loss)>1e-12)
  throw Error('Held/Top1 exact label mismatch '+d);
 const corr=m?m.p1-m.p0:null;
 return {signal:x.signal,held:s,rawTop1:top?.s??null,
  rawTop1L5:top?.loss??null,heldL5:full.loss,withinVoidLoss:exposed.loss,
  withinVoidSessions:exposed.sessions,hit:+(full.loss>=.05),withinHit:+(exposed.loss>=.05),
  own120EmpiricalP:hist.p,own120EmpiricalQ90:hist.q90,
  M1GlobalCorrection:corr,
  empiricalPlusM1:corr===null?null:clip(hist.p+corr),
  originalP0ForHeldETF:top?.s===s?top.pLoss5_full:null,
  originalM1ForHeldETF:top?.s===s?m.p1:null};
});
const summary=a=>{
 const matched=a.filter(x=>x.M1GlobalCorrection!==null);
 const brier=k=>mean(matched.map(x=>(x.hit-x[k])**2));
 const exact=a.filter(x=>x.originalP0ForHeldETF!==null);
 return {n:a.length,m1TransferN:matched.length,eventsFull5:a.filter(x=>x.hit).length,
  eventsWithinVoid:a.filter(x=>x.withinHit).length,
  meanCorrection:mean(matched.map(x=>x.M1GlobalCorrection)),
  negativeCorrectionDays:matched.filter(x=>x.M1GlobalCorrection<0).length,
  positiveCorrectionDays:matched.filter(x=>x.M1GlobalCorrection>0).length,
  meanOwnP:mean(matched.map(x=>x.own120EmpiricalP)),
  meanTransferredP:mean(matched.map(x=>x.empiricalPlusM1)),
  empiricalBrier:brier('own120EmpiricalP'),transferredBrier:brier('empiricalPlusM1'),
  empiricalQ90Coverage:a.filter(x=>x.heldL5<=x.own120EmpiricalQ90).length/a.length,
  exactOriginalHeldPredictions:exact.length,
  exactP0Brier:exact.length?mean(exact.map(x=>(x.hit-x.originalP0ForHeldETF)**2)):null,
  exactM1Brier:exact.length?mean(exact.map(x=>(x.hit-x.originalM1ForHeldETF)**2)):null};
};
const byEpisode={first:summary(cases.filter(x=>x.held==='159509')),
 second:summary(cases.filter(x=>x.held==='159957'))};
const final={method:{
 data:'Supabase OHLC frozen snapshot + Github Void-day frozen ETF + original raw Top1 M1 correction',
 definition:'label=1-min(next 5 session lows)/next open, clipped at 0; next-10 mature 120-day own historical prior',
 limitation:'Full original unified raw P0/Q90 never archived for 24 of 27 held dates; transfer applies global correction to a separate empirical prior, NOT official M1, and cannot justify trading.',
 censor:'Within-Void label stops on final session prior to executing Void exit on next open; its horizon is variable and NOT suitable for five-day Brier comparison.'},
 summary:summary(cases),byEpisode,cases};
process.stdout.write(JSON.stringify(final,null,2)+'\n');
