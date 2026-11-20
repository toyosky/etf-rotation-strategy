// Audits historical ETF category x prior 20-day volatility strata.
// Pure reproducible Node.js 18+, no dependencies; requires archived prior rolling OOS CSV.
// Usage: node asset_vol_calibration_audit.mjs 20261120_prob_opportunity_oos_predictions.csv
import fs from 'node:fs';
const auditAssetVolCalibration=function auditAssetVolCalibration(csv) {
 const lines=csv.trim().split("\n");const fields=lines.shift().split(",");
 const rows=lines.map(s=>{const a=s.split(","),r={};for(let i=0;i<fields.length;i++)r[fields[i]]=["d","s","fold"].includes(fields[i])?a[i]:(a[i]===""?null:+a[i]);return r;}).filter(r=>r.s&&r.loss!==null);
 const groupMap={"501018":"原油LOF","159981":"其他商品","159985":"其他商品","159934":"其他商品","161226":"其他商品",
 "513100":"美股","159509":"美股","513290":"美股","159529":"美股",
 "159957":"中港股票","512800":"中港股票","513530":"中港股票",
 "164824":"印度股票","511380":"可转债"};
 const symbolName={"501018":"原油LOF","159981":"能源化工ETF","159985":"豆粕ETF","159934":"黄金ETF",
 "161226":"白银LOF","513100":"纳指ETF","159509":"纳指科技ETF","513290":"纳指生物科技ETF","159529":"标普消费ETF",
 "159957":"创业板ETF","512800":"银行ETF","513530":"港股通红利ETF","164824":"印度基金LOF","511380":"可转债ETF"};
 if(rows.some(r=>!groupMap[r.s]))throw Error("Unmapped ETF");
 const bins=[{id:"低<1.5%",lo:0,hi:.015},{id:"中1.5%-2.5%",lo:.015,hi:.025},{id:"高≥2.5%",lo:.025,hi:Infinity}];
 const binsAlt=[{id:"低<1.0%",lo:0,hi:.01},{id:"中1.0%-2.0%",lo:.01,hi:.02},{id:"高≥2.0%",lo:.02,hi:Infinity}];
 const den=(n)=>n||1;
 const aggregate=(group)=>{
  const n=group.length,actual=group.reduce((a,r)=>a+(r.loss>=.05?1:0),0),p=group.reduce((a,r)=>a+r.pLoss5_full,0),base=group.reduce((a,r)=>a+r.pLoss5_vol,0);
  const hi3=group.reduce((a,r)=>a+(r.loss>=.03?1:0),0),totalVol=group.reduce((a,r)=>a+r.vol,0);
  const coverage=group.reduce((a,r)=>a+(r.loss<=r.D?1:0),0);
  const mse=group.reduce((a,r)=>a+(r.pLoss5_full-(r.loss>=.05?1:0))**2,0);
  return {n,events5:actual,actual5:n?actual/n:null,forecast5:n?p/n:null,volBaseline5:n?base/n:null,calibrationGap:n?(actual-p)/n:null,volBaselineGap:n?(actual-base)/n:null,actual3:n?hi3/n:null,avgVol:n?totalVol/n:null,q90Coverage:n?coverage/n:null,brier:n?mse/n:null};
 };
 const pre=rows.filter(r=>r.d<"20260101"),post=rows.filter(r=>r.d>="20260101");
 const groupKeys=[...new Set(rows.map(r=>groupMap[r.s]))];
 const groups={};
 for(const g of groupKeys)groups[g]={pre:aggregate(pre.filter(r=>groupMap[r.s]===g)),post:aggregate(post.filter(r=>groupMap[r.s]===g))};
 const symbols={};
 for(const s of Object.keys(groupMap).sort())symbols[s]={name:symbolName[s],group:groupMap[s],pre:aggregate(pre.filter(r=>r.s===s)),post:aggregate(post.filter(r=>r.s===s)),year2022:aggregate(rows.filter(r=>r.d.startsWith("2022")&&r.s===s))};
 function breakdown(binsDef,grouping="group"){
  const band=r=>(binsDef.find(x=>r.vol>=x.lo&&r.vol<x.hi)||{}).id;
  const key=r=>(grouping==="group"?groupMap[r.s]:r.s)+"|"+band(r);
  const cells=new Map();
  for(const r of rows){
   const k=key(r);
   if(!cells.has(k))cells.set(k,{key:k,category:grouping==="group"?groupMap[r.s]:r.s,volBin:band(r),pre:[],post:[]});
   cells.get(k)[r.d<"20260101"?"pre":"post"].push(r);
  }
  const cellArr=[...cells.values()].sort((a,b)=>a.category.localeCompare(b.category)||a.volBin.localeCompare(b.volBin));
  const details=cellArr.map(c=>({category:c.category,bin:c.volBin,eligible:c.pre.length>=15&&c.post.length>=3,
   insufficientComparison:c.pre.length<20||c.post.length<5,
   pre:aggregate(c.pre),post:aggregate(c.post)}));
  const eligibleKeys=new Set(details.filter(x=>x.eligible).map(x=>x.category+"|"+x.bin));
  const supportPre=pre.filter(r=>eligibleKeys.has(key(r))),supportPost=post.filter(r=>eligibleKeys.has(key(r)));
  const outOfSupport=post.filter(r=>!eligibleKeys.has(key(r)));
  const preByKey=new Map();
  for(const r of supportPre){const k=key(r);if(!preByKey.has(k))preByKey.set(k,[]);preByKey.get(k).push(r);}
  let counterfactual=0,foreCastCF=0,prevGapCF=0;
  for(const r of supportPost){
   const cellPrev=preByKey.get(key(r)),a=aggregate(cellPrev);
   counterfactual+=a.actual5;
   foreCastCF+=a.forecast5;
   prevGapCF+=a.calibrationGap;
  }
  const p0=aggregate(supportPre),p1=aggregate(supportPost);
  const cf=supportPost.length?counterfactual/supportPost.length:null;
  const cfForecast=supportPost.length?foreCastCF/supportPost.length:null;
  const cfGap=supportPost.length?prevGapCF/supportPost.length:null;
  const difference=p1.actual5-p0.actual5;
  const comp=cf-p0.actual5,conditional=p1.actual5-cf;
  const gapDiff=p1.calibrationGap-p0.calibrationGap;
  const gapComp=cfGap-p0.calibrationGap,gapConditional=p1.calibrationGap-cfGap;
  return {definition:{grouping,bins:binsDef.map(x=>x.id),eligibleRule:"pre >=15 days and 2026 >=3 days",flagLowConfidence:"pre <20 or 2026 <5",sameDayGlobalVol: true},
   counts:{strata:details.length,supportedStrata:eligibleKeys.size,preSupported:supportPre.length,postSupported:supportPost.length,postShare:supportPost.length/post.length,postOutOfSupport:outOfSupport.length,postOutOfSupportGroups:Object.entries(outOfSupport.reduce((o,r)=>(o[key(r)]=(o[key(r)]??0)+1,o),{})).sort((a,b)=>b[1]-a[1])},
   rates:{preAll:aggregate(pre),postAll:aggregate(post),preMatched:p0,postMatched:p1,counterfactual2026HistoricalEventRate:cf,counterfactual2026HistoricalForecast:cfForecast,counterfactual2026HistoricalCalibrationGap:cfGap,
   shiftInEventRateOnComparableCells:difference,assetVolMixEffect:comp,withinCellRiskChange:conditional,relativeMixShare:comp/difference,relativeWithinShare:conditional/difference,
   calibrationGapChange:gapDiff,compositionEffectOnGap:gapComp,withinCellCalibrationGapChange:gapConditional},
   cells:details,
   helper:{eligibleKeys:[...eligibleKeys],grouping,binsDef}
  };
 }
 const main=breakdown(bins),alt=breakdown(binsAlt),bySymbol=breakdown(bins,"symbol");
 const volOnly={};
 for(const b of bins){
  volOnly[b.id]={pre:aggregate(pre.filter(r=>r.vol>=b.lo&&r.vol<b.hi)),post:aggregate(post.filter(r=>r.vol>=b.lo&&r.vol<b.hi))};
 }
 const groupYear={};
 for(const yr of ["2021","2022","2023","2024","2025","2026"]){const rr=rows.filter(r=>r.d.startsWith(yr));groupYear[yr]={total:aggregate(rr)};for(const g of groupKeys)groupYear[yr][g]=aggregate(rr.filter(r=>groupMap[r.s]===g));}
 const oilVol={};for(const b of bins){
  oilVol[b.id]={year2022:aggregate(rows.filter(r=>r.s==="501018"&&r.d.startsWith("2022")&&r.vol>=b.lo&&r.vol<b.hi)),
   prior2021to2025:aggregate(pre.filter(r=>r.s==="501018"&&r.vol>=b.lo&&r.vol<b.hi)),
   year2026:aggregate(post.filter(r=>r.s==="501018"&&r.vol>=b.lo&&r.vol<b.hi))};
 }
 // Optional within-comparable-support annual block bootstrap for risk difference and calibration-gap decomposition.
 const rngFactory=seed=>{let rng=seed;return()=>{rng^=rng<<13;rng^=rng>>>17;rng^=rng<<5;return (rng>>>0)/4294967296;}};
 const fy=["2021","2022","2023","2024","2025","2026"],yearRows=Object.fromEntries(fy.map(y=>[y,rows.filter(r=>r.d.slice(0,4)===y)]));
 function boot(binsDef,grouping,block,direction=20,reps=1600){
  const selected=grouping==="group"?main:bySymbol;
  if(binsDef!==bins)throw Error("Bad parameter");
  const elig=new Set(selected.helper.eligibleKeys),band=r=>(binsDef.find(x=>r.vol>=x.lo&&r.vol<x.hi)||{}).id,kfun=r=>(grouping==="group"?groupMap[r.s]:r.s)+"|"+band(r);
  const ra=rngFactory(0x20261120+block+(grouping==="group"?0:123));
  const out={mix:[],within:[],total:[],gapMix:[],gapWithin:[],gapTotal:[],forecastCalibration2026:[]};
  let skipped=0;
  for(let b=0;b<reps;b++){
   const preS=[],postS=[];
   for(const y of fy){
    const arr=yearRows[y],N=arr.length;let count=0;
    while(count<N){
     const st=Math.floor(ra()*N);
     for(let t=0;t<block&&count<N;t++,count++){const r=arr[(st+t)%N];if(elig.has(kfun(r)))(y==="2026"?postS:preS).push(r);}
    }
   }
   if(!preS.length||!postS.length){skipped++;continue;}
   const perCell=new Map();
   for(const r of preS){
    const k=kfun(r);let p=perCell.get(k);if(!p){p={n:0,evt:0,p:0};perCell.set(k,p);}
    p.n++;p.evt+=(r.loss>=.05?1:0);p.p+=r.pLoss5_full;
   }
   let cfR=0,cfGap=0,valid=true;
   for(const r of postS){const x=perCell.get(kfun(r));if(!x){valid=false;break;}
    cfR+=x.evt/x.n;cfGap+=(x.evt-x.p)/x.n;
   }
   if(!valid){skipped++;continue;}
   const a=aggregate(preS),c=aggregate(postS),norm=postS.length;
   const m=cfR/norm-a.actual5,w=c.actual5-cfR/norm,gm=cfGap/norm-a.calibrationGap,gw=c.calibrationGap-cfGap/norm;
   out.mix.push(m);out.within.push(w);out.total.push(c.actual5-a.actual5);
   out.gapMix.push(gm);out.gapWithin.push(gw);out.gapTotal.push(c.calibrationGap-a.calibrationGap);
   out.forecastCalibration2026.push(c.calibrationGap);
  }
  const q=(v,p)=>{if(!v.length)return null;const a=[...v].sort((x,y)=>x-y),x=(a.length-1)*p,i=Math.floor(x);return a[i]+(a[Math.min(i+1,a.length-1)]-a[i])*(x-i)};
  return {block,reps,skipped,valid:reps-skipped,ci:Object.fromEntries(Object.entries(out).map(([k,v])=>[k,{mean:v.length?v.reduce((s,x)=>s+x,0)/v.length:null,lower:q(v,.025),upper:q(v,.975),positiveShare:v.length?v.filter(x=>x>0).length/v.length:null}]))};
 }
 const B=boot(bins,"group",20,20,1600),B10=boot(bins,"group",10,10,800),B40=boot(bins,"group",40,40,800);
 // 5 offset systematic thinning by trading-signal date; use the global rows not risk-only to avoid symbol-dependent index mapping.
 const allLines=csv.trim().split("\n");allLines.shift();
 const globalDates=[...new Set(allLines.map(z=>z.split(",")[0]))].sort();
 const globalDateNo=new Map(globalDates.map((d,i)=>[d,i]));
 const independentOffsets=[];
 for(let k=0;k<5;k++){
  const r=rows.filter(x=>globalDateNo.get(x.d)%5===k);
  independentOffsets.push({offset:k,pre:aggregate(r.filter(x=>x.d<"20260101")),post:aggregate(r.filter(x=>x.d>="20260101")),
   preOil:aggregate(r.filter(x=>x.d<"20260101"&&x.s==="501018")),postOil:aggregate(r.filter(x=>x.d>="20260101"&&x.s==="501018"))});
 }
 return {meta:{n:rows.length,from:rows[0].d,to:rows.at(-1).d,source:"20261120_prob_opportunity_oos_predictions.csv",target:"future5dMAE >= 5%",holdout:"quarterly expanding 2018 with 10-trading-day purge",categories:groupMap,description:symbolName},overall:{pre:aggregate(pre),post:aggregate(post)},groups,symbols,volBands:volOnly,groupYear,primary:((({helper,...o})=>o)(main)),sensitivityAltVol:((({helper,...o})=>o)(alt)),sensitivitySameTicker:((({helper,...o})=>o)(bySymbol)),oilVol,bootstrap20:B,bootstrap10:B10,bootstrap40:B40,offsets:independentOffsets,
  warnings:["Non-independence of adjacent L5 event labels","Posthoc same-historical-window exploratory strata despite prereg bin choices","Top1 proxy not live point-in-time execution","High vol conditional distribution within a bin may vary","Sparse class×vol strata cannot support strong extrapolation"]};
};
const file=process.argv[2];if(!file)throw Error("CSV path required");
process.stdout.write(JSON.stringify(auditAssetVolCalibration(fs.readFileSync(file,'utf8')),null,2)+"\n");
