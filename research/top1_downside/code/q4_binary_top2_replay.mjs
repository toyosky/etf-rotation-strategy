import fs from "node:fs";
// Run with exactly nine CSV inputs: frozen Q90 daily predictions, Q1 event pairs, seven Q1 bars files (2020-2026).
const research=function research(inputs){
 const parse=(s)=>{const [h,...rows]=s.trim().split(/\r?\n/),key=h.split(",");return rows.map(l=>{const v=l.split(","),r={};for(let i=0;i<key.length;i++)r[key[i]]=v[i]??"";return r;});};
 const archived=parse(inputs[0]),pair=parse(inputs[1]),bars=inputs.slice(2).flatMap(parse).map(x=>({s:x.symbol,d:x.date,o:+x.open,c:+x.close,h:+x.high,l:+x.low}));
 const risk=["159934","159985","161226","513100","159957","159509","513290","159529","159981","501018","513530","511380","164824","512800"];
 const sym=[...risk,"511220"],byS=new Map(sym.map(s=>[s,[]])),price=new Map(sym.map(s=>[s,new Map()]));
 for(const x of bars){if(byS.has(x.s)){byS.get(x.s).push(x);price.get(x.s).set(x.d,x);}}
 for(const a of byS.values())a.sort((x,y)=>x.d.localeCompare(y.d));
 const calendar=byS.get("511220").map(x=>x.d),idx=new Map(calendar.map((d,i)=>[d,i]));
 const shift=(d,n)=>calendar[(idx.get(d)??-99999)+n]??null,get=(s,d)=>price.get(s)?.get(d);
 const weights=Array.from({length:26},(_,i)=>Math.pow(.5,2*(25-i)/10)),sw=weights.reduce((a,b)=>a+b,0),sx=weights.reduce((a,w,i)=>a+w*i,0),sxx=weights.reduce((a,w,i)=>a+w*i*i,0);
 const metric=new Map(sym.map(s=>[s,new Map()]));
 for(const s of sym){const arr=byS.get(s),out=metric.get(s);
  for(let i=25;i<arr.length;i++){
   let wy=0,wxy=0,wyy=0;
   for(let j=0;j<26;j++){const z=Math.log(arr[i-25+j].c);wy+=weights[j]*z;wxy+=weights[j]*j*z;wyy+=weights[j]*z*z;}
   const beta=(sw*wxy-sx*wy)/(sw*sxx-sx*sx),b=(wy-beta*sx)/sw;
   const ssr=Math.max(0,wyy-2*b*wy-2*beta*wxy+b*b*sw+2*b*beta*sx+beta*beta*sxx),sst=wyy-wy*wy/sw;
   const r2=sst>1e-13?Math.max(0,Math.min(1,1-ssr/sst)):0,annual=Math.expm1(beta*250),score=annual>0&&r2>0?annual*r2:0;
   let veto=false;for(let k=i-2;k<=i;k++)if(arr[k].c/arr[k-1].c < .97)veto=true;
   const sig=Math.sqrt(ssr/sw),z=sig>1e-9?(Math.log(arr[i].c)-b-25*beta)/sig:0;
   const date=arr[i].d,past5=get(s,shift(date,-5)),ret5=past5&&past5.c>0?Math.log(arr[i].c/past5.c):null;
   let returns=[],full=true;for(let j=19;j>=0;j--){const v=get(s,shift(date,-j)),u=get(s,shift(date,-j-1));
     if(!u||!v||!(u.c>0&&v.c>0)){full=false;break;}returns.push(Math.log(v.c/u.c));
   }
   const mean=full?returns.reduce((a,b)=>a+b,0)/20:0,vol20=full?Math.sqrt(returns.reduce((a,b)=>a+(b-mean)**2,0)/19):null;
   out.set(date,{score,r2,annual,z,ret5,vol20,eligible:score>0&&!veto});
  }
 }
 const rankings=new Map();
 for(const d of calendar){const cash=metric.get("511220").get(d)?.score;
  const all=risk.map(s=>({s,m:metric.get(s).get(d)})).filter(x=>x.m?.eligible&&Number.isFinite(cash)&&x.m.score>cash).sort((a,b)=>(b.m.score-a.m.score)||b.s.localeCompare(a.s));
  rankings.set(d,{top1:all[0]?.s??"",top2:all[1]?.s??"",cash});
 }
 function outcome(s,d){const entry=get(s,shift(d,1)),exit=get(s,shift(d,6));if(!entry||!exit||entry.o<=0||exit.o<=0)return null;
  let minL=Infinity;for(let i=1;i<=5;i++){const bar=get(s,shift(d,i));if(!bar||!(bar.l>0&&bar.o>0))return null;minL=Math.min(minL,bar.l);}
  return {net:exit.o/entry.o-1-.0012,gross:exit.o/entry.o-1,mae:Math.max(0,1-minL/entry.o)};
 }
 function features(d,a,b){const ma=metric.get(a)?.get(d),mb=metric.get(b)?.get(d);if(!ma||!mb||ma.ret5===null||mb.ret5===null||ma.vol20===null||mb.vol20===null)return null;
  const pa=metric.get(a)?.get(shift(d,-3)),pb=metric.get(b)?.get(shift(d,-3));
  if(!pa||!pb)return null;
  const x=[mb.ret5,mb.vol20,mb.z,mb.r2,mb.ret5-ma.ret5,(mb.score-pb.score)-(ma.score-pa.score)];
  return x.every(Number.isFinite)?{x,vol:mb.vol20,z1:ma.z,corr:null,top2: b,top1:a,score1:ma.score,score2:mb.score}:null;
 }
 const samples=[];const state=new Map();
 for(const d of calendar){const {top1,top2}=rankings.get(d);if(!top1||!top2)continue;
  const f=features(d,top1,top2);if(!f)continue;const target=outcome(top2,d);
  const s={d,...f,valid:!!target,ret:target?.net??null,loss:target?.mae??null};
  state.set(d,s);samples.push(s);
 }
 const yearMeta=[], predictions=new Map(),perYear={};
 function quantile(vals,q){if(!vals.length)return null;const a=[...vals].sort((x,y)=>x-y),p=(a.length-1)*q,lo=Math.floor(p),hi=Math.ceil(p);return a[lo]+(a[hi]-a[lo])*(p-lo);}
 function trainRidge(train){
  const n=train.length,m=6,mu=Array(m).fill(0),sd=Array(m).fill(1),Z=[];
  for(let j=0;j<m;j++){mu[j]=train.reduce((s,r)=>s+r.x[j],0)/n;sd[j]=Math.sqrt(Math.max(1e-12,train.reduce((s,r)=>s+(r.x[j]-mu[j])**2,0)/n));}
  const mat=Array.from({length:m+1},()=>Array(m+2).fill(0));
  for(const r of train){const v=[1,...r.x.map((x,j)=>Math.max(-5,Math.min(5,(x-mu[j])/sd[j])))];
   for(let j=0;j<m+1;j++){for(let k=0;k<m+1;k++)mat[j][k]+=v[j]*v[k];mat[j][m+1]+=v[j]*r.ret;}
  }
  for(let j=1;j<=m;j++)mat[j][j]+=.2*n;
  for(let i=0;i<m+1;i++){let pivot=i;for(let j=i+1;j<m+1;j++)if(Math.abs(mat[j][i])>Math.abs(mat[pivot][i]))pivot=j;
   if(Math.abs(mat[pivot][i])<1e-14)throw Error("singular ridge");
   [mat[i],mat[pivot]]=[mat[pivot],mat[i]];const div=mat[i][i];for(let k=i;k<m+2;k++)mat[i][k]/=div;
   for(let j=0;j<m+1;j++)if(j!==i){const fac=mat[j][i];for(let k=i;k<m+2;k++)mat[j][k]-=fac*mat[i][k];}
  }
  const beta=mat.map(row=>row[m+1]);
  return {beta,mu,sd,fn:x=>{let z=beta[0];for(let j=0;j<m;j++)z+=beta[j+1]*Math.max(-5,Math.min(5,(x[j]-mu[j])/sd[j]));return z;}};
 }
 const evalSet=[];
 for(let year=2021;year<=2026;year++){
  const yearDate=calendar.find(d=>d.startsWith(String(year))),cut=idx.get(yearDate)-10;
  const train=samples.filter(s=>s.valid&&idx.get(s.d)<cut);
  const test=samples.filter(s=>s.d.startsWith(String(year)));
  if(train.length<40){yearMeta.push({year,train:train.length,error:"Not enough prior-year complete labels"});continue;}
  const ridge=trainRidge(train);
  const divisor=train.map(x=>x.loss/(Math.max(x.vol,.002)*Math.sqrt(5)));
  const q90=quantile(divisor,.9),trainNet=train.reduce((s,r)=>s+r.ret,0)/train.length,trainTail=train.filter(x=>x.loss>=.05).length/train.length,trainAvgVol=train.reduce((s,r)=>s+r.vol,0)/train.length;
  const predrec={year,train:train.length,test:test.length,validTest:test.filter(x=>x.valid).length,trainQ90Multiplier:q90,trainNet,trainTail,trainAvgVol,beta:ridge.beta,mu:ridge.mu,sd:ridge.sd,lowVolFloorTrain:train.filter(x=>x.vol<.002).length};
  yearMeta.push(predrec);
  for(const s of test){const predRidge=ridge.fn(s.x),predRisk=q90*Math.max(s.vol,.002)*Math.sqrt(5),p={...s,predNet:predRidge,predRisk,trainNet,trainTail,trainQ90Multiplier:q90,year};predictions.set(s.d,p);evalSet.push(p);}
 }
 const errs={};for(let year=2021;year<=2026;year++){const a=evalSet.filter(x=>x.year===year&&x.valid);
  const mean=(arr,f)=>arr.length?arr.reduce((t,x)=>t+f(x),0)/arr.length:null;
  errs[year]={n:a.length,meanActualNet:mean(a,x=>x.ret),meanPredictedNet:mean(a,x=>x.predNet),
   predRMSE:Math.sqrt(mean(a,x=>(x.predNet-x.ret)**2)??NaN),flatRMSE:Math.sqrt(mean(a,x=>(x.trainNet-x.ret)**2)??NaN),
   riskExceed:mean(a,x=>x.loss>x.predRisk?1:0),meanPredQ90:mean(a,x=>x.predRisk),meanActualMAE:mean(a,x=>x.loss),
   acceptNet:mean(a,x=>x.predNet>0?1:0),acceptRisk:mean(a,x=>x.predRisk<=.05?1:0)};
 }
 const events=pair.map(e=>{
  const t=predictions.get(e.d),f=state.get(e.d),orig=archived.find(x=>x.d===e.d);
  const dBase=orig?+orig.Dbase:null, D=orig?+orig.D:null, riskCond=t&&dBase!==null?t.predRisk<=dBase:false,oppCond=t?t.predNet>0:false;
  const o1=e.top1_ret5!==""?+e.top1_ret5:null,o2=e.top2_ret5!==""?+e.top2_ret5:null;
  const validPair=e.top2!==""&&o1!==null&&o2!==null;
  const match=!f||(f.top1===e.top1&&f.top2===e.top2),forecastValid=!!t&&f&&match;
  return {d:e.d,top1:e.top1,top2:e.top2,E:+e.withdraw_e,
   riskD:D,riskBase:dBase,riskRatio:D&&dBase?D/dBase:null,
   pDelta:orig?+orig.pLoss5_full-(+orig.pLoss5_vol):null,
   validPair,forecastValid,forecastError:!f?"missing t feature or Top2":!t?"missing prior-year model":!match?"ranking mismatch":"",
   predNet:forecastValid?t.predNet:null,predQ90:forecastValid?t.predRisk:null,actualTop2Loss:f?.loss??null,
   actualTop2Net:validPair?o2-.0012:null,actualTop1Ret:o1,
   fitOpp:forecastValid&&oppCond,fitRisk:forecastValid&&riskCond,fitJoint:forecastValid&&oppCond&&riskCond,
   fitRiskLoose:forecastValid&&oppCond&&t.predRisk<=D,
   modelYear:t?.year??null,ret5Top2:o2};
 });
 const matched=events.filter(x=>x.forecastValid),paired=events.filter(x=>x.validPair),joint=events.filter(x=>x.fitJoint&&x.validPair);
 const eventMean=(a,f)=>a.length?a.reduce((s,x)=>s+f(x),0)/a.length:null;
 const selectionSummary=(k)=>{const selected=events.filter(x=>x[k]&&x.validPair),rejected=events.filter(x=>!x[k]&&x.validPair);
  const stats=(a)=>({n:a.length,net5:eventMean(a,x=>x.actualTop2Net),spread:eventMean(a,x=>x.actualTop2Net-x.actualTop1Ret),eWeighted:eventMean(a,x=>x.E*x.actualTop2Net),lossAbovePred:a.length?eventMean(a.filter(x=>x.predQ90!==null&&x.actualTop2Loss!==null),x=>x.actualTop2Loss>x.predQ90?1:0):null,avgRiskRatio:eventMean(a,x=>x.riskRatio)});
  return {selected:stats(selected),rejected:stats(rejected)};
 };
 const policies=["full","cash","all","opportunity","risk","joint","loose"];
 const eventMap=new Map(events.map(e=>[e.d,e]));
 const day=archived.map((x,i)=>({...x,i,ret:+x.ret,E:x.s?Math.max(0,Math.min(1,(1-1.1*(+x.Dbase)/(+x.D))*Math.max(0,Math.min(1.8,1+2*((+x.pLoss5_full)-(+x.pLoss5_vol)))))):0}));
 function extraReturn(s,d){const a=get(s,shift(d,1)),b=get(s,shift(d,2));return a&&b&&a.o>0?b.o/a.o-1:null;}
 function simulate(name){
  let nav=1,peak=1,mdd=0,prev={},active=null,nStart=0,nBuy=0,cashExposure=0,fees=0,turn=0;
  const logs=[],byYear={};
  for(const r of day){
   if(active&&r.i>active.end)active=null;
   if(!active&&r.s&&r.E>1e-5){
    const event=eventMap.get(r.d);if(!event)throw Error("No event for Q90 "+r.d);
    const eligible=event.validPair;
    const chosen=eligible&&(name==="all"||name==="opportunity"&&event.fitOpp||name==="risk"&&event.fitRisk||name==="joint"&&event.fitJoint||name==="loose"&&event.fitRiskLoose);
    active={end:r.i+4,E:r.E,alt:chosen?event.top2:null};nStart++;if(chosen)nBuy++;
   }
   const w={};
   if(r.s){const E=active?active.E:0;w[r.s]=name==="full"?1:1-E;
     if(name!=="full"&&name!=="cash"&&active?.alt)w[active.alt]=(w[active.alt]||0)+E;
   }else if(active?.alt)active.alt=null;
   for(const s of Object.keys(w))if(w[s]<1e-12)delete w[s];
   let ret=0;for(const [s,weight] of Object.entries(w)){
    const v=s===r.s?r.ret:extraReturn(s,r.d);
    if(v===null||!Number.isFinite(v))throw Error("No intra-portfolio return "+r.d+" "+s);
    ret+=weight*v;
   }
   let delta=0;for(const s of new Set([...Object.keys(w),...Object.keys(prev)]))delta+=Math.abs((w[s]||0)-(prev[s]||0));
   const fee=.0006*delta,fac=1+ret-fee;
   if(!(fac>0))throw Error("bad account factor "+r.d);
   const start=nav;nav*=fac;peak=Math.max(peak,nav);mdd=Math.min(mdd,nav/peak-1);fees+=fee;turn+=delta;logs.push(Math.log(fac));
   const yr=r.d.slice(0,4);if(!byYear[yr])byYear[yr]={start,end:nav};byYear[yr].end=nav;
   if(r.s)cashExposure+=Math.max(0,1-Object.values(w).reduce((x,y)=>x+y,0));
   prev=w;
  }
  const cagr=Math.pow(nav,244/day.length)-1;
  return {cagr,mdd,calmar:cagr/-mdd,nStart,nBuy,cashExposure,fees,turn,byYear:Object.fromEntries(Object.entries(byYear).map(([y,obj])=>[y,obj.end/obj.start-1])),logs};
 }
 const sims=Object.fromEntries(policies.map(x=>[x,simulate(x)]));
 // Blocks of 20 trading days within each year keep temporal autocorrelation and strict paired indices.
 let seed=2097345;const rand=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return(seed>>>0)/4294967296;};
 const byY=[...new Set(day.map(x=>x.d.slice(0,4)))].map(y=>day.map((r,i)=>r.d.startsWith(y)?i:-1).filter(i=>i>=0));
 function boot(a,b,count=2000){const dist=[];
  for(let i=0;i<count;i++){let x=0;
   for(const arr of byY)for(let n=0;n<arr.length;){const start=Math.floor(rand()*arr.length);for(let k=0;k<20&&n<arr.length;k++,n++){const id=arr[(start+k)%arr.length];x+=a.logs[id]-b.logs[id];}}
   dist.push(x*244/day.length);
  }
  dist.sort((a,b)=>a-b);
  return {annualLogExcess:a.logs.reduce((s,x,i)=>s+x-b.logs[i],0)*244/day.length,CI95:[dist[Math.floor(.025*count)],dist[Math.floor(.975*count)]],pPositive:dist.filter(x=>x>0).length/count};
 }
 const contrasts={allVsCash:boot(sims.all,sims.cash),jointVsCash:boot(sims.joint,sims.cash),jointVsAll:boot(sims.joint,sims.all),oppVsCash:boot(sims.opportunity,sims.cash),riskVsCash:boot(sims.risk,sims.cash),looseVsCash:boot(sims.loose,sims.cash)};
 const reports={metadata:{bars:bars.length,eligibleDailyPairs:samples.length,trainingLabeledPairs:samples.filter(s=>s.valid).length,oosTests:evalSet.length,oosComplete:evalSet.filter(s=>s.valid).length,oldTop1SignalDays:archived.length,Q90events:events.length,Q90matched:matched.length,Q90validPairs:paired.length,Q90both:matched.filter(e=>e.validPair).length,Q90noForecast:events.filter(e=>!e.forecastValid).map(e=>({d:e.d,reason:e.forecastError,top1:e.top1,top2:e.top2})),Q90missingPricePath:events.filter(e=>!e.validPair).map(e=>e.d),Q90jointEligible:joint.length},
  train:yearMeta,forecasts:errs,events:{all:{n:events.length},selection:{opp:selectionSummary("fitOpp"),risk:selectionSummary("fitRisk"),joint:selectionSummary("fitJoint"),loose:selectionSummary("fitRiskLoose")}},
  portfolio:Object.fromEntries(Object.entries(sims).map(([key,{logs,...v}])=>[key,v])),contrasts,
  yearEvents:Object.fromEntries([...new Set(events.map(e=>e.d.slice(0,4)))].map(y=>[y,{total:events.filter(e=>e.d.startsWith(y)).length,forecast:events.filter(e=>e.d.startsWith(y)&&e.forecastValid).length,opportunity:events.filter(e=>e.d.startsWith(y)&&e.fitOpp&&e.validPair).length,risk:events.filter(e=>e.d.startsWith(y)&&e.fitRisk&&e.validPair).length,joint:events.filter(e=>e.d.startsWith(y)&&e.fitJoint&&e.validPair).length,loose:events.filter(e=>e.d.startsWith(y)&&e.fitRiskLoose&&e.validPair).length}]))};
 const predHeader=["date","top1","top2","modelYear","E","D","Dbase","D_over_Dbase","P5full_minus_vol","validPair","forecastValid","predNet5","predQ90MAE5","actualTop2Net5","actualTop2MAE5","actualTop1Ret5","passOpportunity","passRiskDbase","passJoint","passRiskD","forecastError"];
 const csv=predHeader.join(",")+"\n"+events.map(e=>[e.d,e.top1,e.top2,e.modelYear??"",e.E,e.riskD??"",e.riskBase??"",e.riskRatio??"",e.pDelta??"",+e.validPair,+e.forecastValid,e.predNet??"",e.predQ90??"",e.actualTop2Net??"",e.actualTop2Loss??"",e.actualTop1Ret??"",+e.fitOpp,+e.fitRisk,+e.fitJoint,+e.fitRiskLoose,e.forecastError].join(",")).join("\n")+"\n";
 return {reports,csv};
};
if(process.argv.length!==11)throw new Error("Pass nine CSV paths: Q90 Q1Event bars2020..bars2026");
const result=research(process.argv.slice(2).map(path=>fs.readFileSync(path,"utf8")));
console.log(JSON.stringify(result.reports,null,2));
