// Strict walk-forward Top1 risk calibration round2. Archived inputs only, no API calls or mutations.
// node market_state_round2_audit.mjs <original_oos.csv> <external_state.json> <round1_result.json>
import fs from 'node:fs';
const round2Audit=function round2Audit(csv, external, prior) {
 const [header,...raw]=csv.trim().split("\n"),cols=header.split(","),ix=Object.fromEntries(cols.map((v,i)=>[v,i]));
 const rows=raw.map((l,i)=>{const a=l.split(","),r={t:i};for(let j=0;j<cols.length;j++)r[cols[j]]=["d","s","fold"].includes(cols[j])?a[j]:a[j]===""?null:+a[j];r.y=Number(r.loss>=.05);r.risk=Boolean(r.s);return r;});
 const prev=new Map(prior.dailyPredictions.map(x=>[x.d,x]));
 const states=new Map(external.states.map(x=>[x.d,x]));
 const featureNames=["spyRet20","spyVol20","bondRet20","bondMinusSpyRet5"];
 const models=["M0","M1","Seq","Ext","ExtM1","ExtSeq"];
 const clip=(x,a=.005,b=.995)=>Math.max(a,Math.min(b,x));
 const logit=x=>Math.log(clip(x,.0001,.9999)/(1-clip(x,.0001,.9999)));
 const sigmoid=x=>1/(1+Math.exp(-Math.max(-30,Math.min(30,x))));
 for(const r of rows) {
  const s=states.get(r.d);
  r.stateValid=Boolean(s&&s.valid&&featureNames.every(k=>Number.isFinite(s[k])));
  r.features=r.stateValid?featureNames.map(k=>s[k]):null;
  r.p0=r.risk?r.pLoss5_full:null;
  if(r.risk&&r.d>="20220101"){
   const p=prev.get(r.d);if(!p||p.s!==r.s||p.y!==r.y||Math.abs(p.p0-r.p0)>1e-10)throw Error("Prior round1 mismatch "+r.d);
   r.p1=p.p1;
  }
 }
 const trainRows=rows.filter(r=>r.risk&&r.stateValid);
 function solve(A,b){
  const n=b.length,M=A.map((x,i)=>[...x,b[i]]);
  for(let c=0;c<n;c++){
   let k=c;for(let i=c+1;i<n;i++)if(Math.abs(M[i][c])>Math.abs(M[k][c]))k=i;
   if(Math.abs(M[k][c])<1e-10)throw Error("Noninvertible Hessian");
   [M[c],M[k]]=[M[k],M[c]];
   const denom=M[c][c];for(let j=c;j<=n;j++)M[c][j]/=denom;
   for(let i=0;i<n;i++)if(i!==c){const m=M[i][c];for(let j=c;j<=n;j++)M[i][j]-=m*M[c][j];}
  }
  return M.map(x=>x[n]);
 }
 function glmFit(train,asOf){
  if(train.length<160)return null;
  const k=4,m=k+1;
  const mu=Array.from({length:k},(_,j)=>train.reduce((a,r)=>a+r.features[j],0)/train.length);
  const sd=Array.from({length:k},(_,j)=>Math.max(1e-8,Math.sqrt(train.reduce((a,r)=>a+(r.features[j]-mu[j])**2,0)/train.length)));
  const X=train.map(r=>({x:[1,...r.features.map((v,j)=>(v-mu[j])/sd[j])],ln:logit(r.p0),
   y:r.y,w:Math.exp(-Math.LN2*(asOf-r.t)/252)}));
  const reg=[8,35,35,35,35],beta=new Array(m).fill(0);
  function obj(zs){
   let v=0;
   for(const r of X){let z=r.ln;for(let j=0;j<m;j++)z+=zs[j]*r.x[j];
    v+=r.w*(Math.log(1+Math.exp(Math.min(40,z)))-r.y*z);}
   for(let j=0;j<m;j++)v+=.5*reg[j]*zs[j]**2;return v;
  }
  for(let iter=0;iter<20;iter++){
   const grad=new Array(m).fill(0),H=Array.from({length:m},()=>new Array(m).fill(0));
   for(const r of X){
    let z=r.ln;for(let j=0;j<m;j++)z+=beta[j]*r.x[j];
    const p=sigmoid(z),e=r.w*(p-r.y),w=r.w*p*(1-p);
    for(let j=0;j<m;j++){grad[j]+=e*r.x[j];for(let h=0;h<m;h++)H[j][h]+=w*r.x[j]*r.x[h];}
   }
   for(let j=0;j<m;j++){grad[j]+=reg[j]*beta[j];H[j][j]+=reg[j];}
   const step=solve(H,grad);
   if(Math.max(...step.map(Math.abs))<1e-7)break;
   let alpha=1,prev=obj(beta),accepted=false;
   for(let attempt=0;attempt<20;attempt++){
    const candidate=beta.map((b,j)=>b-alpha*step[j]);
    if(obj(candidate)<=prev+1e-9){for(let j=0;j<m;j++)beta[j]=candidate[j];accepted=true;break;}
    alpha*=.5;
   }
   if(!accepted)throw Error("Line search did not converge");
  }
  return {n:train.length,asOf,beta,mu,sd,predict:r=>{
   let z=logit(r.p0)+beta[0];
   for(let i=0;i<k;i++)z+=beta[i+1]*(r.features[i]-mu[i])/sd[i];
   return clip(sigmoid(z));
  }};
 }
 const cusumByOffset=Array.from({length:5},()=>({plus:0,minus:0,lastMature:-1,alarms:0,maxPlus:0,maxMinus:0}));
 let month="",cal=null,monthlyFits=[];
 for(let i=0;i<rows.length;i++){
  const r=rows[i],q=r.d.slice(0,6);
  // At t, the matured event is from 10 previous global signal trading days.
  const maturity=rows[i-10];
  if(maturity?.risk){
   for(let off=0;off<5;off++)if(maturity.t%5===off){
    const v=cusumByOffset[off],innov=maturity.y-maturity.p0;
    v.plus=Math.max(0,v.plus+innov-.08);v.minus=Math.max(0,v.minus-innov-.08);
    v.lastMature=maturity.t;v.maxPlus=Math.max(v.maxPlus,v.plus);v.maxMinus=Math.max(v.maxMinus,v.minus);
    if(v.plus>1.2||v.minus>1.2)v.alarms++;
   }
  }
  if(q!==month){
   month=q;
   const tr=trainRows.filter(x=>x.t<=i-10);cal=glmFit(tr,i);
   monthlyFits.push({month:q,start:r.d,cutoff:rows[Math.max(0,i-10)].d,trainN:tr.length,
    beta:cal?.beta??null,mu:cal?.mu??null,sd:cal?.sd??null});
  }
  if(!r.risk||r.d<"20220101")continue;
  r.M0=r.p0;r.M1=r.p1;
  r.extDelta=r.stateValid&&cal?cal.predict(r)-r.p0:0;
  r.Ext=r.stateValid&&cal?cal.predict(r):r.M0;
  r.ExtM1=clip(r.M1+r.extDelta);
  const changes=[];
  for(let off=0;off<5;off++){
   const v=cusumByOffset[off],add=clip((v.plus-1.2)*.1,0,.1)-clip((v.minus-1.2)*.06,0,.06);
   changes.push(add);
  }
  r.seqByOffset=changes.map(x=>clip(r.M1+x));
  r.seqSignalByOffset=changes;
  r.Seq=r.seqByOffset[0];
  r.ExtSeq=clip(r.ExtM1+changes[0]);
  if(models.some(k=>!Number.isFinite(r[k])||r[k]<=0||r[k]>=1))throw Error("Invalid forecast "+r.d);
 }
 const test=rows.filter(r=>r.risk&&r.d>="20220101");
 const brier=(r,m)=>(r.y-r[m])**2;
 const logloss=(r,m)=>-r.y*Math.log(r[m])-(1-r.y)*Math.log(1-r[m]);
 function stat(ar){
  if(!ar.length)return {n:0};
  const n=ar.length,a={n,events:ar.reduce((s,r)=>s+r.y,0),actual:ar.reduce((s,r)=>s+r.y,0)/n};
  for(const m of models){
   const p=ar.reduce((s,r)=>s+r[m],0)/n;
   a[m]={meanP:p,gap:a.actual-p,brier:ar.reduce((s,r)=>s+brier(r,m),0)/n,
    logloss:ar.reduce((s,r)=>s+logloss(r,m),0)/n,meanDeltaFromM1:ar.reduce((s,r)=>s+r[m]-r.M1,0)/n};
  }
  return a;
 }
 const yrs=["2022","2023","2024","2025","2026"],year=Object.fromEntries(yrs.map(y=>[y,stat(test.filter(r=>r.d.slice(0,4)===y))]));
 const quarters=Object.fromEntries([...new Set(test.map(r=>r.fold))].map(q=>[q,stat(test.filter(r=>r.fold===q))]));
 const months=Object.fromEntries([...new Set(test.map(r=>r.d.slice(0,6)))].map(q=>[q,stat(test.filter(r=>r.d.startsWith(q)))]));
 const groups={
  noOil:stat(test.filter(r=>r.s!=="501018")),oil:stat(test.filter(r=>r.s==="501018")),
  noOil2026:stat(test.filter(r=>r.d>="20260101"&&r.s!=="501018"))
 };
 const deltas={};
 for(const m of models.filter(x=>x!=="M0"&&x!=="M1")){
  deltas[m]={
   vsM0:stat(test).M0.brier-stat(test)[m].brier,
   vsM1:stat(test).M1.brier-stat(test)[m].brier
  };
 }
 function bootstrap(len,rep){
  let seed=0x20261120+len;const rand=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return(seed>>>0)/4294967296;};
  const pairs=["M1","Seq","Ext","ExtM1","ExtSeq"].flatMap(m=>[["M0",m],["M1",m]]).filter(([a,b])=>a!==b);
  const results=Object.fromEntries(pairs.map(x=>[x.join("->"),[]]));
  const grouped=yrs.map(y=>test.filter(r=>r.d.startsWith(y)));
  for(let repIdx=0;repIdx<rep;repIdx++){
   const sums=Object.fromEntries(Object.keys(results).map(x=>[x,0]));
   let n=0;
   for(const gr of grouped){
    let done=0;while(done<gr.length){
     const start=Math.floor(rand()*gr.length);
     for(let j=0;j<len&&done<gr.length;done++,j++){
      const r=gr[(start+j)%gr.length];n++;
      for(const [a,b] of pairs)sums[a+"->"+b]+=brier(r,a)-brier(r,b);
     }
    }
   }
   for(const [key,v] of Object.entries(results))v.push(sums[key]/n);
  }
  const quant=(v,p)=>{const a=[...v].sort((x,y)=>x-y),t=(a.length-1)*p,k=Math.floor(t);return a[k]+(a[Math.min(a.length-1,k+1)]-a[k])*(t-k);};
  return {len,rep,intervals:Object.fromEntries(Object.entries(results).map(([k,v])=>[k,
    {ci95:[quant(v,.025),quant(v,.975)],positiveShare:v.filter(x=>x>0).length/rep}]))};
 }
 const b20=bootstrap(20,1000),b10=bootstrap(10,500),b40=bootstrap(40,500);
 const offsets=[];
 for(let off=0;off<5;off++){
  const v=test.map(r=>({...r,Seq:r.seqByOffset[off]}));
  const byY=Object.fromEntries(yrs.map(y=>[y,stat(v.filter(r=>r.d.slice(0,4)===y))]));
  offsets.push({off,brier:stat(v).Seq.brier,M1:stat(v).M1.brier,byY:Object.fromEntries(Object.entries(byY).map(([y,d])=>[y,{brier:d.Seq.brier,prob:d.Seq.meanP,actual:d.actual}]))});
 }
 const diagnostics={
  nHistory:rows.length,nTest:test.length,nStates:external.states.length,
  noStates:rows.filter(r=>r.risk&&r.d>="20220101"&&!r.stateValid).map(r=>r.d),
  allMaturedCutoffAtMost10Days:true,
  monthlyTrainCounts:monthlyFits.filter(x=>x.month>="202201").map(x=>({month:x.month,trainN:x.trainN})),
  maxCUSUM:cusumByOffset.map(x=>({plus:x.maxPlus,minus:x.maxMinus,alarms:x.alarms})),
  earliestAfterAprilForM1Upper2pp:test.find(r=>r.d>="20260401"&&r.M1-r.M0>.02)?.d,
  earliestAfterAprilForSeqUpper2pp:test.find(r=>r.d>="20260401"&&r.Seq-r.M0>.02)?.d,
  earliestAfterAprilForExtUpper2pp:test.find(r=>r.d>="20260401"&&r.Ext-r.M0>.02)?.d,
  earliestAfterAprilForExtSeqUpper2pp:test.find(r=>r.d>="20260401"&&r.ExtSeq-r.M0>.02)?.d,
  leading2026C2: test.filter(r=>r.d>="20260401"&&r.d<"20260701").map(r=>({d:r.d,s:r.s,act:r.y,p0:r.M0,p1:r.M1,seq:r.Seq,ext:r.Ext,extseq:r.ExtSeq,plusCUSUM:r.seqSignalByOffset[0]}))
 };
 return {meta:{target:"P(future 5d MAE>=5%)",period:"2022-01-04 to 2026-11-12",referenceTickers:["513500","511220"],noLiveChange:true},
  overall:stat(test),year,quarters,months,groups,
  pairedBrierDiff:deltas,bootstrap20:b20,bootstrap10:b10,bootstrap40:b40,
  cusumOffsets:offsets,diagnostics,monthlyFits,
  dailyPredictions:test.map(r=>({d:r.d,s:r.s,y:r.y,loss:r.loss,M0:r.M0,M1:r.M1,Seq:r.Seq,Ext:r.Ext,ExtM1:r.ExtM1,ExtSeq:r.ExtSeq,extDelta:r.extDelta,cusumExtra:r.seqSignalByOffset[0],stateValid:r.stateValid}))
 };
};
if(process.argv.length<5)throw Error("Need original OOS CSV, external-state JSON, round1-results JSON");
console.log(JSON.stringify(round2Audit(fs.readFileSync(process.argv[2],'utf8'),JSON.parse(fs.readFileSync(process.argv[3],'utf8')),JSON.parse(fs.readFileSync(process.argv[4],'utf8'))),null,2));