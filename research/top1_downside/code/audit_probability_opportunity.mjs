// Deterministic audit over archived 2021–26 out-of-sample probability/opportunity CSV.
// Usage: node audit_probability_opportunity.mjs 20261120_prob_opportunity_oos_predictions.csv
import fs from "node:fs";
const auditProbabilities=function auditProbabilities(csv){
 const parts=csv.trim().split("\n"),head=parts.shift().split(",");
 const rows=parts.map(line=>{const cols=line.split(","),r={};head.forEach((k,i)=>r[k]=["d","s","fold"].includes(k)?cols[i]:(cols[i]===""?null:+cols[i]));return r;}).sort((a,b)=>a.d.localeCompare(b.d));
 const risk=rows.filter(r=>r.s&&r.loss!==null&&r.endReturn!==null&&r.mfe!==null);
 const years=[...new Set(rows.map(r=>r.d.slice(0,4)))].sort();
 const byYear=Object.fromEntries(years.map(y=>[y,rows.map((r,i)=>r.d.startsWith(y)?i:-1).filter(i=>i>=0)]));
 const binary=[
  ["loss3","pLoss3",r=>r.loss>=.03],
  ["loss5","pLoss5",r=>r.loss>=.05],
  ["negativeTerminal","pFinalNeg",r=>r.endReturn<0],
  ["upside5","pMfe5",r=>r.mfe>=.05]
 ];
 const clipping=(x,lo,hi)=>Math.max(lo,Math.min(hi,x));
 const brier=(p,y)=>(p-y)**2;
 const logloss=(p,y)=>-(y*Math.log(clipping(p,1e-12,1-1e-12))+(1-y)*Math.log(clipping(1-p,1e-12,1-1e-12)));
 function apRoc(rows,col,label){
  const pairs=rows.map(r=>({p:r[col],y:+label(r)})).sort((a,b)=>b.p-a.p),nPos=pairs.filter(x=>x.y===1).length,nNeg=pairs.length-nPos;
  if(nPos===0||nNeg===0)return {auroc:null,averagePrecision:null};
  let tp=0,fp=0,prec=0,auc=0,prevRecall=0;
  for(let i=0;i<pairs.length;){
   let j=i,pos=0,neg=0;
   while(j<pairs.length&&pairs[j].p===pairs[i].p){if(pairs[j].y)pos++;else neg++;j++;}
   const previousTp=tp,previousFp=fp;tp+=pos;fp+=neg;
   const rec=tp/nPos,precision=tp/(tp+fp);
   prec+=(rec-prevRecall)*precision;prevRecall=rec;
   auc+=(previousTp/nPos+tp/nPos)/2*((fp-previousFp)/nNeg);
   i=j;
  }
  return {auroc:auc,averagePrecision:prec};
 }
 function binaryMetrics(data,col,label){
  let b=0,l=0,observed=0,meanp=0;
  for(const r of data){const y=+label(r);b+=brier(r[col],y);l+=logloss(r[col],y);observed+=y;meanp+=r[col];}
  const n=data.length,metrics={n,baseRate:observed/n,meanPred:meanp/n,brier:b/n,logLoss:l/n,...apRoc(data,col,label)};
  const ordered=[...data].sort((a,b)=>a[col]-b[col]);
  metrics.calibrationBins=[];
  for(let i=0;i<5;i++){
   const subset=ordered.slice(Math.floor(n*i/5),Math.floor(n*(i+1)/5));
   metrics.calibrationBins.push({n:subset.length,prob:subset.reduce((s,r)=>s+r[col],0)/subset.length,empirical:subset.filter(label).length/subset.length});
  }
  return metrics;
 }
 function regressionMetrics(data,col){
  const n=data.length;
  return {n,meanPred:data.reduce((s,r)=>s+r[col],0)/n,meanReal:data.reduce((s,r)=>s+r.endReturn,0)/n,
   rmse:Math.sqrt(data.reduce((s,r)=>s+(r.endReturn-r[col])**2,0)/n),
   mae:data.reduce((s,r)=>s+Math.abs(r.endReturn-r[col]),0)/n};
 }
 const predictions={};
 for(const [name,target,label] of binary){
  predictions[name]={vol:binaryMetrics(risk,target+"_vol",label),full:binaryMetrics(risk,target+"_full",label)};
  if(name==="loss5")predictions[name].noMarket=binaryMetrics(risk,target+"_noMarket",label);
 }
 predictions.terminalReturn={vol:regressionMetrics(risk,"return5_vol"),full:regressionMetrics(risk,"return5_full")};
 const yearly={};
 for(const yr of years){
  const rr=risk.filter(r=>r.d.startsWith(yr));yearly[yr]={n:rr.length};
  for(const [name,target,label] of binary){
   yearly[yr][name]={base:binaryMetrics(rr,target+"_vol",label).brier,full:binaryMetrics(rr,target+"_full",label).brier,calibrationError:binaryMetrics(rr,target+"_full",label).meanPred-binaryMetrics(rr,target+"_full",label).baseRate};
  }
  yearly[yr].return5={vol:regressionMetrics(rr,"return5_vol").rmse,full:regressionMetrics(rr,"return5_full").rmse};
 }
 function exit(r,variant){
  if(variant==="full"||!r.s)return 0;
  const base=clipping(1-1.1*r.Dbase/Math.max(r.D,1e-9),0,1);
  if(variant==="q90")return base;
  const pDelta=r.pLoss5_full-r.pLoss5_vol,opDelta=r.return5_full-r.return5_vol,upDelta=r.pMfe5_full-r.pMfe5_vol;
  if(variant==="probOnly")return clipping(2*Math.max(0,pDelta),0,.6);
  if(variant==="q90prob")return clipping(base*clipping(1+2*pDelta,0,1.8),0,1);
  if(variant==="q90probOpportunity")return clipping(base*clipping(1+2*pDelta-.3*opDelta/Math.max(r.vol*Math.sqrt(5),.01),0,1.8),0,1);
  if(variant==="q90probUpside")return clipping(base*clipping(1+2*pDelta-upDelta,0,1.8),0,1);
  throw Error("Unknown variant");
 }
 function portfolio(variant,options={}){
  let nav=1,peak=1,mdd=0,prevW=0,prevS=null,remain=0,holdE=0,starts=0,active=0,avgSum=0,turn=0,tc=0,missed=0,saved=0;
  let totalGrossSaved=0,totalMiss=0;
  const logReturns=[],yearlyNav={},events=[];
  for(const r of rows){
   let w=r.s?1:0;
   if(remain>0){if(r.s)w=1-holdE;remain--;}
   else if(r.s&&variant!=="full"){
    const e=(options.noOil&&r.s==="501018")?0:exit(r,variant);
    if(e>1e-4){w=1-e;holdE=e;remain=4;starts++;avgSum+=e;events.push({d:r.d,s:r.s,e});}
    else holdE=0;
   }
   const turnover=prevS===r.s?Math.abs(prevW-w):prevW+w,fee=turnover*.0006;
   const oldNav=nav,factor=1+w*r.ret-fee;nav*=factor;peak=Math.max(nav,peak);mdd=Math.min(mdd,nav/peak-1);
   const y=r.d.slice(0,4);if(!yearlyNav[y])yearlyNav[y]={start:oldNav,end:nav};else yearlyNav[y].end=nav;
   logReturns.push(Math.log(factor));turn+=turnover;tc+=fee;
   if(r.s&&w<.99999){active++;if(r.ret>0)missed+=(1-w)*r.ret;else saved+=(1-w)*(-r.ret);}
   prevS=r.s;prevW=w;
  }
  const ann=nav**(244/rows.length)-1;
  return {annualized:ann,finalMultiple:nav,mdd,calmar:ann/(-mdd),starts,active,meanExit:starts?avgSum/starts:0,turn,tradeCosts:tc,upsideMiss:missed,downsideAvoid:saved,
   byYear:Object.fromEntries(Object.entries(yearlyNav).map(([yr,v])=>[yr,v.end/v.start-1])),logReturns,lastEntries:events.slice(-5)};
 }
 const variants=["full","q90","probOnly","q90prob","q90probOpportunity","q90probUpside"];
 const portfolios=Object.fromEntries(variants.map(k=>[k,portfolio(k)]));
 const oilCheck=Object.fromEntries(variants.slice(1).map(k=>[k,portfolio(k,{noOil:true})]));
 const diag={oil:risk.filter(r=>r.s==="501018").length,other:risk.filter(r=>r.s!=="501018").length,
  2026:risk.filter(r=>r.d.startsWith("2026")).length,
  noOil2026:risk.filter(r=>r.d.startsWith("2026")&&r.s!=="501018").length,
  event20261103:risk.find(r=>r.d==="20261103")};
 function statProbDelta(data,labelKey,target){
  const label=labelKey==="loss5"?(r=>r.loss>=.05):labelKey==="negativeTerminal"?(r=>r.endReturn<0):(r=>r.mfe>=.05);
  const col=target;
  return data.reduce((sum,r)=>{
   const y=+label(r);return sum+brier(r[col+"_vol"],y)-brier(r[col+"_full"],y);
  },0)/data.length;
 }
 const checkGroups={};for(const [g,data] of Object.entries({all:risk,noOil:risk.filter(r=>r.s!=="501018"),onlyOil:risk.filter(r=>r.s==="501018"),2026:risk.filter(r=>r.d.startsWith("2026")),noOil2026:risk.filter(r=>r.d.startsWith("2026")&&r.s!=="501018")})){
  checkGroups[g]={n:data.length,
   loss5BrierImprovement:statProbDelta(data,"loss5","pLoss5"),
   negTerminalBrierImprovement:statProbDelta(data,"negativeTerminal","pFinalNeg"),
   mfe5BrierImprovement:statProbDelta(data,"upside5","pMfe5"),
   rmseReturnFull:regressionMetrics(data,"return5_full").rmse,
   rmseReturnVol:regressionMetrics(data,"return5_vol").rmse};
 }
 let rng=0x17b5eed;const rand=()=>{rng^=rng<<13;rng^=rng>>>17;rng^=rng<<5;return (rng>>>0)/4294967296};
 const block=20,N=1600;
 const bootKeys=["loss5Brier","returnMSE","logQ90Prob","logQ90ProbOpp","logQ90ProbUp","logQ90ProbOnly","logQ90"];
 const samples=Object.fromEntries(bootKeys.map(k=>[k,[]]));
 for(let b=0;b<N;b++){
  const sums=Object.fromEntries(bootKeys.map(k=>[k,0]));let nRisk=0;
  for(const yr of years){
   const inds=byYear[yr];let got=0;
   while(got<inds.length){
    const start=Math.floor(rand()*inds.length);
    for(let j=0;j<block&&got<inds.length;j++,got++){
     const i=inds[(start+j)%inds.length],r=rows[i];
     if(r.s){
      nRisk++;
      const y=+(r.loss>=.05);
      sums.loss5Brier+=brier(r.pLoss5_vol,y)-brier(r.pLoss5_full,y);
      sums.returnMSE+=(r.endReturn-r.return5_vol)**2-(r.endReturn-r.return5_full)**2;
     }
     sums.logQ90Prob+=portfolios.q90prob.logReturns[i]-portfolios.q90.logReturns[i];
     sums.logQ90ProbOpp+=portfolios.q90probOpportunity.logReturns[i]-portfolios.q90.logReturns[i];
     sums.logQ90ProbUp+=portfolios.q90probUpside.logReturns[i]-portfolios.q90.logReturns[i];
     sums.logQ90ProbOnly+=portfolios.probOnly.logReturns[i]-portfolios.q90.logReturns[i];
     sums.logQ90+=portfolios.q90.logReturns[i]-portfolios.full.logReturns[i];
    }
   }
  }
  for(const k of bootKeys)samples[k].push(sums[k]/(k==="loss5Brier"||k==="returnMSE"?nRisk:rows.length)*(k.startsWith("log")?244:1));
 }
 const quant=(v,p)=>{const a=[...v].sort((a,b)=>a-b),t=(a.length-1)*p,i=Math.floor(t);return a[i]+(a[Math.min(i+1,a.length-1)]-a[i])*(t-i)};
 const boot={N,block,seed:"0x17b5eed",byYear:true,interpretation:"Paired approximate 95% intervals; labels overlap and holdout histories explored; not fresh blind forecast"};
 for(const [k,v] of Object.entries(samples)){
  boot[k]={ci:[quant(v,.025),quant(v,.975)],pPositive:v.filter(z=>z>0).length/N};
 }
 return {meta:{nTotal:rows.length,nRisk:risk.length,years},predictions,yearly,diag,checkGroups,
  portfolios:Object.fromEntries(Object.entries(portfolios).map(([k,v])=>[k,((({logReturns,lastEntries,...other})=>({...other,lastEntries}))(v))])),
  oilCheck:Object.fromEntries(Object.entries(oilCheck).map(([k,v])=>[k,((({logReturns,lastEntries,...other})=>({...other,lastEntries}))(v))])),
  bootstrap:boot};
};
if(!process.argv[2])throw Error("CSV path required");
process.stdout.write(JSON.stringify(auditProbabilities(fs.readFileSync(process.argv[2],"utf8")),null,2)+"\n");
