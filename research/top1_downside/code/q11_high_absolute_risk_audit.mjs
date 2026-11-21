import fs from "node:fs";
// node q11_high_absolute_risk_audit.mjs <archived_q90.csv> <formal_void_history.csv>
const auditE0HighRisk=function auditE0HighRisk(prediction,voiddata){
 const parse=s=>{const [h,...ls]=s.trim().split(/\r?\n/),ks=h.split(",");return ls.map(x=>Object.fromEntries(x.split(",").map((v,j)=>[ks[j],v])))};
 const q=parse(prediction),vm=new Map(parse(voiddata).map(x=>[x.date.replaceAll("-",""),x]));
 const all=q.map((r,i)=>{
 const D=+r.D,Db=+r.Dbase,loss=r.loss===""?null:+r.loss,modifier=Math.max(0,Math.min(1.8,1+2*((+r.pLoss5_full)-(+r.pLoss5_vol)))),
 baseFactor=Math.max(0,1-1.1*Db/D);
 const rawE=r.s?Math.min(1,baseFactor*modifier):0;
 const execE=rawE>=.05?rawE:0;
 const v=vm.get(r.d);return {i,d:r.d,year:r.d.slice(0,4),s:r.s,asset:r.s,fold:r.fold,D,Db,ratio:D/Db,delta:D-1.1*Db,loss,
  endReturn:r.endReturn===""?null:+r.endReturn,ret:r.ret===""?null:+r.ret,modifier,baseFactor,rawE,execE,voidState:v?.state,formalAsset:v?.target,
  eligible:v?.state==="NON_VOID"&&!!r.s&&v?.target===r.s,baseCause:rawE<=1e-12?(baseFactor<=1e-12?"BASELINE_THRESHOLD":modifier<=1e-12?"PROBABILITY_FACTOR_ZERO":"OTHER"):rawE<.05?"SMALL_E_FILTER":"ACTIVE_E"};
 });
 const good=all.filter(x=>x.s&&Number.isFinite(x.D)&&x.D>0&&Number.isFinite(x.Db)&&x.Db>0&&Number.isFinite(x.loss)&&x.loss>=0),
 allowed=good.filter(x=>x.eligible);
 const lbl=(x)=>x.execE===0?(x.D<.06?"E0_D_LT6":x.D<.07?"E0_D_6_7":x.D<.08?"E0_D_7_8":"E0_D_GE8"):(x.D>=.07?"EA_D_GE7":"EA_D_LT7");
 const N=arr=>arr.length;const avg=(xs,fn)=>xs.length?xs.reduce((s,x)=>s+fn(x),0)/xs.length:null;
 const quant=(xs,p)=>{if(!xs.length)return null;const arr=[...xs].sort((a,b)=>a-b),t=(arr.length-1)*p,a=Math.floor(t),z=Math.ceil(t);return arr[a]+(arr[z]-arr[a])*(t-a);};
 const stats=xs=>{const n=N(xs);if(!n)return {n:0};
  const streaks=[];let prev=-20;for(const x of xs){if(x.i-prev>=5){streaks.push(x);prev=x.i;}}
  return {n,years:[...new Set(xs.map(x=>x.year))].length,assets:[...new Set(xs.map(x=>x.s))].length,avgD:avg(xs,x=>x.D),meanBaseline:avg(xs,x=>x.Db),avgActual:avg(xs,x=>x.loss),
    medianActual:quant(xs.map(x=>x.loss),.5),p90Actual:quant(xs.map(x=>x.loss),.9),exceedD:avg(xs,x=>+(x.loss>x.D)),severe5:avg(xs,x=>+(x.loss>=.05)),severe8:avg(xs,x=>+(x.loss>=.08)),
    severe10:avg(xs,x=>+(x.loss>=.10)),meanExcess:avg(xs,x=>x.loss-x.D),meanReturn:avg(xs,x=>x.endReturn),
    medianReturn:quant(xs.map(x=>x.endReturn),.5),negativeReturn:avg(xs,x=>+(x.endReturn<0)),strictZero:avg(xs,x=>+(x.rawE<=1e-12)),
    meanRawE:avg(xs,x=>x.rawE),p90D:quant(xs.map(x=>x.D),.9),nonOverlap5:{n:streaks.length,severe5:avg(streaks,x=>+(x.loss>=.05)),severe8:avg(streaks,x=>+(x.loss>=.08)),exceedD:avg(streaks,x=>+(x.loss>x.D)),meanReturn:avg(streaks,x=>x.endReturn)}
  };
 };
 const group=(xs)=>Object.fromEntries(["E0_D_LT6","E0_D_6_7","E0_D_7_8","E0_D_GE8","EA_D_GE7","EA_D_LT7"].map(k=>[k,stats(xs.filter(x=>lbl(x)===k))]));
 const highE0=xs=>xs.filter(x=>x.execE===0&&x.D>=.07);
 const breakdown=xs=>{const h=highE0(xs);return {n:h.length,why:Object.fromEntries(["BASELINE_THRESHOLD","PROBABILITY_FACTOR_ZERO","SMALL_E_FILTER","OTHER","ACTIVE_E"].map(k=>[k,stats(h.filter(x=>x.baseCause===k))])),baseHigh6:stats(h.filter(x=>x.Db>=.06)),ratioBelow11:stats(h.filter(x=>x.ratio<=1.1)),ratioBelow1:stats(h.filter(x=>x.ratio<=1)),topAssets:Object.entries(Object.groupBy(h,x=>x.s)).map(([asset,a])=>({asset,n:a.length,exceedD:avg(a,x=>+(x.loss>x.D)),severe8:avg(a,x=>+(x.loss>=.08)),meanLoss:avg(a,x=>x.loss)})).sort((a,b)=>b.n-a.n).slice(0,18)};};
 const byYear=Object.fromEntries([...new Set(good.map(x=>x.year))].map(year=>{const x=good.filter(r=>r.year===year),v=allowed.filter(r=>r.year===year);return [year,{total:stats(x),E0high:stats(highE0(x)),actual:stats(v),actualE0high:stats(highE0(v)),E0lower:stats(v.filter(z=>z.execE===0&&z.D<.07))}];}));
 const breakdownAll=breakdown(good),breakdownActual=breakdown(allowed);
 const comparison={global:group(good),formalNonVoidMatched:group(allowed),baseline:stats(good),eligible:stats(allowed),highE0:stats(highE0(good)),actualHighE0:stats(highE0(allowed)),
  byYear,breakdownAll,breakdownActual,samples:all.filter(x=>x.d>="20261024"&&x.d<="20261104").map(x=>({d:x.d,s:x.s,void:x.voidState,eligible:x.eligible,D:x.D,Db:x.Db,ratio:x.ratio,rawE:x.rawE,E:x.execE,loss:x.loss,endReturn:x.endReturn,cause:x.baseCause}))};
 // CI from year stratified block bootstrap; group means and differences.
 const yrs=[...new Set(good.map(x=>x.year))],ind=yrs.map(y=>good.filter(x=>x.year===y).map(x=>x.i)),lookup=new Map(good.map(x=>[x.i,x]));
 let seed=20261121;
 const rnd=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return (seed>>>0)/4294967296;};
 const boot={};const reps=3000;
 for(const scope of ["global","formalNonVoidMatched"]){
  const comps={highE0:[],lowE0:[],highEA:[]};
  const ar=[];
  for(let b=0;b<reps;b++){
    let dat=[];for(const ii of ind){for(let j=0;j<ii.length;){const start=Math.floor(rnd()*ii.length);for(let k=0;k<20&&j<ii.length;k++,j++){const x=lookup.get(ii[(start+k)%ii.length]);if(x&&(scope==="global"||x.eligible))dat.push(x);}}}
    const he=highE0(dat),le=dat.filter(x=>x.execE===0&&x.D<.07),ha=dat.filter(x=>x.execE>0&&x.D>=.07);
    const severe=x=>avg(x,z=>+(z.loss>=.08)),exceed=x=>avg(x,z=>+(z.loss>z.D)),mu=x=>avg(x,z=>z.endReturn);
    if(!he.length||!le.length||!ha.length)continue;
    ar.push({dSevere8_low:severe(he)-severe(le),dSevere8_highE:severe(he)-severe(ha),
      dExceed_low:exceed(he)-exceed(le),dExceed_highE:exceed(he)-exceed(ha),
      dEndReturn_low:mu(he)-mu(le),dEndReturn_highE:mu(he)-mu(ha)});
  }
  const summary={validBoot:ar.length};
  for(const key of Object.keys(ar[0]??{}))summary[key]={CI95:[quant(ar.map(x=>x[key]),.025),quant(ar.map(x=>x[key]),.975)],pPositive:avg(ar,x=>+(x[key]>0))};
  boot[scope]=summary;
 }
 return {comparison,bootstrap:boot,counts:{raw:q.length,good:good.length,actualEligible:allowed.length,notRisk:q.filter(x=>!x.s).length,invalidMissingLabels:q.filter(x=>x.s&&!Number.isFinite(x.loss)).length}};
};
const files=process.argv.slice(2);if(files.length!==2)throw Error("Expected Q90 predictions and historical formal Void routes");
console.log(JSON.stringify(auditE0HighRisk(...files.map(p=>fs.readFileSync(p,"utf8"))),null,2));
