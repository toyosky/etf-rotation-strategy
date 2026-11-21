import fs from "node:fs";
// node q10_formal_void_q90_replay.mjs <void_history.csv> <q90_oos_daily.csv>
const runFormalVoid=function runFormalVoid(inputs){
 function parse(src){const [h,...ls]=src.trim().split(/\r?\n/),k=h.split(",");return ls.map(l=>Object.fromEntries(l.split(",").map((v,i)=>[k[i],v])));}
 const source=parse(inputs[0]),Q=parse(inputs[1]),qmap=new Map(Q.map(q=>[q.d,q]));
 const riskSymbols=new Set(["159934","159985","161226","513100","159957","159509","513290","159529","159981","501018","513530","164824","511380","512800"]);
 const daily=source.filter(x=>qmap.has(x.date.replace(/-/g,""))).map((v,i)=>{
  const date=v.date.replace(/-/g,""),q=qmap.get(date),t=v.target,nonVoid=v.state==="NON_VOID";
  const rawE=q.s?Math.max(0,Math.min(1,(1-1.1*(+q.Dbase)/(+q.D))*Math.max(0,Math.min(1.8,1+2*((+q.pLoss5_full)-(+q.pLoss5_vol)))))):0;
  const compatible=nonVoid&&riskSymbols.has(t)&&q.s===t;
  const repairedGross=v.missing==="1"&&v.target===q.s?+q.ret:+v.gross;
  if(v.missing==="1"&&v.target!==q.s)throw Error(`Missing gross cannot be repaired for ${date}`);
  const unclassified=t&&!riskSymbols.has(t)&&!["511220","513500"].includes(t);
  if(unclassified)throw Error(`Unknown formal route ${date} ${t}`);
  return {date,year:date.slice(0,4),index:i,asset:t,void:v.state==="DEFENSIVE_VOID",decision:v.decision,compatible,rawTop:q.s,
   E:rawE,Ef:rawE>=.05?rawE:0,rawPositive:rawE>=.05,ret:repairedGross,rawRet:+v.gross,
   missing:v.missing==="1",v1:v.v1Decision,rawSourceRet:q.s===t?+q.ret:null};
 });
 if(daily.length!==1419||daily[0].date!=="20210104"||daily.at(-1).date!=="20261112")throw Error("Data alignment failure");
 if(daily.filter(x=>x.void).length!==445)throw Error("Void state count changed");
 const modeSpecs=[{name:"baseline",kind:"base"},{name:"daily5",kind:"daily"},{name:"s1_two_confirm_oneshot",kind:"s1"}];
 const fees=[{name:"sixBp",rate:.0006,min:0,extra:0},{name:"min5yuan",rate:.0006,min:5/20000,extra:0},{name:"min5plus4bp",rate:.0006,min:5/20000,extra:.0004}];
 const res={},allPaths={};
 for(const cost of fees)for(const mode of modeSpecs){
  let asset=null,assetValue=0,cash=1,peak=1,mdd=0,peakDate=null,lowDate=null,cumFees=0,tickets=0,buyOrders=0,sellOrders=0,tradeDays=0,notional=0,voidTrades=0,voidFreezeBreaches=0;
  let q90Decrease=0,q90Increase=0,q90Entries=0,plainTrades=0,sellClipped=0,confirm=0,prevVoid=false;
  let eligibleDays=0,positiveDays=0,missingSameSymbol=0,voidEntries=0,routeChangesInVoid=0,voidEntersWithPreviousQ90Cash=0,avgCash=0,avgRisk=0,assetSwitches=0;
  const series=[],yrs={},riskEByYear={},abnormal=[];
  const charge=amt=>amt>1e-14?Math.max(amt*cost.rate,cost.min)+amt*cost.extra:0;
  function sellAll(){
   if(!asset||assetValue<1e-14){asset=null;assetValue=0;return 0;}
   const value=assetValue,fee=charge(value);cash+=value-fee;asset=null;assetValue=0;
   cumFees+=fee;tickets++;sellOrders++;notional+=value;return fee;
  }
  function transact(target, targetW){
   const from=asset,nav=cash+assetValue,desired=Math.max(0,Math.min(1,targetW))*nav;
   if(!target){return sellAll();}
   let trade=0,fee=0;
   if(asset&&asset!==target){fee+=sellAll();trade++;}
   if(!asset){asset=target;assetValue=0;}
   if(assetValue>desired+1e-12){
    const amount=assetValue-desired,f=charge(amount);assetValue-=amount;cash+=amount-f;
    cumFees+=f;fee+=f;tickets++;sellOrders++;notional+=amount;trade++;
   }else if(assetValue<desired-1e-12){
    const request=desired-assetValue;
    let low=0,high=Math.min(request,cash);
    for(let k=0;k<55;k++){const mid=(low+high)/2;if(mid+charge(mid)<=cash)low=mid;else high=mid;}
    const amount=low;
    if(amount>1e-10){const f=charge(amount);cash-=amount+f;assetValue+=amount;cumFees+=f;fee+=f;tickets++;buyOrders++;notional+=amount;trade++;} 
    if(request-amount>1e-6)sellClipped++;
   }
   if(!assetValue){asset=null;}
   return trade;
  }
  for(const d of daily){
   const beforeAsset=asset,beforeValue=assetValue,beforeCash=cash,preNav=assetValue+cash;
   let instruction="HOLD",targetW=assetValue/preNav,actE=0,wantedE=0;
   const enterVoid=d.void&&!prevVoid,exitVoid=!d.void&&prevVoid;
   if(enterVoid){voidEntries++;confirm=0;if(beforeAsset&&beforeCash/preNav>=.05)voidEntersWithPreviousQ90Cash++;}
   if(exitVoid)confirm=0;
   if(d.void){
    // Formal asset route decides. If unchanged, keep exact shares and cash.
    // Prior cash but formal Void started a base-target at entry: follow original route.
    if(d.asset!==asset){if(!enterVoid)routeChangesInVoid++;instruction="FORMAL_VOID_ROUTE";transact(d.asset,d.asset?1:0);if(beforeAsset!==d.asset)assetSwitches++;}
    else instruction="VOID_PRESERVE_SHARES";
    if(d.asset===beforeAsset&&Math.abs(assetValue-beforeValue)>1e-13)voidFreezeBreaches++;
   }else if(!d.asset){
    if(asset){instruction="FORMAL_CASH";transact(null,0);}
    confirm=0;
   }else if(!d.compatible||mode.kind==="base"){
    // For no valid same-ETF prediction, if retaining same asset, freeze shares as-is.
    // If formal new ETF, route full width as original strategy prescribes.
    if(d.asset!==asset){
     instruction="FORMAL_NEW_NO_Q90";transact(d.asset,1);assetSwitches++;
    }else instruction=mode.kind==="base"?"FORMAL_HOLD":"PIT_Q90_MISSING_PRESERVE";
    if(!d.compatible&&mode.kind!=="base")missingSameSymbol++;
    confirm=0;
   }else {
    eligibleDays++;if(d.Ef>=.05)positiveDays++;
    wantedE=d.Ef;
    if(d.asset!==asset){
     instruction="Q90_NEW_ETF";transact(d.asset,1-wantedE);assetSwitches++;confirm=0;q90Entries++;
    }else {
     const actualE=1-assetValue/preNav;
     if(mode.kind==="daily"){
      const difference=wantedE-actualE;
      if(Math.abs(difference)>=.05-1e-12){
       instruction=difference>0?"Q90_REDUCE":"Q90_RESTORE";
       transact(d.asset,1-wantedE);
       if(difference>0)q90Decrease++;else q90Increase++;
      }
     }else if(mode.kind==="s1"){
      const difference=wantedE-actualE;
      if(difference>=.05-1e-12){
       instruction="Q90_FAST_REDUCE";transact(d.asset,1-wantedE);q90Decrease++;confirm=0;
      }else if(difference<=-.05+1e-12){
       confirm++;if(confirm>=2){
        instruction="Q90_CONFIRMED_RESTORE";transact(d.asset,1-wantedE);q90Increase++;confirm=0;
       }else instruction="Q90_RESTORE_CONFIRM_WAIT";
      }else{confirm=0;}
     }
    }
   }
   if(!d.void&&d.compatible&&mode.kind==="base"&&d.asset!==asset)throw Error("bad baseline");
   if(d.void&&instruction.startsWith("Q90_"))throw Error("Void Q90 action at "+d.date);
   if(d.asset===asset){assetValue*=1+d.ret;}else if(asset!==null){throw Error("route mismatch "+d.date);}
   const nav=assetValue+cash;if(!(nav>0)||!Number.isFinite(nav))throw Error("bad portfolio "+d.date+" "+mode.name);
   if(nav>peak){peak=nav;peakDate=d.date;}
   const dd=nav/peak-1;if(dd<mdd){mdd=dd;lowDate=d.date;}
   const currentRisk=asset&&riskSymbols.has(asset)?assetValue/nav:0,actualCash=cash/nav;
   avgCash+=actualCash;avgRisk+=currentRisk;
   if(instruction!=="HOLD"&&!["FORMAL_HOLD","VOID_PRESERVE_SHARES","PIT_Q90_MISSING_PRESERVE","Q90_RESTORE_CONFIRM_WAIT"].includes(instruction))tradeDays++;
   const year=d.year,y=yrs[year]??(yrs[year]={first:preNav,last:nav,peak:preNav,mdd:0,days:0,beginCash:0,endingCash:0,avgCash:0,tradeDays:0,q90Reduces:0,q90Restores:0,voidDays:0,voidEntries:0,voidRoute:0,fees:0});
   y.last=nav;y.peak=Math.max(y.peak,nav);y.mdd=Math.min(y.mdd,nav/y.peak-1);y.days++;y.avgCash+=actualCash;y.endingCash=actualCash;
   if(instruction.includes("REDUCE"))y.q90Reduces++;
   if(instruction.includes("RESTORE"))y.q90Restores++;
   if(d.void)y.voidDays++;
   if(enterVoid)y.voidEntries++;
   if(instruction==="FORMAL_VOID_ROUTE")y.voidRoute++;
   const feeDay=preNav+(d.asset===beforeAsset?beforeValue*d.ret:0)-nav; // inaccurate after new asset; only used for validation not report
   const nextWeight=assetValue/nav;
   series.push({date:d.date,year,asset:d.asset,priorAsset:beforeAsset,void:d.void,decision:d.decision,signal:d.compatible,
    top1:d.rawTop,rawE:d.E,desiredE:d.compatible?d.Ef:null,actualCashWeight:actualCash,actualAssetWeight:nextWeight,
    instruction,enteredVoid:enterVoid,exitedVoid:exitVoid,pretradeWeight:beforeValue/preNav,cashBefore:beforeCash/preNav,
    nav,logret:Math.log(nav/preNav),grossReturn:d.ret,missing:d.missing,confirmedCounter:confirm});
   prevVoid=d.void;
  }
  const n=daily.length,NAV=cash+assetValue,CAGR=NAV**(244/n)-1,lr=series.map(x=>Math.expm1(x.logret)),mean=lr.reduce((a,b)=>a+b,0)/n,
    vol=Math.sqrt(lr.reduce((a,b)=>a+(b-mean)**2,0)/(n-1))*Math.sqrt(244);
  const summary={CAGR,MDD:mdd,Calmar:CAGR/-mdd,NAV,annualVol:vol,peakDate,troughDate:lowDate,fees:cumFees,
   tickets,buyOrders,sellOrders,tradeDays,notional,voidTrades,voidFreezeBreaches,voidEntries,routeChangesInVoid,
   voidEntersWithPreviousQ90Cash,q90Decrease,q90Increase,q90Entries,missingSameSymbol,eligibleDays,positiveDays,
   avgCash:avgCash/n,avgRisk:avgRisk/n,assetSwitches,
   years:Object.fromEntries(Object.entries(yrs).map(([yr,y])=>[yr,{return:y.last/y.first-1,MDD:y.mdd,days:y.days,voidDays:y.voidDays,voidEntries:y.voidEntries,voidRoute:y.voidRoute,q90Reduces:y.q90Reduces,q90Restores:y.q90Restores,avgCash:y.avgCash/y.days}]))};
  res[`${mode.name}__${cost.name}`]=summary;
  allPaths[`${mode.name}__${cost.name}`]=series;
 }
 const base=allPaths["baseline__sixBp"],yearGroups=[...new Set(daily.map(x=>x.year))].map(y=>daily.flatMap((x,i)=>x.year===y?[i]:[]));
 const boot={};let seed=217991;function rand(){seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return(seed>>>0)/4294967296;}
 function confidence(a,b,n=2200){const deltas=a.map((x,i)=>x.logret-b[i].logret),obs=deltas.reduce((s,x)=>s+x,0)*244/a.length,dist=[];
  for(let r=0;r<n;r++){let sum=0;for(const indices of yearGroups){let pos=0;while(pos<indices.length){const st=Math.floor(rand()*indices.length);for(let j=0;j<20&&pos<indices.length;j++,pos++)sum+=deltas[indices[(st+j)%indices.length]];}}dist.push(sum*244/a.length);}
  dist.sort((a,b)=>a-b);return {annualLogExcess:obs,CI95:[dist[Math.floor(.025*n)],dist[Math.floor(.975*n)]],positiveFraction:dist.filter(x=>x>0).length/n};
 }
 for(const cost of fees){const get=m=>allPaths[`${m}__${cost.name}`];boot[cost.name]={
  dailyVsVoid:confidence(get("daily5"),get("baseline")),s1VsVoid:confidence(get("s1_two_confirm_oneshot"),get("baseline")),
  s1VsDaily:confidence(get("s1_two_confirm_oneshot"),get("daily5"))
 }}
 const pa=allPaths["daily5__sixBp"],ps=allPaths["s1_two_confirm_oneshot__sixBp"];
 const deltaByDay=pa.map((x,i)=>({date:x.date,year:x.year,asset:x.asset,void:x.void,rawE:x.rawE,deltaLog:x.logret-base[i].logret,entry:x.enteredVoid,signal:x.signal,action:x.instruction,baselineNAV:base[i].nav,dailyNAV:x.nav,s1NAV:ps[i].nav}));
 const extreme=[...deltaByDay].sort((a,b)=>b.deltaLog-a.deltaLog);
 const overall=deltaByDay.reduce((sum,x)=>sum+x.deltaLog,0),worst=deltaByDay.slice().sort((a,b)=>a.deltaLog-b.deltaLog),outliers={sumLogExcess:overall,topPositive:extreme.slice(0,12),topNegative:worst.slice(0,12),
  neutralizeTopOne:{date:extreme[0].date,relativeLogAnnual:(overall-extreme[0].deltaLog)*244/daily.length,
   counterfactualCAGR:Math.exp((Math.log(res["daily5__sixBp"].NAV)-extreme[0].deltaLog)*244/daily.length)-1},
  exclude2026LogAnnual:deltaByDay.filter(x=>x.year!=="2026").reduce((s,x)=>s+x.deltaLog,0)*244/deltaByDay.filter(x=>x.year!=="2026").length,
  relativeYear:Object.fromEntries([...new Set(daily.map(x=>x.year))].map(y=>[y,deltaByDay.filter(x=>x.year===y).reduce((s,x)=>s+x.deltaLog,0)]))
 };
 const csv=["date,year,Void_target,Void_state,Void_decision,Q90_raw_top,Q90_matched,Q90_E,Void_base_NAV,Q90_daily_NAV,Q90_S1_NAV,Daily_assetWeight,Daily_cashWeight,Daily_action,S1_assetWeight,S1_cashWeight,S1_action,VoidEntry,VoidExit,missing",
 ...daily.map((d,i)=>[d.date,d.year,d.asset,d.void?"DEFENSIVE_VOID":"NON_VOID",d.decision,d.rawTop,+d.compatible,d.E,base[i].nav,pa[i].nav,ps[i].nav,pa[i].actualAssetWeight,pa[i].actualCashWeight,pa[i].instruction,ps[i].actualAssetWeight,ps[i].actualCashWeight,ps[i].instruction,+pa[i].enteredVoid,+pa[i].exitedVoid,+d.missing].join(","))].join("\n")+"\n";
 const result={study:"Q10 formal Void freeze with actual holdings and Q90 nonVoid only",period:{first:daily[0].date,last:daily.at(-1).date,n:daily.length,
    nVoid:daily.filter(x=>x.void).length,nNonVoid:daily.filter(x=>!x.void).length,nValid:daily.filter(x=>x.compatible).length,
    nEffectivePositive:daily.filter(x=>x.compatible&&x.Ef>=.05).length,nNonVoidMismatch:daily.filter(x=>!x.void&&x.asset!==x.rawTop).length,
    nMissingGross:daily.filter(x=>x.missing).length},results:res,bootstrap:boot,outliers};
 return {result,csv,allPaths};
};
const files=process.argv.slice(2);if(files.length!==2)throw Error("expected historical formal Void CSV and Q90 frozen OOS CSV");
const {result}=runFormalVoid(files.map(f=>fs.readFileSync(f,"utf8")));
console.log(JSON.stringify(result,null,2));
