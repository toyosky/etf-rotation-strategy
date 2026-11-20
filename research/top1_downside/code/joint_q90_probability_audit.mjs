// Recalculate joint Q90+probability trigger sizing, oil sensitivity and confidence intervals.
// Usage: node joint_q90_probability_audit.mjs 20261120_prob_opportunity_oos_predictions.csv
// Node.js 18+, no dependencies. All observed prices and input predictions are stored in the CSV.
import fs from "node:fs";
const auditJointCSV=function auditJointCSV(csv) {
 const lines=csv.trim().split("\n"),fields=lines.shift().split(",");
 const rows=lines.map(line=>{const p=line.split(","),r={};for(let i=0;i<fields.length;i++){const k=fields[i];r[k]=["d","s","fold"].includes(k)?p[i]:(p[i]===""?null:+p[i]);}return r;});
 rows.sort((a,b)=>a.d.localeCompare(b.d));
 const risk=rows.filter(x=>x.s&&x.loss!==null);
 const years=[...new Set(rows.map(r=>r.d.slice(0,4)))].sort();
 const nRisk=risk.length,ln=Math.log,exp=Math.exp,clip=(v,a,b)=>Math.min(b,Math.max(a,v));
 const rawInputs=r=>{
  if(!r.s)return {S:null,p5:null,p3:null,q90:0,old:0,joint:0,joint3:0};
  const S=ln(r.D/(1.1*r.Dbase)),p5=r.pLoss5_full-r.pLoss5_vol,p3=r.pLoss3_full-r.pLoss3_vol;
  const q90=clip(1-exp(-Math.max(S,0)),0,1);
  const old=clip(q90*clip(1+2*p5,0,1.8),0,1);
  const joint=clip(1-exp(-Math.max(S+2*p5,0)),0,1);
  const joint3=clip(1-exp(-Math.max(S+2*p3,0)),0,1);
  const probOnly=clip(2*Math.max(p5,0),0,.6);
  return {S,p5,p3,q90,old,joint,joint3,probOnly};
 };
 for(const r of rows){r.input=rawInputs(r);}
 let rawCases={q90Positive:0,oldPositive:0,jointPositive:0,probabilityOverrodeQ90:0,probabilityCancelledQ90:0,jointHigherThanOld:0,jointLowerThanOld:0,joint3HigherThanOld:0,p5Pos:0,p5Neg:0,meanP5delta:0};
 const overrides=[],cancels=[];
 for(const r of risk){
  const x=r.input;
  rawCases.q90Positive+=(x.q90>1e-5);
  rawCases.oldPositive+=(x.old>1e-5);
  rawCases.jointPositive+=(x.joint>1e-5);
  if(x.q90<=1e-5&&x.joint>1e-5){rawCases.probabilityOverrodeQ90++;if(overrides.length<12)overrides.push({d:r.d,s:r.s,S:x.S,pDelta:x.p5,exit:x.joint,loss:r.loss,ret:r.ret});}
  if(x.q90>1e-5&&x.joint<=1e-5){rawCases.probabilityCancelledQ90++;if(cancels.length<12)cancels.push({d:r.d,s:r.s,S:x.S,pDelta:x.p5,loss:r.loss,ret:r.ret});}
  rawCases.jointHigherThanOld+=(x.joint>x.old+1e-5);
  rawCases.jointLowerThanOld+=(x.joint<x.old-1e-5);
  rawCases.joint3HigherThanOld+=(x.joint3>x.old+1e-5);
  rawCases.p5Pos+=(x.p5>0);rawCases.p5Neg+=(x.p5<0);
  rawCases.meanP5delta+=x.p5/nRisk;
 }
 const strategies=["full","q90","old","joint","joint3","probOnly"];
 function runPolicy(policy,options={}){
  let nav=1,peak=1,mdd=0,prevS=null,prevW=0,remaining=0,heldE=0,cost=0,turn=0;
  let started=0,daysPartial=0,withdrawalTotal=0,withdrawalCandidate=0,drawdownAvoid=0,missedPositive=0,cashUnitDays=0,netCumul=0;
  let newlyTriggeredByP=0,avoidedByP=0;
  const entries=[],byYear={},logs=[];
  for(const r of rows){
   let w=r.s?1:0,e=0,start=false;
   if(remaining>0){if(r.s)w=1-heldE;remaining--;}
   else if(r.s&&policy!=="full"){
    e=(options.noOil&&r.s==="501018")?0:(r.input[policy]);
    if(options.globalScale)e=clip(e*options.globalScale,0,1);
    if(e>1e-5){
     w=1-e;heldE=e;remaining=4;start=true;started++;withdrawalTotal+=e;
     if(r.input.q90<=1e-5&&["joint","joint3"].includes(policy))newlyTriggeredByP++;
     entries.push({d:r.d,s:r.s,e,ret:r.ret,loss:r.loss,S:r.input.S,pDelta:policy==="joint3"?r.input.p3:r.input.p5,q90:r.input.q90,old:r.input.old});
    }else{
     heldE=0;
     if(policy==="joint" && r.input.q90>1e-5)avoidedByP++;
    }
   }
   const delta=r.s===prevS?Math.abs(w-prevW):w+prevW,fee=0.0006*delta;
   const factor=1+w*r.ret-fee;
   if(!Number.isFinite(factor)||factor<=0)throw Error("Invalid trade-return factor at "+r.d);
   const prior=nav;nav*=factor;peak=Math.max(peak,nav);mdd=Math.min(mdd,nav/peak-1);
   const y=r.d.slice(0,4);if(!byYear[y])byYear[y]={initial:prior,last:nav,starts:0};byYear[y].last=nav;if(start)byYear[y].starts++;
   prevW=w;prevS=r.s;turn+=delta;cost+=fee;netCumul+=ln(factor);logs.push(ln(factor));
   if(r.s&&w<.99999){
    daysPartial++;cashUnitDays+=(1-w);
    if(r.ret>=0)missedPositive+=(1-w)*r.ret;
    else drawdownAvoid+=(1-w)*(-r.ret);
   }
  }
  const CAGR=Math.pow(nav,244/rows.length)-1;
  return {CAGR,mdd,calmar:CAGR/(-mdd),totalReturn:nav-1,tradeTurnover:turn,tradeCostProxy:cost,
    starts:started,daysPartial,avgExit:started?withdrawalTotal/started:0,
    cashUnitDays,cashFractionOfRiskTime:cashUnitDays/nRisk,avoidedLoss:drawdownAvoid,foregoneUpside:missedPositive,
    newTriggersByProbability:newlyTriggeredByP,cancelledByProbability:avoidedByP,
    byYear:Object.fromEntries(Object.entries(byYear).map(([y,v])=>[y,{return:v.last/v.initial-1,starts:v.starts}])),
    entries:entries.slice(-12),logs
  };
 }
 const perf={},noOil={},synthetic={};
 for(const p of strategies)perf[p]=runPolicy(p);
 for(const p of strategies.slice(1))noOil[p]=runPolicy(p,{noOil:true});
 synthetic.q90x12=runPolicy("q90",{globalScale:1.2});
 synthetic.q90x14=runPolicy("q90",{globalScale:1.4});
 synthetic.oldx12=runPolicy("old",{globalScale:1.2});
 // Produce a diagnostic matched-capital multiplier by root finding via exposures on all 2021–2026 test days. NOT valid train-time strategy; descriptive only.
 let lo=.5,hi=3,after=0;
 for(let i=0;i<28;i++){
  const mid=(lo+hi)/2,trial=runPolicy("old",{globalScale:mid});
  if(trial.cashUnitDays<perf.joint.cashUnitDays)lo=mid;else hi=mid;
 }
 const matchingScale=(lo+hi)/2;
 const matchedOld=runPolicy("old",{globalScale:matchingScale});
 let lo2=.5,hi2=3;
 for(let i=0;i<28;i++){
  const mid=(lo2+hi2)/2,trial=runPolicy("q90",{globalScale:mid});
  if(trial.cashUnitDays<perf.joint.cashUnitDays)lo2=mid;else hi2=mid;
 }
 const matchedQ90=runPolicy("q90",{globalScale:(lo2+hi2)/2});
 const matchedOldNoOil=runPolicy("old",{noOil:true,globalScale:matchingScale});
 const matchedQ90NoOil=runPolicy("q90",{noOil:true,globalScale:(lo2+hi2)/2});
 const datesForYear=Object.fromEntries(years.map(y=>[y,rows.map((r,i)=>r.d.slice(0,4)===y?i:-1).filter(i=>i>=0)]));
 const bootstrapPolicies={full:perf.full,q90:perf.q90,old:perf.old,joint:perf.joint,joint3:perf.joint3,probOnly:perf.probOnly,
  matchedOld,matchedQ90,oldNoOil:noOil.old,jointNoOil:noOil.joint,matchedOldNoOil,matchedQ90NoOil};
 function bootstrap(blockLen,draws=1600){
  let rng=0x51313937+blockLen;
  function rand(){rng^=rng<<13;rng^=rng>>>17;rng^=rng<<5;return (rng>>>0)/4294967296;}
  const contrast=[
   ["joint","old"],["joint","q90"],["joint","full"],["joint","matchedOld"],["joint","matchedQ90"],["joint3","old"],
   ["jointNoOil","oldNoOil"],["jointNoOil","matchedOldNoOil"],["jointNoOil","matchedQ90NoOil"]
  ];
  const samples=Object.fromEntries(contrast.map(([a,b])=>[a+"−"+b,[]]));
  for(let rep=0;rep<draws;rep++){
   const sums=Object.fromEntries(Object.keys(samples).map(k=>[k,0]));
   for(const y of years){
    const ids=datesForYear[y];let sampled=0;
    while(sampled<ids.length){
     const start=Math.floor(rand()*ids.length);
     for(let j=0;j<blockLen&&sampled<ids.length;j++,sampled++){
      const i=ids[(start+j)%ids.length];
      for(const [a,b] of contrast)sums[a+"−"+b]+=bootstrapPolicies[a].logs[i]-bootstrapPolicies[b].logs[i];
     }
    }
   }
   for(const key of Object.keys(samples))samples[key].push(sums[key]/rows.length*244);
  }
  const quant=(v,p)=>{const s=[...v].sort((a,b)=>a-b),m=(s.length-1)*p,k=Math.floor(m);return s[k]+(s[Math.min(k+1,s.length-1)]-s[k])*(m-k);};
  const answer={blockLen,draws,seed:0x51313937+blockLen,contrasts:{}};
  for(const [a,b] of contrast){
   const key=a+"−"+b,v=samples[key],difference=bootstrapPolicies[a].logs.reduce((sum,x,i)=>sum+x-bootstrapPolicies[b].logs[i],0)/rows.length*244;
   answer.contrasts[key]={logExcessAnnual:difference,CI95:[quant(v,.025),quant(v,.975)],probPositive:v.filter(z=>z>0).length/v.length};
  }
  return answer;
 }
 const B20=bootstrap(20,1600),B10=bootstrap(10,800),B40=bootstrap(40,800);
 const dailyExamples=[...new Set(["20261026","20261027","20261028","20261029","20261030","20261102","20261103","20261104","20261105","20261106","20261109"])].map(d=>{
  const r=rows.find(x=>x.d===d);if(!r)return null;
  return {date:d,symbol:r.s,loss:r.loss,return:r.ret,D:r.D,Dbase:r.Dbase,p5:r.pLoss5_full,pBaseline:r.pLoss5_vol,
   S:r.input.S,pDelta:r.input.p5,EGate:r.input.old,EJoint:r.input.joint};
 }).filter(Boolean);
 const leaveYear={};
 for(const yr of years){
  let n=0,sDiff=0,sDiffFull=0;
  for(let i=0;i<rows.length;i++)if(!rows[i].d.startsWith(yr)){
   n++;sDiff+=perf.joint.logs[i]-perf.old.logs[i];sDiffFull+=perf.joint.logs[i]-perf.full.logs[i];
  }
  leaveYear[yr]={n,annualLogExcessOverOld:sDiff/n*244,annualLogExcessOverFull:sDiffFull/n*244};
 }
 const probe=rows.filter(r=>r.s&&r.input.q90<=1e-5&&r.input.joint>1e-5);
 const triggerDiagnostics={
  rawCases,overrides,cancels,actualJointOnlyStarts:perf.joint.newTriggersByProbability,
  jointOnlyStarts:probe.length,
  newStartLoss5Rate:probe.length?probe.filter(r=>r.loss>=.05).length/probe.length:null,
  newStartMeanFinalReturn:probe.length?probe.reduce((s,r)=>s+r.endReturn,0)/probe.length:null
 };
 const flat=({logs,...r})=>r;
 return {
  meta:{n:rows.length,risk:nRisk,oil:risk.filter(r=>r.s==="501018").length,dateFrom:rows[0].d,dateThrough:rows.at(-1).d,years,
    definition:"jointU=ln(D/(1.10*Dbase))+2*(P_L5_ge5_full-P_L5_ge5_vol); E=1-exp(-max(U,0)), clip[0,1]",trackingReturn:"next-open to following-open",cashDuration:5,feePerSide:0.0006},
  triggerDiagnostics,
  performance:Object.fromEntries(Object.entries(perf).map(([k,v])=>[k,flat(v)])),
  noOil:Object.fromEntries(Object.entries(noOil).map(([k,v])=>[k,flat(v)])),
  sensitivity:Object.fromEntries(Object.entries(synthetic).map(([k,v])=>[k,flat(v)])),
  exposureMatchedPosthoc:{matchingScaleForOld:matchingScale,matchingScaleForQ90:(lo2+hi2)/2,matchedOld:flat(matchedOld),matchedQ90:flat(matchedQ90),matchedOldNoOil:flat(matchedOldNoOil),matchedQ90NoOil:flat(matchedQ90NoOil)},
  boot20:B20,boot10:B10,boot40:B40,
  leaveYear,dailyExamples,
  artifactScope:"Tests fixed already OOS probability and quantile forecasts, NOT standalone full PIT executable strategy or blind untouched 2021-2026 sample"
 };
};
if(!process.argv[2]) throw Error("Prediction CSV path required");
console.log(JSON.stringify(auditJointCSV(fs.readFileSync(process.argv[2],"utf8")),null,2));
