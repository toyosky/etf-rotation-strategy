import fs from "node:fs";
// Usage: node q9_void_q90_overlay.mjs <Void_history.csv> <Q90_predictions.csv> <q1_bars_2021.csv> ... <q1_bars_2026.csv>
const replayVoidQ90=function replayVoidQ90(inputs,repairMissing=true){
 const parse=s=>{const [h,...lines]=s.trim().split(/\r?\n/),keys=h.split(",");return lines.map(line=>Object.fromEntries(line.split(",").map((z,j)=>[keys[j],z])))};
 const V=parse(inputs[0]),Q=parse(inputs[1]),qm=new Map(Q.map(x=>[x.d,x]));
 const b=inputs.slice(2).flatMap(parse).filter(x=>x.s==="511220"||x.symbol==="511220").sort((a,b)=>String(a.d??a.date).localeCompare(String(b.d??b.date)));
 const bonds=new Map();let countBondRef=0;const bondCalendar=b.map(x=>({date:String(x.d??x.date).replaceAll("-",""),open:+x.o||+x.open})),bondDates=bondCalendar.map(x=>x.date),price=new Map(bondCalendar.map(x=>[x.date,x.open]));
 for(let i=0;i<bondCalendar.length;i++){const day=bondCalendar[i].date,next=bondCalendar[i+1]?.date;if(next&&bondCalendar[i].open>0&&bondCalendar[i+1].open>0)bonds.set(day,bondCalendar[i+1].open/bondCalendar[i].open-1);}
 const daily=V.filter(v=>qm.has(v.date.replaceAll("-",""))).map((v,i)=>{
  const date=v.date.replaceAll("-",""),q=qm.get(date),same=v.target===q.s;
  const E=q.s?Math.max(0,Math.min(1,(1-1.1*(+q.Dbase)/(+q.D))*Math.max(0,Math.min(1.8,1+2*((+q.pLoss5_full)-(+q.pLoss5_vol)))))):0;
  const valid=!!v.target&&v.target!=="511220"&&v.target!=="513500"&&same;
  return {i,date,iso:v.date,asset:v.target,state:v.state,decision:v.decision,
   missing:v.missing==="1",rawE:E,qualifies:valid,source:q.s,
   targetE:valid&&E>=.05?E:0,
   originalGross:+v.gross,gross:v.missing==="1"&&repairMissing&&same?(+q.ret):(+v.gross),
   qGross:same?+q.ret:null,q90r:(+q.D)/(+q.Dbase)};
 });
 const mismatches=daily.filter(x=>x.asset!==x.source);
 const bondCheck=daily.filter(x=>x.asset==="511220"&&bonds.has(x.date)&&Math.abs(x.originalGross-bonds.get(x.date))>1e-7).map(x=>({date:x.date,voidGross:x.originalGross,bondGross:bonds.get(x.date)}));
 const types=["void","daily5","s1","lock5","daily5Bond"];
 const sim={};
 for(const id of types){
  let nav=1,high=1,mdd=0,peakDate="",troughDate="",weights={},prevAsset=null;
  let entryE=0,confirm=0,lockEnd=-1,lockSymbol=null,changes=0,sellChanges=0,buyChanges=0,tickets=0,meanE=0,opp=0,feeSum=0,turnSum=0,positiveValid=0,riskHeld=0;
  let voidDays=0,bondTargetDays=0,eligibleDays=0,eligibleSignalDays=0;
  let missingGross=0,forcedClose=0,exposuresByYear={};
  const data=[],years={};
  for(const x of daily){
   const before=entryE,riskEligible=x.qualifies,priorAsset=prevAsset;
   if(x.state==="DEFENSIVE_VOID")voidDays++;
   if(x.asset==="511220")bondTargetDays++;
   if(riskEligible){eligibleDays++;if(x.targetE>1e-10)eligibleSignalDays++;}
   // drifted portfolio weights entering next signal execution; if same asset and no instruction, no rebalance.
   const oldRiskWeight=x.asset&&weights[x.asset]||0;
   const oldDefensiveWeight=weights["511220"]||0,oldCashWeight=Math.max(0,1-Object.values(weights).reduce((a,b)=>a+b,0));
   // For Q90 risk-sleeve under same risk symbol, account E must reflect actual cash or bond weight, not simply previous nominal.
   const currentE=(id==="daily5Bond"&&riskEligible)?oldDefensiveWeight:oldCashWeight;
   const previousCoverage=prevAsset&&prevAsset!=="511220"&&prevAsset!=="513500";
   let newE=0,shouldRebalance=false;
   if(id==="void"){newE=0;entryE=0;confirm=0;lockEnd=-1;}
   else if(!riskEligible){
    newE=0;entryE=0;confirm=0;lockEnd=-1;lockSymbol=null;
    if(before>1e-12)forcedClose++;
   }else if(id==="lock5"){
    // if same symbol and lock active keep previous E until expiry, otherwise choose fresh episode
    if(x.i>lockEnd||lockSymbol!==x.asset){
     entryE=x.rawE>1e-5?x.rawE:0;
     lockSymbol=x.asset;
     lockEnd=entryE>1e-5?x.i+4:-1;
    }
    newE=entryE;
   }else if(id==="daily5"||id==="daily5Bond"){
    if(Math.abs(x.targetE-currentE)>=.05-1e-12)entryE=x.targetE;
    else entryE=currentE;
    newE=entryE;
   }else if(id==="s1"){
    if(x.targetE>=currentE+.05-1e-12){entryE=x.targetE;confirm=0;}
    else if(x.targetE<=currentE-.05+1e-12){confirm++;entryE=confirm>=2?x.targetE:currentE;if(confirm>=2)confirm=0;}
    else{confirm=0;entryE=currentE;}
    newE=entryE;
   }
   const riskRoute=!!x.asset&&x.asset!=="511220"&&x.asset!=="513500";
   if(!riskRoute)newE=0;
   // Act: position in Void target 1-E; leftover E cash or 511220. Nonrisk 511220 & 513500 follow full Void.
   const w={};if(x.asset){w[x.asset]=1-newE;}
   if(id==="daily5Bond"&&newE>0)w["511220"]=(w["511220"]||0)+newE;
   // No instrument switch & target E same actual drifted E => retain holdings, do NOT force small drift trades.
   // If asset switched, force full target routing; if target E changes ≥5pp (or forced cover close), rebalance.
   if(x.asset===priorAsset && id!=="void" && riskRoute && riskEligible && ((id==="daily5"||id==="daily5Bond"||id==="s1")&&Math.abs(newE-currentE)<1e-12)){
    // leave drifted weights unchanged
    for(const key of Object.keys(w))delete w[key];
    for(const [key,value] of Object.entries(weights))w[key]=value;
   }
   // Baseline if asset stays same, w=100%; baseline drift in the same single security is 100%.
   // For nonrisk route, always target full 100%; if already full single asset, w no change.
   let turnover=0,fee=0,orders=0;
   for(const s of new Set([...Object.keys(weights),...Object.keys(w)])){
    const delta=(w[s]||0)-(weights[s]||0);if(Math.abs(delta)<1e-10)continue;
    turnover+=Math.abs(delta);orders++;
   }
   fee=turnover*.0006;
   const trueE=(riskRoute?(id==="daily5Bond"?(w["511220"]||0):Math.max(0,1-Object.values(w).reduce((a,b)=>a+b,0))):0);
   if(Math.abs(trueE-before)>1e-8){changes++;if(trueE>before)sellChanges++;else buyChanges++;}
   entryE=trueE;
   if(x.missing)missingGross++;
   if(x.asset==="511220"&&id!=="daily5Bond"&&x.missing)throw Error("missing bond source");
   let gross=0;for(const [s,weight] of Object.entries(w)){
    const ret=s===x.asset?x.gross:s==="511220"?bonds.get(x.date):null;
    if(ret===undefined||ret===null||!Number.isFinite(ret))throw Error("missing bond rate at "+x.date+" "+s);
    gross+=weight*ret;
   }
   const factor=1+gross-fee;if(factor<=0)throw Error("negative NAV on "+x.date);
   const oldNav=nav;nav*=factor;
   if(nav>high){high=nav;peakDate=x.date;}
   if(nav/high-1<mdd){mdd=nav/high-1;troughDate=x.date;}
   const year=x.date.slice(0,4),y=years[year]??(years[year]={start:oldNav,end:nav,peak:oldNav,mdd:0,days:0,eligible:0,adjustments:0,cash:0,fee:0});
   y.end=nav;y.peak=Math.max(y.peak,nav);y.mdd=Math.min(y.mdd,nav/y.peak-1);y.days++;y.eligible+=+riskEligible;y.cash+=trueE;y.fee+=fee;if(Math.abs(trueE-before)>1e-8)y.adjustments++;
   meanE+=trueE;tickets+=orders;feeSum+=fee;turnSum+=turnover;
   data.push({date:x.date,asset:x.asset,q90Asset:x.source,qualifies:x.qualifies,rawE:x.rawE,executedE:trueE,nav,gross,fee,weightRisk:w[x.asset]||0,weightBond:w["511220"]||0,weightCash:Math.max(0,1-Object.values(w).reduce((a,b)=>a+b,0)),ret:x.gross,state:x.state,missing:x.missing});
   // Mark to market drift at next open: cash weight fixed in nominal value, assets grow by gross.
   const next={};for(const [s,weight]of Object.entries(w)){
    const ret=s===x.asset?x.gross:s==="511220"?bonds.get(x.date):null;
    next[s]=weight*(1+ret)/(1+gross); // safe: before fees, fees deducted separately from NAV (small approximation)
   }
   weights=next;prevAsset=x.asset;
  }
  const rets=data.map((x,i)=>x.nav/(i?data[i-1].nav:1)-1),retAvg=rets.reduce((s,x)=>s+x,0)/rets.length;
  const annualVol=Math.sqrt(rets.reduce((s,x)=>s+(x-retAvg)**2,0)/(rets.length-1))*Math.sqrt(244);
  const cagr=nav**(244/daily.length)-1;
  sim[id]={cagr,mdd,nav,annualVol,calmar:cagr/-mdd,peakDate,troughDate,changes,sellChanges,buyChanges,tickets,feeSum,turnover:turnSum,meanE:meanE/daily.length,
   years:Object.fromEntries(Object.entries(years).map(([k,y])=>[k,{ret:y.end/y.start-1,mdd:y.mdd,days:y.days,eligible:y.eligible,adjustments:y.adjustments,avgE:y.cash/y.days,fees:y.fee}])),data};
 }
 // paired 20-trading-day block yearly comparisons. No boot MDD difference; block counts avoid independent assumption.
 const yy=[...new Set(daily.map(x=>x.date.slice(0,4)))],groups=yy.map(y=>daily.flatMap((r,i)=>r.date.slice(0,4)===y?[i]:[]));
 let seed=100234;const rng=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return(seed>>>0)/4294967296;};
 const comparisons={};
 for(const a of ["daily5","s1","lock5","daily5Bond"]){
  const A=sim[a].data,B=sim.void.data,di=A.map((r,i)=>Math.log(r.nav/(i?A[i-1].nav:1))-Math.log(B[i].nav/(i?B[i-1].nav:1))),obs=di.reduce((s,x)=>s+x,0)*244/daily.length;
  const n=2400,boot=[];for(let z=0;z<n;z++){let s=0;for(const g of groups)for(let i=0;i<g.length;){let at=Math.floor(rng()*g.length);for(let k=0;k<20&&i<g.length;k++,i++)s+=di[g[(at+k)%g.length]];}boot.push(s*244/daily.length);}
  boot.sort((x,y)=>x-y);comparisons[a]={annualLogExcess:obs,CI95:[boot[Math.floor(n*.025)],boot[Math.floor(n*.975)]],pPositive:boot.filter(x=>x>0).length/n};
 }
 const q90Pos=daily.filter(x=>x.rawE>1e-5),eligible=daily.filter(x=>x.qualifies),positiveOnEligible=eligible.filter(x=>x.targetE>0);
 const result={
  period:{from:daily[0].date,to:daily.at(-1).date,days:daily.length,rawQ90Days:q90Pos.length,eligibleDays:eligible.length,rawMatchedDays:daily.filter(x=>x.asset===x.source).length,
    currentVoidDays:daily.filter(x=>x.state==="DEFENSIVE_VOID").length,cashRouteDays:daily.filter(x=>x.asset==="511220").length,carrierRouteDays:daily.filter(x=>x.asset==="513500").length,
    positiveRawQ90: q90Pos.length,positiveEstrict:positiveOnEligible.length,misses:daily.filter(x=>x.missing).map(x=>({date:x.date,asset:x.asset,originalGross:x.originalGross,imputedGross:x.gross})),bondDataRef:bondCalendar.length,bondReturnConflicts:bondCheck.slice(0,15),bondReturnConflictsN:bondCheck.length
  },scenario:Object.fromEntries(Object.entries(sim).map(([k,{data,...v}])=>[k,v])),comparisons};
 const csv=[
 "date,void_target,q90_asset,state,matched,raw_q90_E,void_nav,daily_nav,s1_nav,lock_nav,via_bond_nav,daily_E,s1_E,lock_E,missing_flag",
 ...daily.map((r,i)=>[r.date,r.asset,r.source,r.state,+r.qualifies,r.rawE,sim.void.data[i].nav,sim.daily5.data[i].nav,sim.s1.data[i].nav,sim.lock5.data[i].nav,sim.daily5Bond.data[i].nav,sim.daily5.data[i].executedE,sim.s1.data[i].executedE,sim.lock5.data[i].executedE,+r.missing].join(","))
 ].join("\n")+"\n";
 return {result,csv};
};
const files=process.argv.slice(2);if(files.length!==8)throw Error("Need 8 input CSVs: Void, Q90, 2021-2026 bond bars");
const primary=replayVoidQ90(files.map(p=>fs.readFileSync(p,"utf8")),true);
const sensitivity=replayVoidQ90(files.map(p=>fs.readFileSync(p,"utf8")),false);
console.log(JSON.stringify({primary:primary.result,missingZeroSensitivity:sensitivity.result.scenario},null,2));
