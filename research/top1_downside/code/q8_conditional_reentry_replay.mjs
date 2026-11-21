import fs from "node:fs";
// node q8_conditional_reentry_replay.mjs <Q90_daily.csv> <Q7_daily_paths.csv> <Q7_results.json> <Q7B_results.json>
const analyzeQ8=function analyzeQ8(inputs){
 const parse=s=>{const [h,...lines]=s.trim().split(/\r?\n/),fields=h.split(",");return lines.map(l=>Object.fromEntries(l.split(",").map((x,i)=>[fields[i],x])))};
 const daily=parse(inputs[0]),paths=parse(inputs[1]),q7=JSON.parse(inputs[2]),q7b=JSON.parse(inputs[3]);
 if(daily.length!==paths.length)throw Error("records differ");
 const n=daily.length;
 const rows=daily.map((d,i)=>{
  const p=paths[i];if(p.date!==d.d)throw Error("dates mismatched on "+d.d);
  const E=+p.dailyE,oldE=i?+paths[i-1].dailyE:0;
  return {i,d:d.d,year:d.d.slice(0,4),symbol:d.s,ret:d.s?+d.ret:0,E,oldE,delta:oldE-E,rawE:+p.rawE,
   D:+d.D,Dbase:+d.Dbase,pLoss5Full:+d.pLoss5_full,pLoss5Vol:+d.pLoss5_vol};
 });
 const H=[1,3,5,10];
 const all=rows.filter(r=>r.symbol&&r.oldE>=.05-1e-10&&r.delta>=.05-1e-10).map(r=>{
  const outcome={};for(const h of H){
   if(r.i+h>n-1){outcome[h]=null;continue;}
   let acc=1,minPath=0;
   for(let k=0;k<h;k++){acc*=1+rows[r.i+k].ret;if(!(acc>0))throw Error("bad return "+r.d);minPath=Math.min(minPath,acc-1);}
   outcome[h]={gross:acc-1,netAfterRoundTrip:acc*(1-.0006)-.0006-1,minPortfolioPath:minPath};
  }
  return {...r,outcome};
 });
 const embargo=(()=>{let last=-Infinity,lastYear="";return all.filter(r=>{if(r.year!==lastYear){last=-Infinity;lastYear=r.year;}if(r.i-last<5)return false;last=r.i;return true;});})();
 const mean=(array,fn)=>array.length?array.reduce((a,x)=>a+fn(x),0)/array.length:null;
 const quant=(a,p)=>{if(!a.length)return null;const arr=a.slice().sort((a,b)=>a-b),index=(arr.length-1)*p,low=Math.floor(index),high=Math.ceil(index);return arr[low]+(arr[high]-arr[low])*(index-low);};
 const stats=(e,h)=>{
  const list=e.filter(x=>x.outcome[h]!==null),r=list.map(x=>x.outcome[h].gross),net=list.map(x=>x.outcome[h].netAfterRoundTrip),totalDelta=list.reduce((s,x)=>s+x.delta,0);
  return {n:list.length,meanGross:mean(list,x=>x.outcome[h].gross),meanNetRoundTrip:mean(list,x=>x.outcome[h].netAfterRoundTrip),
   medianGross:quant(r,.5),p05Gross:quant(r,.05),p10Gross:quant(r,.1),minGross:quant(r,0),positiveGross:r.filter(x=>x>0).length/list.length,
   positiveNet:net.filter(x=>x>0).length/list.length,belowMinus3Gross:r.filter(x=>x<=-.03).length/list.length,
   weightedGrossByDelta:totalDelta?list.reduce((s,x)=>s+x.delta*x.outcome[h].gross,0)/totalDelta:null,
   averageAccountGainIfImmediate:mean(list,x=>x.delta*x.outcome[h].gross),
   weightedNetByDelta:totalDelta?list.reduce((s,x)=>s+x.delta*x.outcome[h].netAfterRoundTrip,0)/totalDelta:null,
   avgMinPath:mean(list,x=>x.outcome[h].minPortfolioPath),negativeMinPath:mean(list,x=>x.outcome[h].minPortfolioPath<0?1:0),
   meanDelta:mean(list,x=>x.delta),totalDelta};
 };
 const allStats=Object.fromEntries(H.map(h=>[h,stats(all,h)])),embStats=Object.fromEntries(H.map(h=>[h,stats(embargo,h)]));
 const perYear=Object.fromEntries([...new Set(rows.map(r=>r.year))].map(y=>{
  const e=all.filter(r=>r.year===y),b=embargo.filter(r=>r.year===y);
  return [y,{events:e.length,embargo5:b.length,meanDelta:mean(e,x=>x.delta),gross1:stats(e,1),gross3:stats(e,3),gross5:stats(e,5),embargo5gross5:stats(b,5)}];
 }));
 const underZero=all.filter(x=>x.rawE<.05),stillPartial=all.filter(x=>x.rawE>=.05);
 const byType={fullRestoration:Object.fromEntries([1,3,5].map(h=>[h,stats(underZero,h)])),partialRestoration:Object.fromEntries([1,3,5].map(h=>[h,stats(stillPartial,h)]))};
 // Bootstrap circular 20-market-day blocks within each year's daily calendar; events are fixed PIT entry decisions and outcomes may overlap.
 const byYearDay=[...new Set(rows.map(r=>r.year))].map(y=>rows.filter(r=>r.year===y).map(r=>r.i));
 const eventMap=new Map(all.map(e=>[e.i,e]));
 let seed=982173;const rand=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return(seed>>>0)/4294967296;};
 const B=3000,confidence={};
 for(const h of [1,3,5,10]){
  const boot=[],bootW=[],bootWin=[];
  for(let z=0;z<B;z++){
   let total=0,count=0,wsum=0,wcount=0,wins=0;
   for(const ix of byYearDay)for(let pos=0;pos<ix.length;){
    const offset=Math.floor(rand()*ix.length);
    for(let k=0;k<20&&pos<ix.length;k++,pos++){
     const t=ix[(offset+k)%ix.length],e=eventMap.get(t),o=e?.outcome[h];
     if(!o)continue;
     total+=o.netAfterRoundTrip;wsum+=e.delta*o.netAfterRoundTrip;wcount+=e.delta;count++;if(o.netAfterRoundTrip>0)wins++;
    }
   }
   if(count){boot.push(total/count);bootW.push(wsum/wcount);bootWin.push(wins/count);}
  }
  const toStat=ar=>({CI95:[quant(ar,.025),quant(ar,.975)],probPositive:ar.filter(z=>z>0).length/ar.length});
  confidence[h]={meanEventNet:toStat(boot),deltaWeightedNet:toStat(bootW),winRate:{CI95:[quant(bootWin,.025),quant(bootWin,.975)]}};
 }
 const check={q7DailyN:q7.period.n,q7Daily5EAdjusts:q7.scenarios.base6bp.daily5.actions,
  reentryEventCount:all.length,q7Daily5Buybacks:q7.scenarios.base6bp.daily5.buyActions,dayListMatch:all.every(x=>x.E< x.oldE)};
 const portfolio={};
 for(const fee of ["base6bp","minimum5yuan","minimum5plus4bp"]){
  const rec={
   locked:q7.scenarios[fee].lock5,daily:q7.scenarios[fee].daily5,
   S1:q7b.summary[`S1_2day_oneshot__${fee}`],S2:q7b.summary[`S2_2day_10pp_oneshot__${fee}`],S3:q7b.summary[`S3_3day_oneshot__${fee}`]
  };
  portfolio[fee]=Object.fromEntries(Object.entries(rec).map(([name,x])=>[name,{
   cagr:x.cagr,mdd:x.mdd,meanCash:x.meanCash??x.meanE,actions:x.actions,buyActions:x.buyActions??x.buys,
   sellActions:x.sellActions??x.sells,tickets:x.tickets,totalFees:x.totalFees,
   annual:Object.fromEntries(Object.entries(x.byYear).map(([y,r])=>[y,r.ret??r.ret]))}]));
 }
 const findings={meta:{first:rows[0].d,last:rows.at(-1).d,allDays:n,events:all.length,embargo5:embargo.length,
  countForward5Missing:all.filter(x=>!x.outcome[5]).length,check},eventOutcomes:allStats,embargo5Outcomes:embStats,
  byYear:perYear,byType,confidence,portfolio};
 const header=["date","year","top1","raw_E","previous_executed_E","executed_E","restored_delta","D","Dbase","pLoss5_full","pLoss5_vol",
 ...H.flatMap(h=>[`gross_${h}d`,`netRoundTrip_${h}d`,`minPath_${h}d`]),"embargo5"];
 const embSet=new Set(embargo.map(x=>x.d));
 const csv=[header.join(","),...all.map(x=>[x.d,x.year,x.symbol,x.rawE,x.oldE,x.E,x.delta,x.D,x.Dbase,x.pLoss5Full,x.pLoss5Vol,
 ...H.flatMap(h=>x.outcome[h]?[x.outcome[h].gross,x.outcome[h].netAfterRoundTrip,x.outcome[h].minPortfolioPath]:["","",""]),+embSet.has(x.d)].join(","))].join("\n")+"\n";
 return {findings,csv};
};
const args=process.argv.slice(2);if(args.length!==4)throw Error("Expected exactly four local input files");
const {findings,csv}=analyzeQ8(args.map(f=>fs.readFileSync(f,"utf8")));
console.log(JSON.stringify(findings,null,2));
