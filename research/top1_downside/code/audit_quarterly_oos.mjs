// Recompute all robust statistics from stored quarterly OOS CSV without npm packages
// usage: node audit_quarterly_oos.mjs 20261120_quarterly_oos_predictions.csv
import fs from "node:fs";
const audit=function audit(csv){
 const lines=csv.trim().split("\n"),keys=lines.shift().split(",");
 const rows=lines.map(line=>{const vals=line.split(","),r={};for(let j=0;j<keys.length;j++){const k=keys[j];r[k]=["date","symbol","fold"].includes(k)?vals[j]:vals[j]===""?null:+vals[j];}return r;}).sort((a,b)=>a.date.localeCompare(b.date));
 const risk=rows.filter(r=>r.symbol&&r.loss!==null);
 const models=["vol","ols","hot","down","uni","market","rollOls","rollUni","rollVol"];
 const pairs=[["ols","uni"],["hot","uni"],["down","uni"],["uni","market"],["vol","uni"],["rollOls","rollUni"],["ols","hot"],["ols","down"]];
 const pin=(y,d)=>{const a=y-d;return a>=0?.9*a:-.1*a};
 const quant=(aa,p)=>{const a=[...aa].sort((x,y)=>x-y),q=p*(a.length-1),i=Math.floor(q);return a[i]+(a[Math.min(i+1,a.length-1)]-a[i])*(q-i)};
 const years=[...new Set(rows.map(x=>x.date.slice(0,4)))].sort();
 const groupsByYear=Object.fromEntries(years.map(y=>[y,rows.map((r,i)=>r.date.slice(0,4)===y?i:-1).filter(i=>i>=0)]));
 const evIdx=rows.findIndex(x=>x.date==="20261103"),shockDays=new Set(evIdx>=0?rows.slice(Math.max(0,evIdx-5),evIdx+6).map(x=>x.date):[]);
 const stats=(a)=>{const o={n:a.length};for(const m of models)o[m]={pinball:a.length?a.reduce((z,r)=>z+pin(r.loss,r[m]),0)/a.length:null,coverage:a.length?a.filter(r=>r.loss<=r[m]).length/a.length:null};return o};
 const samples={
  all:stats(risk),noOil:stats(risk.filter(x=>x.symbol!=="501018")),onlyOil:stats(risk.filter(x=>x.symbol==="501018")),
  excludeNov3PlusMinus5:stats(risk.filter(x=>!shockDays.has(x.date))),
  year2026:stats(risk.filter(x=>x.date.startsWith("2026"))),
  year2026NoOil:stats(risk.filter(x=>x.date.startsWith("2026")&&x.symbol!=="501018"))
 };
 const annually=Object.fromEntries(years.map(y=>[y,stats(risk.filter(r=>r.date.startsWith(y)))]));
 const annualDeltas=Object.fromEntries(years.map(y=>[y,Object.fromEntries(pairs.map(([a,b])=>[`${a}-${b}`,annually[y][a].pinball-annually[y][b].pinball]))]));
 const thin={};for(let offset=0;offset<5;offset++){
  const c=stats(rows.filter((r,i)=>i%5===offset&&r.symbol));
  thin[offset]={n:c.n,ols:c.ols.pinball,hot:c.hot.pinball,down:c.down.pinball,uni:c.uni.pinball,improvementToBest:Math.min(c.hot.pinball,c.down.pinball)-c.uni.pinball};
 }
 function portfolio(name,options={}){
  let nav=1,peak=1,mdd=0,turn=0,cost=0,exitStarts=0,active=0,exSum=0,remain=0,E=0,prevSymbol=null,prevW=0,upsideMiss=0,downsideAvoid=0;
  const logReturns=[],yr={};
  for(const r of rows){
   let w=r.symbol?1:0;
   if(remain>0){if(r.symbol)w=1-E;remain--;}
   else if(r.symbol&&name!=="full"){
    const base=r[name.startsWith("roll")?"rollVol":"vol"],pred=r[name];
    let e=0;
    if(!(options.noOil&&r.symbol==="501018")&&!(options.noShock&&shockDays.has(r.date))&&base>0&&pred>0)e=Math.max(0,Math.min(1,1-1.1*base/pred));
    if(e>1e-4){E=e;w=1-e;remain=4;exitStarts++;exSum+=e;}else E=0;
   }
   const v=r.symbol===prevSymbol?Math.abs(w-prevW):w+prevW,fee=.0006*v,fac=1+w*r.ret-fee;
   if(!(fac>0))throw Error("Invalid net daily factor "+r.date);
   const before=nav;nav*=fac;peak=Math.max(nav,peak);mdd=Math.min(mdd,nav/peak-1);
   const y=r.date.slice(0,4);if(!yr[y])yr[y]={first:before,last:nav};else yr[y].last=nav;
   if(r.symbol&&w<.999999){active++;if(r.ret>0)upsideMiss+=(1-w)*r.ret;else downsideAvoid+=(1-w)*(-r.ret);}
   turn+=v;cost+=fee;logReturns.push(Math.log(fac));prevSymbol=r.symbol;prevW=w;
  }
  const cagr=nav**(244/rows.length)-1;
  return {cagr,total:nav-1,mdd,calmar:mdd===0?0:cagr/(-mdd),turn,cost,exitStarts,active,avgExit:exitStarts?exSum/exitStarts:0,upsideMiss,downsideAvoid,
   perYear:Object.fromEntries(Object.entries(yr).map(([y,z])=>[y,z.last/z.first-1])),logReturns};
 }
 const pf={};for(const k of ["full","vol","ols","hot","down","uni","market","rollOls","rollUni"])pf[k]=portfolio(k);
 const scenarios={uniNoOil:portfolio("uni",{noOil:true}),marketNoOil:portfolio("market",{noOil:true}),rollUniNoOil:portfolio("rollUni",{noOil:true}),uniNoCrashInitiation:portfolio("uni",{noShock:true})};
 let rng=0x51310051;
 function rand(){rng^=rng<<13;rng^=rng>>>17;rng^=rng<<5;return (rng>>>0)/4294967296}
 const N=1600,block=20;
 const bootKeys=[...pairs.map(([a,b])=>"risk:"+a+"-"+b),...pairs.map(([a,b])=>"nonOil:"+a+"-"+b),...["uni","market","hot","down","rollUni"].map(s=>"return:"+s)];
 const draws=Object.fromEntries(bootKeys.map(k=>[k,[]]));
 for(let b=0;b<N;b++){
  const sums=Object.fromEntries(bootKeys.map(x=>[x,0]));let nr=0,nNoOil=0;
  for(const y of years){
   const ids=groupsByYear[y],count=ids.length;
   let used=0;
   while(used<count){
    const start=Math.floor(rand()*count);
    for(let k=0;k<block&&used<count;k++,used++){
     const j=ids[(start+k)%count],r=rows[j];
     if(r.symbol){
      nr++;
      for(const [a,c] of pairs)sums["risk:"+a+"-"+c]+=pin(r.loss,r[a])-pin(r.loss,r[c]);
      if(r.symbol!=="501018"){nNoOil++;for(const [a,c] of pairs)sums["nonOil:"+a+"-"+c]+=pin(r.loss,r[a])-pin(r.loss,r[c]);}
     }
     for(const m of ["uni","market","hot","down","rollUni"])sums["return:"+m]+=pf[m].logReturns[j]-pf.full.logReturns[j];
    }
   }
  }
  for(const k of bootKeys)draws[k].push(sums[k]/(k.startsWith("risk:")?nr:k.startsWith("nonOil:")?nNoOil:rows.length)*(k.startsWith("return:")?244:1));
 }
 const boot={seed:"0x51310051",N,blockDays:block,stratified:"calendar years",statistics:{}};
 for(const k of bootKeys){
  let estimate;
  if(k.startsWith("return:")){
   const name=k.slice(7);let d=0;for(let i=0;i<rows.length;i++)d+=pf[name].logReturns[i]-pf.full.logReturns[i];
   estimate=d/rows.length*244;
  }else{
   const [group,rest]=k.split(":"),[a,b]=rest.split("-"),arr=group==="risk"?risk:risk.filter(r=>r.symbol!=="501018");
   estimate=arr.reduce((z,r)=>z+pin(r.loss,r[a])-pin(r.loss,r[b]),0)/arr.length;
  }
  const vals=draws[k];
  boot.statistics[k]={estimate,CI95:[quant(vals,.025),quant(vals,.975)],probPositive:vals.filter(x=>x>0).length/N};
 }
 return {
  counts:{rows:rows.length,risk:risk.length,oil:risk.filter(x=>x.symbol==="501018").length,shockDates:shockDays.size,shockDate:evIdx<0?null:rows[evIdx]},
  samples,annually,annualDeltas,thin,boot,
  portfolio:Object.fromEntries(Object.entries(pf).map(([k,v])=>[k,((({logReturns,...z})=>z)(v))])),
  scenarios:Object.fromEntries(Object.entries(scenarios).map(([k,v])=>[k,((({logReturns,...z})=>z)(v))]))
 };
};
if(!process.argv[2])throw Error("Provide prediction CSV filepath");
console.log(JSON.stringify(audit(fs.readFileSync(process.argv[2],"utf-8")),null,2));
