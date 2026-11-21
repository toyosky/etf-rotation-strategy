import fs from "node:fs";
// Call with exactly 10 CSV paths: Q90 daily, Q1 event pairs, Q4 event predictions, seven 2020-2026 archived OHLC CSVs.
const research=function research(inputs){
 const parse=s=>{const [head,...lines]=s.trim().split(/\r?\n/),k=head.split(",");return lines.map(l=>{const p=l.split(","),o={};for(let i=0;i<k.length;i++)o[k[i]]=p[i]??"";return o;});};
 const signal=parse(inputs[0]),q1=parse(inputs[1]),q4=parse(inputs[2]),bars=inputs.slice(3).flatMap(parse).map(x=>({s:x.symbol,d:x.date,o:+x.open,c:+x.close,l:+x.low,h:+x.high}));
 const sym=[...new Set(bars.map(x=>x.s))],byS=new Map(sym.map(s=>[s,[]])),bySD=new Map(sym.map(s=>[s,new Map()]));
 for(const b of bars){byS.get(b.s).push(b);bySD.get(b.s).set(b.d,b);}
 for(const a of byS.values())a.sort((a,b)=>a.d.localeCompare(b.d));
 const cal=byS.get("511220").map(x=>x.d),calId=new Map(cal.map((d,i)=>[d,i]));
 const when=(d,k)=>cal[(calId.get(d)??-9999)+k]??null,get=(s,d)=>bySD.get(s)?.get(d);
 const weights=Array.from({length:26},(_,i)=>Math.pow(.5,2*(25-i)/10)),sw=weights.reduce((s,x)=>s+x,0),sx=weights.reduce((s,w,i)=>s+w*i,0),sxx=weights.reduce((s,w,i)=>s+w*i*i,0);
 const fit=new Map(sym.map(s=>[s,new Map()]));
 for(const s of sym){const a=byS.get(s),out=fit.get(s);
  for(let i=25;i<a.length;i++){
   let wy=0,wxy=0,wyy=0;for(let j=0;j<26;j++){const y=Math.log(a[i-25+j].c);wy+=weights[j]*y;wxy+=weights[j]*j*y;wyy+=weights[j]*y*y;}
   const beta=(sw*wxy-sx*wy)/(sw*sxx-sx*sx),b=(wy-beta*sx)/sw;
   const ssr=Math.max(0,wyy-2*b*wy-2*beta*wxy+b*b*sw+2*b*beta*sx+beta*beta*sxx),sst=wyy-wy*wy/sw;
   const r2=sst>1e-13?Math.max(0,Math.min(1,1-ssr/sst)):0,annual=Math.expm1(beta*250),score=annual>0&&r2>0?annual*r2:0;
   out.set(a[i].d,{annual,r2,score});
  }
 }
 const q4Events=new Map(q4.map(r=>[r.date,r]));
 const events=q1.map(e=>{
  const a=fit.get(e.top1)?.get(e.d),b=fit.get(e.top2)?.get(e.d),q4e=q4Events.get(e.d);
  const r3=fit.get(e.top2)?.get(when(e.d,-3)),r1=fit.get(e.top2)?.get(when(e.d,-1));
  const scoreRatio=a&&b&&a.score>0?b.score/a.score:null;
  const ols=!!(a&&b&&a.score>0&&b.score>0);
  let rebuilt=false,sourceRebuild=null;
  if(b&&b.annual>1e-8&&r1&&b.r2>r1.r2){
   for(let i=1;i<=3;i++){
    const d=when(e.d,-i),prev=when(d,-1),p=fit.get(e.top2)?.get(d),prior=fit.get(e.top2)?.get(prev);
    if(p&&prior&&p.annual>1e-8&&prior.annual<=1e-8&&b.r2>p.r2){rebuilt=true;sourceRebuild=d;break;}
   }
  }
  const good=e.top2!==""&&e.top1_ret5!==""&&e.top2_ret5!==""&&ols;
  const strength=ols&&scoreRatio>=.8,fitR2=ols&&b.r2>=.5,rising=ols&&r3&&b.annual>0&&b.r2>r3.r2;
  const tests={
   strength:!!strength,r2:!!fitR2,r2Improving:!!rising,rebuild:rebuilt,strengthAndR2:!!(strength&&fitR2),strengthOrR2:!!(strength||fitR2),r2AndImproving:!!(fitR2&&rising),
   q4Joint:q4e?.passJoint==="1"
  };
  return {d:e.d,top1:e.top1,top2:e.top2,E:+e.withdraw_e,valid:!!good,
   top1Score:a?.score??null,top2Score:b?.score??null,scoreRatio,annual:b?.annual??null,r2:b?.r2??null,deltaR2:b&&r3?b.r2-r3.r2:null,
   rebuild:rebuilt,rebuildCross:sourceRebuild,tests,
   top1Ret5:e.top1_ret5!==""?+e.top1_ret5:null,top2Ret5:e.top2_ret5!==""?+e.top2_ret5:null,
   top1MAE5:e.mae5_top1!==""?+e.mae5_top1:null,top2MAE5:e.mae5_top2!==""?+e.mae5_top2:null};
 });
 const matchedScores=events.filter(e=>e.valid).map(e=>{
  const q=q1.find(x=>x.d===e.d);
  return {d:e.d,abs1:Math.abs(e.top1Score-(+q.score1)),abs2:Math.abs(e.top2Score-(+q.score2))};
 });
 const scoreDiff={n:matchedScores.length,max1:Math.max(...matchedScores.map(x=>x.abs1)),max2:Math.max(...matchedScores.map(x=>x.abs2))};
 const m=(rows,fn)=>rows.length?rows.reduce((a,b)=>a+fn(b),0)/rows.length:null;
 const pairs=events.filter(e=>e.valid);
 function eventStats(a){return {n:a.length,returnTop1:m(a,e=>e.top1Ret5),returnTop2:m(a,e=>e.top2Ret5),netCash:m(a,e=>e.top2Ret5-.0012),spread:m(a,e=>e.top2Ret5-e.top1Ret5),
  eWeightedCash:m(a,e=>e.E*(e.top2Ret5-.0012)),maxAdverseTop1:m(a,e=>e.top1MAE5),maxAdverseTop2:m(a,e=>e.top2MAE5),
  top2Tail5:m(a,e=>e.top2MAE5<=-.05?1:0),top1Tail5:m(a,e=>e.top1MAE5<=-.05?1:0),top2WinRate:m(a,e=>e.top2Ret5-.0012>0?1:0)};}
 const policies=["full","cash","all","strength","r2","r2Improving","rebuild","strengthAndR2","strengthOrR2","r2AndImproving","q4Joint"];
 const detail={};for(const p of policies.filter(x=>!["full","cash","all"].includes(x))){
  const qualified=pairs.filter(e=>e.tests[p]),not=pairs.filter(e=>!e.tests[p]);detail[p]={yes:eventStats(qualified),no:eventStats(not)};
 }
 const dateMap=new Map(events.map(e=>[e.d,e]));
 const prior=signal.map((r,i)=>({...r,i,ret:+r.ret,E:r.s?Math.max(0,Math.min(1,(1-1.1*(+r.Dbase)/(+r.D))*Math.max(0,Math.min(1.8,1+2*((+r.pLoss5_full)-(+r.pLoss5_vol)))))):0}));
 const extraRet=(s,d)=>{const x=get(s,when(d,1)),y=get(s,when(d,2));return x&&y&&x.o>0?y.o/x.o-1:null;};
 function simulate(p){
  let nav=1,peak=1,mdd=0,previous={},active=null,nEnter=0,buy=0,turn=0,cost=0,monthCash=0,zeroSignal=0,earlyExit=0;
  const log=[],byYear={},tradeYear={};
  for(const r of prior){
   if(active&&r.i>active.end)active=null;
   if(!active&&r.s&&r.E>1e-5){
    const evt=dateMap.get(r.d);if(!evt)throw Error("Missing Q90 event "+r.d);
    const valid=evt.valid;
    const accept=valid&&(p==="all"||(evt.tests[p]===true));
    const target=accept?evt.top2:null;
    active={end:r.i+4,E:r.E,target};
    nEnter++;if(accept){buy++;tradeYear[r.d.slice(0,4)]=(tradeYear[r.d.slice(0,4)]||0)+1;}
   }
   const weights={};
   if(r.s){const E=active?active.E:0;
    weights[r.s]=p==="full"?1:1-E;
    if(p!=="full"&&p!=="cash"&&active?.target)weights[active.target]=(weights[active.target]||0)+E;
   }else if(active?.target){active.target=null;earlyExit++;}
   for(const s of Object.keys(weights))if(weights[s]<1e-12)delete weights[s];
   let ret=0;for(const [s,w] of Object.entries(weights)){
    const dr=s===r.s?r.ret:extraRet(s,r.d);
    if(dr===null||!Number.isFinite(dr))throw Error("No price "+r.d+" "+s);
    ret+=w*dr;
   }
   let delta=0;for(const s of new Set([...Object.keys(weights),...Object.keys(previous)]))delta+=Math.abs((weights[s]||0)-(previous[s]||0));
   const fee=.0006*delta,fac=1+ret-fee;if(!(fac>0))throw Error("bad factor "+r.d);
   const start=nav;nav*=fac;peak=Math.max(peak,nav);mdd=Math.min(mdd,nav/peak-1);
   log.push(Math.log(fac));cost+=fee;turn+=delta;
   const year=r.d.slice(0,4);if(!byYear[year])byYear[year]={start,end:nav};byYear[year].end=nav;
   if(r.s)monthCash+=Math.max(0,1-Object.values(weights).reduce((s,x)=>s+x,0));else zeroSignal++;
   previous=weights;
  }
  const cagr=nav**(244/prior.length)-1;
  return {cagr,mdd,calmar:cagr/-mdd,nEnter,buy,turn,cost,cashExposureDays:monthCash,routeCashDays:zeroSignal,earlyExit,tradeYear,byYear:Object.fromEntries(Object.entries(byYear).map(([y,r])=>[y,r.end/r.start-1])),log};
 }
 const sim=Object.fromEntries(policies.map(p=>[p,simulate(p)]));
 // Year-stratified 20 trading day block bootstrap with paired daily returns and fixed outcome paths.
 const byIds=[...new Set(prior.map(x=>x.d.slice(0,4)))].map(y=>prior.map((r,i)=>r.d.startsWith(y)?i:-1).filter(i=>i>=0));
 let seed=712031,random=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return(seed>>>0)/4294967296;};
 function boot(a,b,n=1600){
  let obs=a.log.reduce((s,x,i)=>s+x-b.log[i],0)*244/prior.length;
  let dist=[];for(let i=0;i<n;i++){
   let sum=0;for(const ids of byIds)for(let j=0;j<ids.length;){const start=Math.floor(random()*ids.length);
    for(let k=0;k<20&&j<ids.length;j++,k++){const t=ids[(start+k)%ids.length];sum+=a.log[t]-b.log[t];}
   }dist.push(sum*244/prior.length);
  }
  dist.sort((a,b)=>a-b);
  return {annualLogExcess:obs,CI95:[dist[Math.floor(n*.025)],dist[Math.floor(n*.975)]],pPositive:dist.filter(x=>x>0).length/n};
 }
 const CI={};for(const name of policies.filter(x=>!["full","cash","all"].includes(x))){
  CI[name]={vsCash:boot(sim[name],sim.cash),vsAll:boot(sim[name],sim.all),vsQ4Joint:boot(sim[name],sim.q4Joint)};
 }
 const result={meta:{ohlc:bars.length,days:prior.length,Q90signals:events.length,paired:pairs.length,invalid:events.filter(x=>!x.valid).map(x=>({d:x.d,top1:x.top1,top2:x.top2})),scoreDiff},details:detail,portfolio:Object.fromEntries(Object.entries(sim).map(([p,{log,...data}])=>[p,data])),CI};
 const csv=["date,top1,top2,E,valid,score1,score2,top2_over_top1_score,top2_annual,top2_r2,top2_dr2_3d,rebuild_cross,ret5_top1,ret5_top2,mae5_top1,mae5_top2,pass_strength,pass_r2,pass_r2improving,pass_rebuild,pass_both,pass_either,pass_r2andimproving,pass_q4joint",
 ...events.map(e=>[e.d,e.top1,e.top2,e.E,+e.valid,e.top1Score??"",e.top2Score??"",e.scoreRatio??"",e.annual??"",e.r2??"",e.deltaR2??"",e.rebuildCross??"",e.top1Ret5??"",e.top2Ret5??"",e.top1MAE5??"",e.top2MAE5??"",+e.tests.strength,+e.tests.r2,+e.tests.r2Improving,+e.tests.rebuild,+e.tests.strengthAndR2,+e.tests.strengthOrR2,+e.tests.r2AndImproving,+e.tests.q4Joint].join(","))].join("\n")+"\n";
 return {result,csv};
};
if(process.argv.length!==12)throw Error("Expected 10 source CSVs");
const data=process.argv.slice(2).map(path=>fs.readFileSync(path,"utf8"));
const {result,csv}=research(data);
console.log(JSON.stringify(result,null,2));
