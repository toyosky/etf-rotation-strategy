// Walk-forward M0 baseline, M1 lagged residual, M2 state GLM, M3 joint state+lagged residual.
// Node 18+, no external packages. Raw inputs fixed in archived prediction CSV and state snapshot.
// Usage: node market_state_calibration_round1.mjs <oos.csv> <states_snapshot.json>
import fs from 'node:fs';
const marketStateCalibrationAudit=function marketStateCalibrationAudit(csv, snapshot) {
 const firstLine=csv.trim().split("\n"),heads=firstLine.shift().split(",");
 const rows=firstLine.map(s=>{const a=s.split(","),r={};for(let i=0;i<heads.length;i++)r[heads[i]]=["d","s","fold"].includes(heads[i])?a[i]:a[i]===""?null:+a[i];return r;});
 const st=new Map(snapshot.states.map(x=>[x.d,x]));
 if(rows.length!==snapshot.states.length)throw Error("Unmatched raw global day counts");
 const logit=p=>Math.log(Math.max(.0001,Math.min(.9999,p))/(1-Math.max(.0001,Math.min(.9999,p))));
 const expit=z=>1/(1+Math.exp(-Math.max(-30,Math.min(30,z))));
 const clamp=(p,a=.005,b=.995)=>Math.max(a,Math.min(b,p));
 const feats=["breadth20","medianVol20","volExpand","down5"];
 for(let i=0;i<rows.length;i++){
  const r=rows[i],s=st.get(r.d);if(!s)throw Error("Missing market state "+r.d);
  r.t=i;r.state=feats.map(k=>s[k]);if(r.state.some(x=>!Number.isFinite(x)))throw Error("Bad state at "+r.d);
  r.y=Number(r.loss>=.05);r.isRisk=!!r.s;
  r.originalP=r.pLoss5_full;
  if(r.isRisk&&!(r.originalP>0&&r.originalP<1))throw Error("Bad p");
 }
 const risk=rows.filter(x=>x.isRisk);
 const penalties=[8,35,35,35,35,35,35];
 function solve(A,b) {
  let n=b.length;const M=A.map((r,i)=>[...r,b[i]]);
  for(let j=0;j<n;j++){
   let k=j;for(let i=j+1;i<n;i++)if(Math.abs(M[i][j])>Math.abs(M[k][j]))k=i;
   if(Math.abs(M[k][j])<1e-10)throw Error("Singular Hessian");[M[j],M[k]]=[M[k],M[j]];
   let base=M[j][j];for(let z=j;z<=n;z++)M[j][z]/=base;
   for(let i=0;i<n;i++)if(i!==j){const f=M[i][j];for(let z=j;z<=n;z++)M[i][z]-=f*M[j][z];}
  }
  return M.map(r=>r[n]);
 }
 function rawRecent(i) {
  let sum=0,n=0;
  for(let k=i-10;k>=0&&n<120;k--)if(rows[k].isRisk){sum+=rows[k].y-rows[k].originalP;n++;}
  return {n,resid:n>=40?sum/n:0,missing:n<40?1:0,firstMaturedIndex:i>=10?i-10:-1};
 }
 // Precompute the strictly matured previous forecasting residual observable at every t.
 for(let i=0;i<rows.length;i++){rows[i].recent=rawRecent(i);}
 const rawX=(r,kind)=>{
  if(kind==="M2")return r.state;
  if(kind==="M3")return [...r.state,r.recent.resid,r.recent.missing];
  throw Error("Unsupported model");
 };
 function train(kind,trainRows,asOf){
  const k=kind==="M2"?4:6;
  const n=trainRows.length;
  if(n<160)return null;
  const xs=trainRows.map(r=>rawX(r,kind));
  const mu=Array.from({length:k},(_,j)=>xs.reduce((s,x)=>s+x[j],0)/n);
  const scale=Array.from({length:k},(_,j)=>Math.max(1e-8,Math.sqrt(xs.reduce((s,x)=>s+(x[j]-mu[j])**2,0)/n)));
  const data=trainRows.map((r,i)=>({
   x:[1,...xs[i].map((x,j)=>Math.abs(scale[j])<1e-8?0:(x-mu[j])/scale[j])],
   logit:logit(r.originalP),
   y:r.y,weight:Math.exp(-Math.LN2*(asOf-r.t)/252)
  }));
  const m=k+1,beta=new Array(m).fill(0);
  function objective(b){
   let obj=0;
   for(const d of data){
    let z=d.logit;
    for(let j=0;j<m;j++)z+=b[j]*d.x[j];
    obj+=d.weight*(Math.log(1+Math.exp(Math.min(40,z)))-d.y*z);
   }
   for(let j=0;j<m;j++)obj+=.5*penalties[j]*b[j]*b[j];
   return obj;
  }
  let converged=false,iterations=0;
  for(let iter=0;iter<20;iter++){
   const g=new Array(m).fill(0),H=Array.from({length:m},()=>new Array(m).fill(0));
   for(const d of data){
    let z=d.logit;for(let j=0;j<m;j++)z+=beta[j]*d.x[j];
    const ph=expit(z),e=d.weight*(ph-d.y),vv=d.weight*ph*(1-ph);
    for(let j=0;j<m;j++){
     g[j]+=e*d.x[j];for(let l=0;l<m;l++)H[j][l]+=vv*d.x[j]*d.x[l];
    }
   }
   for(let j=0;j<m;j++){g[j]+=penalties[j]*beta[j];H[j][j]+=penalties[j];}
   const step=solve(H,g);
   const maxStep=Math.max(...step.map(Math.abs));
   if(maxStep<1e-7){converged=true;iterations=iter;break;}
   const prev=objective(beta);
   let alpha=1;
   for(let attempt=0;attempt<18;attempt++){
    const candidate=beta.map((b,j)=>b-alpha*step[j]);
    if(objective(candidate)<=prev+1e-9){for(let j=0;j<m;j++)beta[j]=candidate[j];break;}
    alpha*=.5;
    if(attempt===17)throw Error("Backtracking failed "+kind);
   }
   iterations=iter+1;
  }
  return {kind,trainedOn:n,asOf,beta,mu,scale,iterations,converged,
   p:(r)=>{const x=rawX(r,kind);let z=logit(r.originalP)+beta[0];
    for(let j=0;j<k;j++)z+=beta[j+1]*(x[j]-mu[j])/scale[j];
    return clamp(expit(z));}
  };
 }
 let M2=null,M3=null,month="",models=[],stateSnapshots=[];
 const fitAt=[];
 for(let i=0;i<rows.length;i++){
  const r=rows[i],ym=r.d.slice(0,6);
  if(ym!==month){
   month=ym;
   const trainRows=risk.filter(x=>x.t<=i-10);
   M2=train("M2",trainRows,i);M3=train("M3",trainRows,i);
   const metadata={ym,at:r.d,cutoffIndex:i-10,latestAllowedData:rows[Math.max(0,i-10)]?.d,trainN:trainRows.length,
    M2:M2?{beta:M2.beta,mean:M2.mu,std:M2.scale,trainedOn:M2.trainedOn}:null,
    M3:M3?{beta:M3.beta,mean:M3.mu,std:M3.scale,trainedOn:M3.trainedOn}:null};
   models.push(metadata);
  }
  if(!r.isRisk)continue;
  const corr=r.recent.n<40?0:Math.max(-.12,Math.min(.12,.65*r.recent.resid));
  r.M0=r.originalP;
  r.M1=clamp(r.originalP+corr);
  r.M2=M2?M2.p(r):r.originalP;
  r.M3=M3?M3.p(r):r.originalP;
  if(!Number.isFinite(r.M2)||!Number.isFinite(r.M3))throw Error("Invalid probability");
  r.m1Residual=r.recent.resid;
  r.m1TrainingN=r.recent.n;
 }
 const modelsList=["M0","M1","M2","M3"];
 const set=risk.filter(r=>r.d>="20220101");
 const logloss=(y,p)=>-y*Math.log(clamp(p,.0001,.9999))-(1-y)*Math.log(1-clamp(p,.0001,.9999));
 const summarize=ar=>{
  const n=ar.length,actual=ar.reduce((s,r)=>s+r.y,0)/n;
  const a={n,events:ar.reduce((s,r)=>s+r.y,0),actual,originalQ90Coverage:ar.reduce((s,r)=>s+(r.loss<=r.D),0)/n};
  for(const mdl of modelsList){
   const avg=ar.reduce((s,r)=>s+r[mdl],0)/n;
   const brier=ar.reduce((s,r)=>s+(r.y-r[mdl])**2,0)/n;
   const ll=ar.reduce((s,r)=>s+logloss(r.y,r[mdl]),0)/n;
   const nDelta=ar.reduce((s,r)=>s+Math.abs(r[mdl]-r.M0),0)/n;
   a[mdl]={meanPred:avg,gap:actual-avg,brier,logLoss:ll,meanAbsProbabilityChange:nDelta};
  }
  return a;
 };
 const byYear={},byQuarter={},byYearNoOil={},byYearOil={},byMonth={},byYearAndVol={};
 for(const y of ["2022","2023","2024","2025","2026"]){
  const r=set.filter(x=>x.d.startsWith(y));byYear[y]=summarize(r);
  const rr=r.filter(x=>x.s!=="501018"),oil=r.filter(x=>x.s==="501018");
  if(rr.length)byYearNoOil[y]=summarize(rr);
  if(oil.length)byYearOil[y]=summarize(oil);
  const bands=[["low",0,.015],["mid",.015,.025],["high",.025,Infinity]];
  byYearAndVol[y]=Object.fromEntries(bands.map(([k,lo,hi])=>{const sub=r.filter(x=>x.vol>=lo&&x.vol<hi);return [k,sub.length?summarize(sub):null];}));
 }
 for(const q of [...new Set(set.map(r=>r.fold))]){const a=set.filter(x=>x.fold===q);byQuarter[q]=summarize(a);}
 for(const month of [...new Set(set.map(r=>r.d.slice(0,6)))]){const a=set.filter(x=>x.d.startsWith(month));byMonth[month]=summarize(a);}
 const annualLog=[];
 const fittedOnly=set.filter(r=>r.d>="20220101");
 const BrierDelta=Object.fromEntries(modelsList.slice(1).map(k=>[k, fittedOnly.reduce((s,r)=>s+((r.y-r.M0)**2-(r.y-r[k])**2),0)/fittedOnly.length]));
 const LLDiff=Object.fromEntries(modelsList.slice(1).map(k=>[k, fittedOnly.reduce((s,r)=>s+logloss(r.y,r.M0)-logloss(r.y,r[k]),0)/fittedOnly.length]));
 function boot(block,draws){
  let seed=0x20261120+block;
  const rand=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return (seed>>>0)/4294967296;};
  const years=["2022","2023","2024","2025","2026"];
  const vals=Object.fromEntries(["M1","M2","M3"].map(m=>[m,[]]));
  for(let loop=0;loop<draws;loop++){
   const sums={M1:0,M2:0,M3:0};let n=0;
   for(const y of years){
    const year=fittedOnly.filter(r=>r.d.startsWith(y));let added=0;
    while(added<year.length){
     const start=Math.floor(rand()*year.length);
     for(let j=0;j<block&&added<year.length;j++,added++){
      const r=year[(start+j)%year.length];n++;
      for(const m of Object.keys(sums))sums[m]+=(r.y-r.M0)**2-(r.y-r[m])**2;
     }
    }
   }
   for(const m of Object.keys(vals))vals[m].push(sums[m]/n);
  }
  const pct=(a,p)=>{const s=a.slice().sort((u,v)=>u-v),x=(s.length-1)*p,z=Math.floor(x);return s[z]+(s[Math.min(z+1,s.length-1)]-s[z])*(x-z);};
  return {block,draws,pairedDelta:Object.fromEntries(Object.entries(vals).map(([k,v])=>[k,{observed:BrierDelta[k],CI95:[pct(v,.025),pct(v,.975)],propPositive:v.filter(x=>x>0).length/v.length}]))};
 }
 const boot20=boot(20,1000),boot10=boot(10,500),boot40=boot(40,500);
 const offset=[];
 for(let mod=0;mod<5;mod++){
  const a=set.filter(r=>r.t%5===mod);offset.push({offset:mod,summary:summarize(a)});
 }
 const diagnostics={
  nStates:snapshot.states.length,risk: risk.length,calibrationTestDays:set.length,firstTest:set[0].d,lastTest:set.at(-1).d,
  marketStateMinN:Math.min(...snapshot.states.map(x=>x.nVol)),
  maturationLagGlobalTradingDays:10,minMonthTrainN:Math.min(...models.filter(x=>x.ym>="202201").map(x=>x.trainN)),
  stateCoefModels:models.filter(x=>["202201","202301","202401","202501","202604","202605","202606","202607","202608","202610","202611"].includes(x.ym)),
  minMaxPred:Object.fromEntries(modelsList.map(k=>[k,[Math.min(...set.map(x=>x[k])),Math.max(...set.map(x=>x[k]))]]))
 };
 return {metadata:{input:"OOS quarterly p5 CSV + 14 ETF Supabase market state historical snapshot",dateInTest:"2022—2026-11-12",def:"P(next-5d MAE >= 5%)",markets:"same-day cross-sectional state based on fixed 14 historical survivorship-bias-prone ETFs",noLiveMutation:true},
  overall:summarize(set),byYear,byQuarter,byMonth,byYearNoOil,byYearOil,byYearAndVol,
  averageBrierImprovement:BrierDelta,averageLogLossImprovement:LLDiff,
  blockBootstrap20:boot20,blockBootstrap10:boot10,blockBootstrap40:boot40,nonOverlapOffset:offset,
  diagnostics, monthlyModelFits:models,
  dailyPredictions:set.map(r=>({d:r.d,s:r.s,fold:r.fold,y:r.y,p0:r.M0,p1:r.M1,p2:r.M2,p3:r.M3,recentErr:r.m1Residual,nRecent:r.m1TrainingN,vol:r.vol,D:r.D,loss:r.loss,state:r.state}))};
};
if(!process.argv[2]||!process.argv[3])throw Error("CSV and market-state JSON paths required");
console.log(JSON.stringify(marketStateCalibrationAudit(fs.readFileSync(process.argv[2],'utf8'),JSON.parse(fs.readFileSync(process.argv[3],'utf8'))),null,2));