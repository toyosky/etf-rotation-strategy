import fs from "node:fs";
// Recalculate from frozen repository files; pass 9 CSV paths in order: Q90 predictions, Q1 events, q1_bars_2020.csv ... q1_bars_2026.csv.
const audit=function audit(inputs){
 const parse=s=>{const [header,...lines]=s.trim().split(/\r?\n/),keys=header.split(",");return lines.map(l=>{const v=l.split(","),o={};for(let i=0;i<keys.length;i++)o[keys[i]]=v[i]??"";return o;});};
 const daily=parse(inputs[0]),events=parse(inputs[1]),barRows=inputs.slice(2).flatMap(parse).map(b=>({s:b.symbol,d:b.date,o:+b.open,c:+b.close,h:+b.high,l:+b.low}));
 const symSet=[...new Set(barRows.map(b=>b.s))];
 const bySymbol=new Map(symSet.map(s=>[s,[]])),byDate=new Map(symSet.map(s=>[s,new Map()]));
 for(const b of barRows){bySymbol.get(b.s).push(b);byDate.get(b.s).set(b.d,b);}
 for(const a of bySymbol.values()){a.sort((x,y)=>x.d.localeCompare(y.d));a.forEach((b,i)=>b.i=i);}
 const calendar=bySymbol.get("511220").map(x=>x.d),ix=new Map(calendar.map((d,i)=>[d,i]));
 const when=(d,n)=>calendar[(ix.get(d)??-999)+n]??null;
 const price=(s,d)=>byDate.get(s)?.get(d);
 const weights=Array.from({length:26},(_,i)=>Math.pow(.5,2*(25-i)/10));
 const sw=weights.reduce((s,v)=>s+v,0),sx=weights.reduce((s,v,i)=>s+v*i,0),sxx=weights.reduce((s,v,i)=>s+v*i*i,0);
 const scores=new Map(symSet.map(s=>[s,new Map()]));
 for(const s of symSet){
  const a=bySymbol.get(s),out=scores.get(s);
  for(let i=25;i<a.length;i++){
   let wy=0,wxy=0,wyy=0;
   for(let j=0;j<26;j++){const y=Math.log(a[i-25+j].c);wy+=weights[j]*y;wxy+=weights[j]*j*y;wyy+=weights[j]*y*y;}
   const slope=(sw*wxy-sx*wy)/(sw*sxx-sx*sx),b=(wy-slope*sx)/sw;
   const sse=Math.max(0,wyy-2*b*wy-2*slope*wxy+b*b*sw+2*b*slope*sx+slope*slope*sxx),sst=wyy-wy*wy/sw;
   const r2=sst>1e-12?Math.max(0,Math.min(1,1-sse/sst)):0,annual=Math.expm1(slope*250),score=annual>0&&r2>0?annual*r2:0;
   const sig=Math.sqrt(sse/sw),z=sig>1e-9?(Math.log(a[i].c)-b-25*slope)/sig:null;
   const old3=price(s,when(a[i].d,-3));const r3=old3?Math.log(a[i].c/old3.c):null;
   const old5=price(s,when(a[i].d,-5));const r5=old5?Math.log(a[i].c/old5.c):null;
   const logReturns=[];for(let j=i-19;j<=i;j++)if(j>0)logReturns.push(Math.log(a[j].c/a[j-1].c));
   const mu=logReturns.reduce((v,x)=>v+x,0)/logReturns.length;
   const vol20=logReturns.length===20?Math.sqrt(logReturns.reduce((v,x)=>v+(x-mu)**2,0)/19):null;
   out.set(a[i].d,{score,annual,r2,z,r3,r5,vol20});
  }
 }
 const q90=new Map(daily.map(r=>[r.d,r]));
 const eventData=events.map(e=>{
  const s1=scores.get(e.top1)?.get(e.d),s2=scores.get(e.top2)?.get(e.d),before=when(e.d,-3);
  const p1=scores.get(e.top1)?.get(before),p2=scores.get(e.top2)?.get(before);
  const delta1=s1&&p1?s1.score-p1.score:null,delta2=s2&&p2?s2.score-p2.score:null;
  const rel=delta1!==null&&delta2!==null?delta2-delta1:null,dr2=s2&&p2?s2.r2-p2.r2:null;
  const active=delta2!==null&&rel!==null&&dr2!==null?(delta2>0&&rel>0&&dr2>0):null;
  const state=s1?.z===null||s1?.z===undefined?"missing":s1.z>=1?"positive":s1.z<=-1?"negative":"central";
  const joint=active!==null&&s1?.r3!==null&&s1?.r3!==undefined?(active&&(state==="positive"||(state==="negative"&&s1.r3<0))):null;
  const n=k=>e[k]!==""?Number(e[k]):null;
  const r=q90.get(e.d);
  const valid=!!e.top2&&n("top1_ret5")!==null&&n("top2_ret5")!==null&&s1&&s2&&s1.z!==null;
  return {d:e.d,s:e.top1,b:e.top2,E:+e.withdraw_e,valid:!!valid,state,z:s1?.z??null,r3:s1?.r3??null,r5:s1?.r5??null,vol1:s1?.vol20??null,vol2:s2?.vol20??null,
   score1:s1?.score??null,score2:s2?.score??null,delta1,delta2,rel,dr2,active,joint,
   qRatio:r?+r.D/(+r.Dbase):null,pDelta:r?(+r.pLoss5_full)-(+r.pLoss5_vol):null,
   a3:n("top1_ret3"),b3:n("top2_ret3"),a5:n("top1_ret5"),b5:n("top2_ret5"),a10:n("top1_ret10"),b10:n("top2_ret10"),mae1:n("mae5_top1"),mae2:n("mae5_top2"),corr:n("corr60"),switched:e.top1_switched5==="1"};
 });
 const good=eventData.filter(e=>e.valid);
 const avg=(a,f)=>a.length?a.reduce((s,x)=>s+f(x),0)/a.length:null;
 function summarise(a){const z=a.filter(x=>x.valid);return {n:a.length,valid:z.length,avgE:avg(z,x=>x.E),meanQ90Relative:avg(z,x=>x.qRatio),ret1:avg(z,x=>x.a5),ret2:avg(z,x=>x.b5),ret2NetCash:avg(z,x=>x.b5-.0012),spread:avg(z,x=>x.b5-x.a5),
  weightedGain:avg(z,x=>x.E*(x.b5-.0012)),mae1:avg(z,x=>x.mae1),mae2:avg(z,x=>x.mae2),tail1:z.length?z.filter(x=>x.mae1<=-.05).length/z.length:null,tail2:z.length?z.filter(x=>x.mae2<=-.05).length/z.length:null,
  beat2:z.length?z.filter(x=>x.b5>x.a5).length/z.length:null,
  corr:avg(z,x=>x.corr??0)};}
 const cells={};for(const st of ["positive","central","negative"])for(const active of [true,false])cells[st+"_"+active]=summarise(good.filter(x=>x.state===st&&x.active===active));
 const states=Object.fromEntries(["positive","central","negative"].map(k=>[k,summarise(good.filter(x=>x.state===k))]));
 const summary={metadata:{bars:barRows.length,total:events.length,good:good.length,invalid:eventData.filter(x=>!x.valid).map(x=>({d:x.d,top1:x.s,top2:x.b,state:x.state}))},cells,states,
  active:summarise(good.filter(x=>x.active)),nonActive:summarise(good.filter(x=>!x.active)),
  joint:summarise(good.filter(x=>x.joint)),nonJoint:summarise(good.filter(x=>!x.joint)),
  byYear:Object.fromEntries([...new Set(events.map(x=>x.d.slice(0,4)))].map(yr=>[yr,{positive:summarise(good.filter(x=>x.d.startsWith(yr)&&x.state==="positive")),central:summarise(good.filter(x=>x.d.startsWith(yr)&&x.state==="central")),active:summarise(good.filter(x=>x.d.startsWith(yr)&&x.active))}]))};
 // full daily portfolio with original Top1 archived return for main sleeve (missing day exactly as in Q1), Top2 OHLC open-to-open if different.
 const eventByDate=new Map(eventData.map(e=>[e.d,e])),dateRec=daily.map((r,i)=>({i,d:r.d,s:r.s,ret:Number(r.ret),E:r.s?Math.max(0,Math.min(1,(1-1.1*(+r.Dbase)/(+r.D))*Math.max(0,Math.min(1.8,1+2*((+r.pLoss5_full)-(+r.pLoss5_vol)))))):0}));
 const extraRet=(s,d)=>{
  const a=price(s,when(d,1)),b=price(s,when(d,2));return a&&b&&a.o>0?b.o/a.o-1:null;
 };
 function portfolio(policy,{noOil=false}={}){
  let nav=1,peak=1,mdd=0,prev={},active=null,starts=0,top2Starts=0,cashUnits=0,feeTotal=0,turn=0;
  const logs=[],byYear={};
  for(const r of dateRec){
   if(active&&r.i>active.end)active=null;
   if(!active&&r.s&&r.E>1e-5){
    const event=eventByDate.get(r.d);
    if(!event)throw Error("Missing frozen Q90 event "+r.d);
    const eligible=event.valid&&!noOil||event.valid&&! (r.s==="501018");
    let selected=eligible&&policy==="all"||eligible&&policy==="active"&&event.active||eligible&&policy==="joint"&&event.joint||eligible&&policy==="positive"&&event.state==="positive";
    const alt=selected?event.b:null;
    active={end:r.i+4,E:r.E,alt};
    starts++;if(alt)top2Starts++;
   }
   const w={};if(r.s){
    const E=active?active.E:0;
    w[r.s]=policy==="full"?1:1-E;
    if(policy!=="full"&&policy!=="cash"&&active?.alt)w[active.alt]=(w[active.alt]||0)+E;
   }else if(active?.alt)active.alt=null;
   for(const s of Object.keys(w))if(w[s]<1e-12)delete w[s];
   let ret=0;for(const [s,z]of Object.entries(w)){
    const dr=s===r.s?r.ret:extraRet(s,r.d);
    if(dr===null||!Number.isFinite(dr))throw Error("Missing forward "+r.d+" "+s);
    ret+=z*dr;
   }
   let delta=0;for(const s of new Set([...Object.keys(w),...Object.keys(prev)]))delta+=Math.abs((w[s]||0)-(prev[s]||0));
   const fee=.0006*delta,fac=1+ret-fee;
   if(!(fac>0))throw Error("Portfolio factor invalid "+r.d);
   const start=nav;nav*=fac;peak=Math.max(peak,nav);mdd=Math.min(mdd,nav/peak-1);feeTotal+=fee;turn+=delta;
   logs.push(Math.log(fac));const yr=r.d.slice(0,4);
   if(!byYear[yr])byYear[yr]={start,end:nav};byYear[yr].end=nav;
   if(r.s)cashUnits+=Math.max(0,1-Object.values(w).reduce((s,x)=>s+x,0));
   prev=w;
  }
  const cagr=Math.pow(nav,244/daily.length)-1;
  return {cagr,mdd,calmar:cagr/(-mdd),starts,top2Starts,cashUnits,feeTotal,turn,byYear:Object.fromEntries(Object.entries(byYear).map(([k,x])=>[k,x.end/x.start-1])),logs};
 }
 const portfolios={};for(const k of ["full","cash","all","active","joint","positive"])portfolios[k]=portfolio(k);
 portfolios.jointNoOil=portfolio("joint",{noOil:true});portfolios.positiveNoOil=portfolio("positive",{noOil:true});
 // Bootstrap by-year event-block; 4 consecutive exit events approx 20-session underlying block with overlap.
 let seed=0x421893,rand=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return(seed>>>0)/4294967296;};
 function resample(f,draws=2000){
  const years=[...new Set(good.map(x=>x.d.slice(0,4)))].sort().map(y=>good.filter(x=>x.d.startsWith(y)));
  const values=[];
  for(let k=0;k<draws;k++){
   let z=[];for(const a of years){for(let n=0;n<a.length;){const start=Math.floor(rand()*a.length);for(let j=0;j<4&&n<a.length;j++,n++)z.push(a[(start+j)%a.length]);}}
   values.push(f(z));
  }
  values.sort((a,b)=>a-b);const obs=f(good);
  return {mean:obs,ci95:[values[Math.floor(.025*draws)],values[Math.floor(.975*draws)]],pPositive:values.filter(x=>x>0).length/draws};
 }
 const effects={
  positiveMinusCentralSpread:resample(a=>{const p=a.filter(x=>x.state==="positive"),c=a.filter(x=>x.state==="central");return p.length&&c.length?avg(p,x=>x.b5-x.a5)-avg(c,x=>x.b5-x.a5):0;}),
  positiveSpread:resample(a=>{const p=a.filter(x=>x.state==="positive");return p.length?avg(p,x=>x.b5-x.a5):0;}),
  positiveNetVsCash:resample(a=>{const p=a.filter(x=>x.state==="positive");return p.length?avg(p,x=>x.b5-.0012):0;}),
  centralSpread:resample(a=>{const p=a.filter(x=>x.state==="central");return p.length?avg(p,x=>x.b5-x.a5):0;}),
  activeSpread:resample(a=>{const p=a.filter(x=>x.active);return p.length?avg(p,x=>x.b5-x.a5):0;})
 };
 const yrs=[...new Set(dateRec.map(x=>x.d.slice(0,4)))],byIdx=yrs.map(y=>dateRec.map((x,i)=>x.d.startsWith(y)?i:-1).filter(i=>i>=0));
 function bootPortfolio(a,b,rep=1800){
  const out=[];for(let t=0;t<rep;t++){
   let sum=0;for(const ids of byIdx){let j=0;while(j<ids.length){let start=Math.floor(rand()*ids.length);for(let k=0;k<20&&j<ids.length;k++,j++)sum+=a.logs[ids[(start+k)%ids.length]]-b.logs[ids[(start+k)%ids.length]];}}
   out.push(sum/daily.length*244);
  }out.sort((x,y)=>x-y);
  return {annualLogExcess:a.logs.reduce((s,x,i)=>s+x-b.logs[i],0)*244/daily.length,ci95:[out[Math.floor(.025*rep)],out[Math.floor(.975*rep)]],pPositive:out.filter(x=>x>0).length/rep};
 }
 const portfolioComparisons={allVsCash:bootPortfolio(portfolios.all,portfolios.cash),activeVsCash:bootPortfolio(portfolios.active,portfolios.cash),jointVsCash:bootPortfolio(portfolios.joint,portfolios.cash),positiveVsCashExploratory:bootPortfolio(portfolios.positive,portfolios.cash),positiveVsAllExploratory:bootPortfolio(portfolios.positive,portfolios.all)};
 const main={...summary,effects,portfolios:Object.fromEntries(Object.entries(portfolios).map(([k,{logs,...rest}])=>[k,rest])),portfolioComparisons};
 const evHeader=["date","top1","top2","E","valid","top1_state","top1_z26","top1_r3","top1_vol20","top2_vol20","top2_z26","top1_score3_delta","top2_score3_delta","relative_score3_delta","top2_r2_3_delta","active","joint","q90_ratio","p5_delta","top1_ret5","top2_ret5","top1_mae5","top2_mae5","past60_corr"];
 const eventCsv=evHeader.join(",")+"\n"+eventData.map(x=>[x.d,x.s,x.b,x.E,+x.valid,x.state,x.z??"",x.r3??"",x.vol1??"",x.vol2??"",x.b? scores.get(x.b)?.get(x.d)?.z??"":"",x.delta1??"",x.delta2??"",x.rel??"",x.dr2??"",x.active===null?"":+x.active,x.joint===null?"":+x.joint,x.qRatio??"",x.pDelta??"",x.a5??"",x.b5??"",x.mae1??"",x.mae2??"",x.corr??""].join(",")).join("\n")+"\n";
 return {main,eventCsv};
};
if(process.argv.length!==11)throw Error("Expected 9 input CSV paths: Q90, Q1 and seven yearly bars");
const result=audit(process.argv.slice(2).map(path=>fs.readFileSync(path,"utf8")));
console.log(JSON.stringify(result.main,null,2));
